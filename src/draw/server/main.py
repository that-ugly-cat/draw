"""
draw — the server.

Route layout, which is also the security boundary:

    /                public showcase, never looks at who is reading it
    /healthz         public
    /static/*        public
    /lang/{code}     public, sets a cookie
    /editor/*        public — served by Caddy straight from the drawio
                     container, never by this app
    /s/*             the guest surface: authorised by a token, and no handler
                     under this prefix ever looks at X-Borant-* or a session
    /app, /api/*     gated

The list below is the single place those public paths are declared, and
`caddy.py` reads it to print the site block. Generated rather than written, so
the day somebody adds a public route they notice while writing it.
"""

from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import locking, storage
from .auth import (
    COOKIE,
    GateNotInFront,
    create_token,
    gateway_mode,
    get_current_user,
    get_user_or_none,
    verify_password,
)
from .locales import DATE_FORMAT, DEFAULT, LANGUAGES, pick, t
from .models import Diagram, DiagramVersion, ShareLink, User, get_db, init_db, utcnow

log = logging.getLogger("draw.main")

# The matcher lists the *public* paths and not the private ones, deliberately:
# the default branch is the gated one, so a route added later is born closed
# rather than open.
PUBLIC_PATHS = [
    "/",             # the showcase, which never looks at its reader
    "/healthz",
    "/static/*",
    "/lang/*",
    "/editor/*",     # the drawio container, reached by Caddy, never by this app
    "/s/*",          # the guest surface, authorised by a token and not identity
    "/login",        # in gateway mode the app turns these away itself, rather
    "/logout",       # than bouncing off the gate to say something it knows
]

# Where the gate ends a session, when there is a gate. Empty in standalone, and
# empty is a working answer: with no value the app stops offering a sign-out it
# cannot perform, instead of pretending. Configurable rather than hardwired,
# because the app has to keep working with no Borant ID anywhere in sight.
GATE_LOGOUT_URL = os.environ.get("GATE_LOGOUT_URL", "").strip()

HERE = os.path.dirname(os.path.abspath(__file__))
GUEST_NAME_COOKIE = "guest_name"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """A lifespan, not on_event.

    Nothing needs it yet, but the day an MCP surface is mounted here its session
    manager has to run inside the *parent* app's lifespan: mounts do not
    propagate lifespans, and without it the transport answers 500 without saying
    why. Starting in the right shape costs nothing now and saves that.
    """
    init_db()
    yield


app = FastAPI(title="draw", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))


# --- rendering ----------------------------------------------------------------


def _lang(request: Request) -> str:
    return pick(request.headers.get("accept-language"), request.cookies.get("lang"))


def render(request: Request, name: str, ctx: dict | None = None) -> HTMLResponse:
    lang = _lang(request)
    base = {
        "lang": lang,
        "languages": LANGUAGES,
        "t": lambda key, **kw: t(lang, key, **kw),
        "fmt": lambda d: d.strftime(DATE_FORMAT.get(lang, DATE_FORMAT[DEFAULT])) if d else "",
        # Templates need to know which mode they are rendering in, because some
        # affordances only exist in one of them: the app owns the session in
        # local mode and does not in gateway mode, so it can offer sign-out in
        # the first case and only pass the request along in the second.
        "gateway": gateway_mode(),
        "can_sign_out": (not gateway_mode()) or bool(GATE_LOGOUT_URL),
    }
    return templates.TemplateResponse(request, name, {**base, **(ctx or {})})


@app.exception_handler(storage.DiagramTooLarge)
def _too_large(request: Request, exc: storage.DiagramTooLarge):
    lang = _lang(request)
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={
            "error": exc.code,
            "size": exc.size,
            "limit": exc.limit,
            "message": t(
                lang,
                "err_diagram_too_large",
                limit=exc.limit // (1024 * 1024),
                size=round(exc.size / (1024 * 1024), 1),
            ),
        },
    )


