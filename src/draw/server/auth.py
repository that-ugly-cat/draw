"""
Authentication — the borant house pattern, in both of its modes.

    local     email + password against the users table  (default)
    gateway   an upstream Borant ID gate vouches via X-Borant-*

`local` is the default for security before portability: an app that believes an
identity header with nothing in front of it lets in anyone who can send that
header. The gateway path stays dead code until someone turns it on deliberately,
and even then the request has to arrive from the expected proxy.

Nothing here is reached from `/s/`. The guest surface is authorised by a token
and never by an identity, and it must stay that way by construction — see
main.py, where no handler under that prefix imports from this module.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import User, get_db

log = logging.getLogger("draw.auth")

SECRET_KEY = os.environ.get("JWT_SECRET", "")
ALGORITHM = "HS256"
EXPIRE_DAYS = 7
COOKIE = "session"

AUTH_MODE = os.environ.get("AUTH_MODE", "local").strip().lower()

# Under Docker this is the bridge gateway address and NOT 127.0.0.1. It takes a
# list, and it must: adding a network moves which gateway Docker picks — it
# chooses in alphabetical order of network name — and a moved gateway silently
# stops the app believing the gate. That is how a login died on 8 Sept 2026.
TRUSTED_PROXY = os.environ.get("BORANT_TRUSTED_PROXY", "127.0.0.1")


def _parse_trusted(raw: str) -> list:
    nets = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            nets.append(ipaddress.ip_network(chunk, strict=False))
        except ValueError:
            log.warning("BORANT_TRUSTED_PROXY: ignoring %r, not an address or CIDR", chunk)
    return nets


TRUSTED_PROXIES = _parse_trusted(TRUSTED_PROXY)


def gateway_mode() -> bool:
    return AUTH_MODE == "gateway"


def _from_trusted_proxy(request: Request) -> bool:
    peer = request.client.host if request.client else None
    if not peer:
        return False
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(addr in net for net in TRUSTED_PROXIES)


def user_from_gateway(request: Request, db: Session) -> User | None:
    """The user the gate vouched for, or None. Lookup by subject, never email."""
    if not gateway_mode():
        return None
    sub = request.headers.get("x-borant-sub")
    if not sub:
        return None
    if not _from_trusted_proxy(request):
        log.warning(
            "X-Borant-Sub from %s, outside BORANT_TRUSTED_PROXY (%s): ignored",
            request.client.host if request.client else "?",
            TRUSTED_PROXY,
        )
        return None

    user = db.query(User).filter(User.borant_sub == sub).first()
    if user is not None:
        return user if user.is_active else None

    email = (
        request.headers.get("x-borant-email", "") or f"{sub}@borant.invalid"
    ).strip().lower()
    if db.query(User).filter(User.email == email).first() is not None:
        # Never adopt an existing row by email: an email is something a gate
        # operator types and a subject is not, so adopting on a typo would hand
        # over someone else's workspace.
        placeholder = f"{sub}@borant.invalid".lower()
        log.warning(
            "gateway: %s already belongs to a local account with no borant_sub; "
            "created a separate profile as %s",
            email,
            placeholder,
        )
        email = placeholder

    hint = (request.headers.get("x-borant-hint", "") or "").strip()
    if hint:
        # No role vocabulary is declared for this app in the gate, because the
        # code reads none. Declaring one would offer a menu that opens nothing.
        log.info("gateway: hint %r ignored — draw declares no roles", hint)

    return _provision(db, sub, email, request.headers.get("x-borant-name", "") or email)


def _provision(db: Session, sub: str, email: str, name: str) -> User | None:
    """Create the profile, surviving the race two parallel requests create.

    SELECT-then-INSERT on a UNIQUE `borant_sub` is the defect found across six
    apps in September 2026: a page and its own XHR arrive together and both
    insert. Invisible with four users, a 500 at the start of a lecture with a
    hundred. Catching the IntegrityError and re-reading is the whole fix.

    Anything a new profile needs goes in here and not in a registration
    handler — a profile created by another road would skip it, which is the
    mistake ArguMap made with its welcome map.
    """
    user = User(
        email=email,
        name=name,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        borant_sub=sub,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(User).filter(User.borant_sub == sub).first()
    db.refresh(user)
    log.info("gateway: new profile for %s (%s)", email, sub)
    return user


# --- passwords and tokens (local mode) ---------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _decode(token: str) -> int:
    try:
        return int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")


# --- who is asking -----------------------------------------------------------


class GateNotInFront(HTTPException):
    """503, not a redirect to /login.

    In gateway mode a request with no identity means the gate did not run, which
    is a configuration fault and not a logged-out visitor. Redirecting would put
    the app and the gate in a loop that production hides, because the gate
    intercepts first — so it only ever shows up under a broken matcher, at the
    worst moment.
    """

    def __init__(self):
        super().__init__(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No identity on a gated route: the Borant ID gate did not run in "
            "front of this request. Check the Caddy site block and "
            "BORANT_TRUSTED_PROXY.",
        )


def get_current_user(
    request: Request,
    session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if gateway_mode():
        user = user_from_gateway(request, db)
        if not user:
            raise GateNotInFront()
        return user

    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = (
        db.query(User)
        .filter(User.id == _decode(session), User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def get_user_or_none(
    session: str | None, db: Session, request: Request | None = None
) -> User | None:
    """Plain function, not a Depends: for pages that also render logged out.

    Never call this from a handler under `/s/`, and never from the showcase at
    `/`. The showcase must not look at who is reading it: identity headers are
    stripped on the public branch, so `{% if user %}` there is always false with
    the gate and sometimes true without it — the same page with two behaviours.
    """
    if gateway_mode():
        return user_from_gateway(request, db) if request is not None else None
    if not session:
        return None
    try:
        uid = _decode(session)
    except HTTPException:
        return None
    return db.query(User).filter(User.id == uid, User.is_active.is_(True)).first()