@app.exception_handler(GateNotInFront)
def _gate_missing(request: Request, exc: GateNotInFront):
    # 503 with the message aimed at the operator, not a redirect to /login: a
    # gated request with no identity means the gate did not run.
    log.error("gated route %s reached with no identity", request.url.path)
    return PlainTextResponse(exc.detail, status_code=exc.status_code)


# --- public -------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def showcase(request: Request):
    """The showcase, and it never looks at who is reading it.

    Not an oversight: on the public branch identity headers are stripped by
    construction, so `{% if user %}` here would be always false with the gate and
    sometimes true without it — the same page with two behaviours. Not looking,
    the page is identical in both modes and one button covers all four cases.

    The button points at /app, a gated path, and never at /login: a page that
    cannot recognise anybody, with a button back to itself, is a ring nobody
    gets into.
    """
    return render(request, "showcase.html")


@app.get("/healthz")
def healthz():
    # Stays green even when the gate is dead and nobody can get in any more, so
    # a useful check also points at a gated route.
    return {"ok": True}


@app.get("/lang/{code}")
def set_language(code: str, request: Request):
    target = request.headers.get("referer") or "/"
    resp = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    if code in LANGUAGES:
        resp.set_cookie("lang", code, max_age=31536000, httponly=False, samesite="lax")
    return resp


# --- sign in (local mode only) -------------------------------------------------


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if gateway_mode():
        # In gateway mode this route draws a way *into* the gate and does not
        # bounce back to the root. The root is public, so forward_auth never
        # fires there: an app that redirects to its own /login, which redirects
        # to the root, builds a ring that survives testing because tests run
        # locally. Dovetail found this the hard way on the way in.
        return render(request, "login.html", {"gateway": True})
    return render(request, "login.html", {"gateway": False})


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if gateway_mode():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return render(request, "login.html", {"gateway": False, "failed": True})
    resp = RedirectResponse("/app", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(COOKIE, create_token(user.id), httponly=True, samesite="lax")
    return resp


@app.get("/logout")
def logout():
    """Ending a session the app does not own is not something it can fake.

    In local mode the cookie is ours and deleting it is the whole of it. In
    gateway mode the session belongs to the gate: clearing anything here would
    leave the browser holding a live gate cookie while the page claims to be
    signed out, which is worse than not offering the button. So the app either
    hands the request to the configured gate endpoint, or — with none
    configured — says plainly that sign-out lives elsewhere.
    """
    if gateway_mode():
        if GATE_LOGOUT_URL:
            return RedirectResponse(GATE_LOGOUT_URL, status_code=status.HTTP_303_SEE_OTHER)
        return PlainTextResponse(
            "Sign-out is handled by the identity gate in front of this app, and "
            "no GATE_LOGOUT_URL is configured. Close the browser session, or set "
            "that variable to the gate's logout endpoint.",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )
    resp = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(COOKIE)
    return resp


# --- the workspace -------------------------------------------------------------


def _owned(db: Session, diagram_id: int, user: User) -> Diagram:
    d = (
        db.query(Diagram)
        .filter(Diagram.id == diagram_id, Diagram.owner_id == user.id)
        .first()
    )
    if not d:
        # What you cannot reach answers "not found" and never "forbidden", so
        # nobody can enumerate what they cannot read.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return d


@app.get("/app", response_class=HTMLResponse)
def workspace(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrams = (
        db.query(Diagram)
        .filter(Diagram.owner_id == user.id, Diagram.deleted_at.is_(None))
        .order_by(Diagram.updated_at.desc())
        .all()
    )
    binned = (
        db.query(Diagram)
        .filter(Diagram.owner_id == user.id, Diagram.deleted_at.isnot(None))
        .order_by(Diagram.deleted_at.desc())
        .all()
    )
    now = utcnow()
    return render(
        request,
        "workspace.html",
        {
            "user": user,
            "diagrams": diagrams,
            "binned": binned,
            "lock_state": {d.id: locking.inspect(d, None, now) for d in diagrams},
            "share_counts": {
                d.id: sum(1 for s in d.share_links if s.is_live(now)) for d in diagrams
            },
        },
    )


@app.post("/app/new")
def new_diagram(
    title: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = Diagram(
        owner_id=user.id,
        title=(title.strip() or "Untitled")[:200],
        xml=storage.EMPTY_DIAGRAM,
        size_bytes=len(storage.EMPTY_DIAGRAM.encode("utf-8")),
        updated_by_label=user.label,
    )
    db.add(d)
    db.commit()
    return RedirectResponse(f"/app/d/{d.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/app/d/{diagram_id}", response_class=HTMLResponse)
def editor(
    diagram_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    return render(
        request,
        "editor.html",
        {
            "user": user,
            "d": d,
            "mode": "rw",
            "api_base": f"/api/d/{d.id}",
            "lock": locking.inspect(d, None),
            "editor_url": os.environ.get("EDITOR_URL", "/editor/"),
        },
    )


@app.post("/app/d/{diagram_id}/rename")
def rename(
    diagram_id: int,
    title: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    d.title = (title.strip() or "Untitled")[:200]
    db.commit()
    return RedirectResponse("/app", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/app/d/{diagram_id}/delete")
def delete(
    diagram_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    d.deleted_at = utcnow()
    db.commit()
    return RedirectResponse("/app", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/app/d/{diagram_id}/restore")
def restore(
    diagram_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    d.deleted_at = None
    db.commit()
    return RedirectResponse("/app", status_code=status.HTTP_303_SEE_OTHER)


# --- versions ------------------------------------------------------------------


@app.get("/app/d/{diagram_id}/versions", response_class=HTMLResponse)
def versions(
    diagram_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    rows = (
        db.query(DiagramVersion)
        .filter(DiagramVersion.diagram_id == d.id)
        .order_by(DiagramVersion.created_at.desc())
        .limit(200)
        .all()
    )
    return render(request, "versions.html", {"user": user, "d": d, "versions": rows})


@app.post("/app/d/{diagram_id}/versions/{version_id}/pin")
def pin_version(
    diagram_id: int,
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    v = (
        db.query(DiagramVersion)
        .filter(DiagramVersion.id == version_id, DiagramVersion.diagram_id == d.id)
        .first()
    )
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    v.pinned = not v.pinned
    db.commit()
    return RedirectResponse(
        f"/app/d/{d.id}/versions", status_code=status.HTTP_303_SEE_OTHER
    )


@app.get("/app/d/{diagram_id}/versions/{version_id}/raw")
def version_raw(
    diagram_id: int,
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    v = (
        db.query(DiagramVersion)
        .filter(DiagramVersion.id == version_id, DiagramVersion.diagram_id == d.id)
        .first()
    )
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return Response(
        storage.decompress(v.xml_z),
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{d.id}-v{v.version_no}.drawio"'
        },
    )


# --- share links ---------------------------------------------------------------


@app.get("/app/d/{diagram_id}/links", response_class=HTMLResponse)
def links(
    diagram_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    return render(
        request,
        "links.html",
        {
            "user": user,
            "d": d,
            "links": sorted(d.share_links, key=lambda s: s.created_at, reverse=True),
            "now": utcnow(),
            "base_url": str(request.base_url).rstrip("/"),
        },
    )


@app.post("/app/d/{diagram_id}/links")
def create_link(
    diagram_id: int,
    mode: str = Form(...),
    label: str = Form(""),
    days: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    if mode not in ("ro", "rw"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad_mode")
    expires = None
    if days.strip().isdigit() and int(days) > 0:
        expires = utcnow() + timedelta(days=int(days))
    db.add(
        ShareLink(
            diagram_id=d.id,
            token=secrets.token_urlsafe(24),
            mode=mode,
            label=(label.strip() or None),
            created_by_user_id=user.id,
            expires_at=expires,
        )
    )
    db.commit()
    return RedirectResponse(f"/app/d/{d.id}/links", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/app/d/{diagram_id}/links/{link_id}/revoke")
def revoke_link(
    diagram_id: int,
    link_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    link = (
        db.query(ShareLink)
        .filter(ShareLink.id == link_id, ShareLink.diagram_id == d.id)
        .first()
    )
    if not link:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    link.revoked_at = utcnow()
    db.commit()
    return RedirectResponse(f"/app/d/{d.id}/links", status_code=status.HTTP_303_SEE_OTHER)


# --- saving, shared by both surfaces -------------------------------------------
#
# Deliberately a plain function taking a label and an origin rather than a user:
# the guest surface calls it too, and nothing on that path may reach for an
# identity.


def _apply_save(
    db: Session,
    d: Diagram,
    raw_xml: str,
    session_id: str,
    *,
    label: str,
    user_id: int | None,
    origin: str,
    share_link_id: int | None = None,
) -> dict:
    xml = storage.normalise(raw_xml)
    size = storage.check_size(xml)  # raises DiagramTooLarge; nothing is lost
    now = utcnow()
    state = locking.inspect(d, session_id, now)

    if state.held_by_other:
        # The rule that makes level 1 safe. A save without a valid lock is never
        # thrown away: it is parked with the reason written down, and the client
        # is told which version it became. Worst case a merge by hand, never an
        # hour lost.
        version = storage.snapshot(
            db,
            d,
            xml,
            author_label=label,
            author_user_id=user_id,
            origin=origin,
            share_link_id=share_link_id,
            orphan=True,
            orphan_reason=f"lock held by {state.label}",
        )
        db.commit()
        return {
            "ok": False,
            "reason": "lock_held",
            "holder": state.label,
            "version": version.version_no if version else None,
        }

    if storage.should_version(d, db, now):
        storage.snapshot(
            db,
            d,
            d.xml,
            author_label=d.updated_by_label,
            origin=origin,
            share_link_id=share_link_id,
        )

    d.xml = xml
    d.size_bytes = size
    d.updated_at = now
    d.updated_by_label = label
    locking.acquire(db, d, session_id, label, user_id, now=now)
    db.commit()
    return {"ok": True, "version": d.version_no, "saved_at": now.isoformat()}


def _lock_payload(state: locking.LockState) -> dict:
    return {
        "held": state.held,
        "held_by_other": state.held_by_other,
        "label": state.label,
        "expires_at": state.expires_at.isoformat() if state.expires_at else None,
        "ttl": int(locking.LOCK_TTL.total_seconds()),
        "refresh": int(locking.REFRESH_EVERY.total_seconds()),
    }


# --- owner API -----------------------------------------------------------------


@app.post("/api/d/{diagram_id}/lock")
async def api_lock(
    diagram_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    body = await request.json()
    state = locking.acquire(
        db,
        d,
        body["session"],
        user.label,
        user.id,
        steal=bool(body.get("steal")),
    )
    db.commit()
    return _lock_payload(state)


@app.post("/api/d/{diagram_id}/unlock")
async def api_unlock(
    diagram_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    body = await request.json()
    locking.release(db, d, body["session"])
    db.commit()
    return {"ok": True}


@app.post("/api/d/{diagram_id}/save")
async def api_save(
    diagram_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    body = await request.json()
    return _apply_save(
        db,
        d,
        body.get("xml", ""),
        body["session"],
        label=user.label,
        user_id=user.id,
        origin="owner",
    )


@app.post("/api/d/{diagram_id}/thumb")
async def api_thumb(
    diagram_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The thumbnail is produced by the client and posted here.

    No headless renderer in v1: the embed protocol already returns a PNG from
    the browser that is doing the editing, and a second container that exists to
    redraw what somebody just drew is a container to maintain for nothing.
    """
    import base64

    d = _owned(db, diagram_id, user)
    body = await request.json()
    data = (body.get("png") or "").split(",", 1)[-1]
    if data:
        blob = base64.b64decode(data)
        if len(blob) <= 512 * 1024:
            d.thumb_png = blob
            db.commit()
    return {"ok": True}


@app.get("/app/d/{diagram_id}/thumb.png")
def thumb(
    diagram_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _owned(db, diagram_id, user)
    if not d.thumb_png:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return Response(d.thumb_png, media_type="image/png")


# --- the guest surface ---------------------------------------------------------
#
# Everything below is public, and the property that makes that safe is
# structural rather than careful: no handler here reads X-Borant-*, a session
# cookie, or anything else that says who is asking. The token authorises; the
# identity never enters. A valid header sent to these routes stays anonymous
# even if the proxy forgot to strip it.
#
# The day a route under this prefix needs to know *who* is asking, it does not
# belong here: it moves under the gated prefix. It is not carved out by method.


def _by_token(db: Session, token: str) -> tuple[ShareLink, Diagram]:
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not link or not link.is_live():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "link_dead")
    d = db.query(Diagram).filter(Diagram.id == link.diagram_id).first()
    if not d or d.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return link, d


def _touch(db: Session, link: ShareLink) -> None:
    link.last_used_at = utcnow()
    link.use_count = (link.use_count or 0) + 1


@app.get("/s/{token}", response_class=HTMLResponse)
def guest(token: str, request: Request, db: Session = Depends(get_db)):
    link, d = _by_token(db, token)
    _touch(db, link)
    db.commit()
    name = request.cookies.get(GUEST_NAME_COOKIE)
    if link.mode == "rw" and not name:
        # A label, asked once. Not an identity, and the page says so.
        return render(request, "guest_name.html", {"token": token, "d": d})
    return render(
        request,
        "editor.html",
        {
            "user": None,
            "d": d,
            "mode": link.mode,
            "guest_label": name,
            "api_base": f"/s/{token}",
            "lock": locking.inspect(d, None),
            "editor_url": os.environ.get("EDITOR_URL", "/editor/"),
        },
    )


@app.post("/s/{token}/name")
def guest_name(token: str, name: str = Form(...), db: Session = Depends(get_db)):
    _by_token(db, token)
    resp = RedirectResponse(f"/s/{token}", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        GUEST_NAME_COOKIE,
        (name.strip() or "Guest")[:60],
        max_age=31536000,
        samesite="lax",
    )
    return resp


def _guest_label(request: Request) -> str:
    return (request.cookies.get(GUEST_NAME_COOKIE) or "Guest")[:60]


@app.post("/s/{token}/lock")
async def guest_lock(token: str, request: Request, db: Session = Depends(get_db)):
    link, d = _by_token(db, token)
    if link.mode != "rw":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read_only")
    body = await request.json()
    state = locking.acquire(
        db,
        d,
        body["session"],
        _guest_label(request),
        None,
        steal=bool(body.get("steal")),
    )
    _touch(db, link)
    db.commit()
    return _lock_payload(state)


@app.post("/s/{token}/unlock")
async def guest_unlock(token: str, request: Request, db: Session = Depends(get_db)):
    _link, d = _by_token(db, token)
    body = await request.json()
    locking.release(db, d, body["session"])
    db.commit()
    return {"ok": True}


@app.post("/s/{token}/save")
async def guest_save(token: str, request: Request, db: Session = Depends(get_db)):
    link, d = _by_token(db, token)
    if link.mode != "rw":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read_only")
    body = await request.json()
    _touch(db, link)
    return _apply_save(
        db,
        d,
        body.get("xml", ""),
        body["session"],
        label=_guest_label(request),
        user_id=None,
        origin="share",
        share_link_id=link.id,
    )
