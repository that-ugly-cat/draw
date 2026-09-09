"""
The rules worth a test are the ones that would be expensive to get wrong.

Not coverage. That a save arriving without the lock is kept rather than refused;
that the guest surface never looks at an identity; that the size cap answers with
a code; that draw.io's own compressed payload is normalised on the way in; and
that both authentication modes behave, including the one place they differ that
a user can see — whether the app can end the session it is showing.
"""

import os
import tempfile

import pytest

os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("AUTH_MODE", "local")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from draw.server import storage  # noqa: E402
from draw.server.auth import hash_password  # noqa: E402
from draw.server.main import app  # noqa: E402
from draw.server.models import SessionLocal, User, init_db  # noqa: E402

XML_A = '<mxfile><diagram id="p1">A</diagram></mxfile>'
XML_B = '<mxfile><diagram id="p1">B</diagram></mxfile>'


@pytest.fixture(scope="module")
def client():
    init_db()
    db = SessionLocal()
    if not db.query(User).filter(User.email == "t@example.org").first():
        db.add(
            User(
                email="t@example.org",
                name="Tester",
                password_hash=hash_password("pw"),
                is_active=True,
            )
        )
        db.commit()
    db.close()
    c = TestClient(app)
    c.post("/login", data={"email": "t@example.org", "password": "pw"}, follow_redirects=False)
    return c


@pytest.fixture(scope="module")
def diagram_id(client):
    r = client.post("/app/new", data={"title": "T"}, follow_redirects=False)
    return int(r.headers["location"].rsplit("/", 1)[1])


def test_showcase_is_public_and_blind():
    """No session, no gate, and it still renders — with a way in."""
    anon = TestClient(app)
    r = anon.get("/")
    assert r.status_code == 200
    assert 'href="/app"' in r.text
    # and never a button back to the page you are already on
    assert 'href="/login"' not in r.text


def test_same_person_in_two_sessions_is_not_a_conflict(client, diagram_id):
    """A browser tab and a script, both yours, are one intent.

    Refusing one of them would park half your own work as an orphan somewhere
    you then have to go and find. What keeps this honest is on the client: the
    open editor learns the revision moved and reloads.
    """
    base = f"/api/d/{diagram_id}"
    first = client.post(base + "/save", json={"session": "sess-one", "xml": XML_A})
    assert first.json()["ok"] is True
    r1 = first.json()["revision"]

    second = client.post(base + "/save", json={"session": "sess-two", "xml": XML_B})
    body = second.json()
    assert body["ok"] is True
    # and the revision moved, which is what an open editor watches
    assert body["revision"] > r1


def test_a_different_person_still_orphans(client, diagram_id):
    """The rule that makes level 1 safe, for the case it was written for."""
    client.post(f"/api/d/{diagram_id}/save", json={"session": "owner-tab", "xml": XML_A})
    client.post(
        f"/app/d/{diagram_id}/links",
        data={"mode": "rw", "label": "G", "days": ""},
        follow_redirects=True,
    )
    token = _token(diagram_id, "rw")

    guest = TestClient(app)
    guest.cookies.set("guest_name", "Someone else")
    out = guest.post(f"/s/{token}/save", json={"session": "guest-1", "xml": XML_B}).json()
    assert out["ok"] is False
    assert out["reason"] == "lock_held"
    # The important half: it did not vanish.
    assert out["version"] is not None

    page = client.get(f"/app/d/{diagram_id}/versions")
    assert "lock held by" in page.text


def test_takeover_is_explicit(client, diagram_id):
    base = f"/api/d/{diagram_id}"
    assert client.post(base + "/lock", json={"session": "sess-two"}).json()["held"] is False
    stolen = client.post(base + "/lock", json={"session": "sess-two", "steal": True}).json()
    assert stolen["held"] is True


def _token(diagram_id: int, mode: str) -> str:
    """Read the token back from the database rather than off the page.

    Scraping the rendered list picks whichever link happens to be first, which
    made the read-only test pass a read-write token and then report the code as
    broken. The store is the unambiguous source.
    """
    from draw.server.models import ShareLink

    db = SessionLocal()
    try:
        row = (
            db.query(ShareLink)
            .filter(ShareLink.diagram_id == diagram_id, ShareLink.mode == mode)
            .order_by(ShareLink.id.desc())
            .first()
        )
        return row.token
    finally:
        db.close()


def test_guest_surface_ignores_identity_headers(client, diagram_id):
    """A valid gate header sent to /s/ must stay anonymous, by construction."""
    client.post(
        f"/app/d/{diagram_id}/links",
        data={"mode": "rw", "label": "L", "days": ""},
        follow_redirects=True,
    )
    token = _token(diagram_id, "rw")

    anon = TestClient(app)
    page = anon.get(f"/s/{token}", headers={"X-Borant-Sub": "someone", "X-Borant-Name": "Someone"})
    assert page.status_code == 200
    # It asks for a label instead of greeting the identity it was handed.
    assert "Someone" not in page.text


def test_read_only_link_cannot_save(client, diagram_id):
    client.post(
        f"/app/d/{diagram_id}/links",
        data={"mode": "ro", "label": "RO", "days": ""},
        follow_redirects=True,
    )
    token = _token(diagram_id, "ro")
    anon = TestClient(app)
    out = anon.post(f"/s/{token}/save", json={"session": "g", "xml": XML_B})
    assert out.status_code == 403


def test_size_cap_answers_with_a_code(client, diagram_id):
    big = '<mxfile><diagram id="p1">' + ("x" * (11 * 1024 * 1024)) + "</diagram></mxfile>"
    out = client.post(f"/api/d/{diagram_id}/save", json={"session": "sess-two", "xml": big})
    assert out.status_code == 413
    assert out.json()["error"] == "diagram_too_large"


def test_compressed_payload_is_normalised():
    """draw.io's deflate+base64 body comes back as plain XML."""
    import base64
    import urllib.parse
    import zlib

    inner = "<mxGraphModel><root><mxCell id=\"0\"/></root></mxGraphModel>"
    quoted = urllib.parse.quote(inner, safe="")
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = base64.b64encode(co.compress(quoted.encode()) + co.flush()).decode()

    out = storage.normalise(f'<mxfile><diagram id="p1">{packed}</diagram></mxfile>')
    assert "mxGraphModel" in out
    assert packed not in out


def test_plain_payload_is_left_alone():
    assert storage.normalise(XML_A) == XML_A


# --- the two modes -----------------------------------------------------------
#
# Both are first-class, so both get a test. The interesting half is sign-out:
# the app owns the session in local mode and does not in gateway mode, and the
# failure worth preventing is a button that clears nothing while the gate cookie
# stays alive.


def test_local_mode_signs_out():
    """Its own client, deliberately.

    Signing out mutates the caller's cookie jar, and this used to run against
    the module-scoped fixture: every test declared after it then ran
    unauthenticated and failed for a reason that had nothing to do with what it
    was checking. A test that changes shared state has to bring its own.
    """
    c = TestClient(app)
    c.post("/login", data={"email": "t@example.org", "password": "pw"},
           follow_redirects=False)
    r = c.get("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert "session" in r.headers.get("set-cookie", "")


def test_gateway_mode_does_not_fake_a_sign_out(monkeypatch):
    from draw.server import main as m

    monkeypatch.setattr(m, "gateway_mode", lambda: True)
    monkeypatch.setattr(m, "GATE_LOGOUT_URL", "")
    r = TestClient(m.app).get("/logout", follow_redirects=False)
    assert r.status_code == 501
    # and above all it does not clear a cookie it does not own
    assert "set-cookie" not in r.headers


def test_gateway_mode_hands_sign_out_to_the_configured_endpoint(monkeypatch):
    from draw.server import main as m

    monkeypatch.setattr(m, "gateway_mode", lambda: True)
    monkeypatch.setattr(m, "GATE_LOGOUT_URL", "https://gate.example.org/logout")
    r = TestClient(m.app).get("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "https://gate.example.org/logout"


def test_login_and_logout_are_public_paths():
    """Both must be reachable without the gate turning them away.

    They qualify under the house rule — no method on them needs to know who is
    asking — and in gateway mode the app has something to say on each: a way in,
    and where sign-out actually lives.
    """
    from draw.server.main import PUBLIC_PATHS

    assert "/login" in PUBLIC_PATHS
    assert "/logout" in PUBLIC_PATHS


# --- the MCP surface ---------------------------------------------------------


def _key_for(email: str = "t@example.org") -> str:
    from draw.server.models import ApiKey

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        row = ApiKey(user_id=u.id, key=f"k-{email}", label="test")
        db.add(row)
        db.commit()
        return row.key
    finally:
        db.close()


def test_mcp_without_a_key_is_refused_by_the_app(client):
    """401, and the body is the app's.

    Worth asserting the body and not the number: with /mcp still inside the gate
    the same 401 arrives from Borant ID instead, and whoever counts status codes
    declares a job finished that has not started.
    """
    r = TestClient(app).post("/mcp", json={})
    assert r.status_code == 401
    assert r.json()["error"] == "missing or invalid API key"


def test_mcp_path_without_the_slash_does_not_redirect(client):
    """The endpoint advertised is the one without the trailing slash.

    A Starlette mount answers that with a 307, and MCP clients do not follow
    redirects on POST — behind TLS termination it is worse, because the app
    builds an http:// redirect. The middleware normalises it, so the failure to
    guard against is a 307 rather than any particular success.
    """
    r = TestClient(app).post("/mcp", json={}, follow_redirects=False)
    assert r.status_code != 307


def test_tools_run_as_the_key_owner(client, diagram_id):
    from draw.server import mcp_app
    from draw.server.auth import hash_password, set_caller

    db = SessionLocal()
    try:
        me = db.query(User).filter(User.email == "t@example.org").first()
        other = db.query(User).filter(User.email == "other@example.org").first()
        if not other:
            other = User(email="other@example.org", name="Other",
                         password_hash=hash_password("x"), is_active=True)
            db.add(other)
            db.commit()
        my_id, other_id = me.id, other.id
    finally:
        db.close()

    set_caller(type("U", (), {"id": my_id, "label": "Tester"})())
    assert any(d["id"] == diagram_id for d in mcp_app.list_diagrams()["diagrams"])

    # Somebody else's diagram is "not found", never "forbidden": otherwise the
    # model can enumerate what it cannot read.
    set_caller(type("U", (), {"id": other_id, "label": "Other"})())
    assert "error" in mcp_app.outline_diagram(diagram_id)
    assert mcp_app.list_diagrams()["count"] == 0


def test_outline_is_far_smaller_than_the_document(client, diagram_id):
    """The reason the surface is shaped this way at all."""
    import json

    from draw.server import mcp_app
    from draw.server.auth import set_caller

    db = SessionLocal()
    try:
        me = db.query(User).filter(User.email == "t@example.org").first()
        set_caller(type("U", (), {"id": me.id, "label": "Tester"})())
    finally:
        db.close()

    big = ('<mxfile><diagram id="p" name="P"><mxGraphModel><root>'
           '<mxCell id="0"/><mxCell id="1" parent="0"/>'
           + "".join(
               f'<mxCell id="c{i}" value="Shape {i}" style="whiteSpace=wrap;'
               f'rounded=1;fillColor=#EAF1FB;strokeColor=#2E5FA3;fontSize=9;" '
               f'vertex="1" parent="1"><mxGeometry x="{i * 120}" y="0" '
               f'width="100" height="60" as="geometry"/></mxCell>'
               for i in range(40))
           + "</root></mxGraphModel></diagram></mxfile>")
    mcp_app.update_diagram(diagram_id, big)

    full = len(mcp_app.get_diagram(diagram_id)["xml"])
    outline = len(json.dumps(mcp_app.outline_diagram(diagram_id)))
    assert outline < full / 2


def test_update_cells_patches_by_id(client, diagram_id):
    from draw.server import mcp_app
    from draw.server.auth import set_caller

    db = SessionLocal()
    try:
        me = db.query(User).filter(User.email == "t@example.org").first()
        set_caller(type("U", (), {"id": me.id, "label": "Tester"})())
    finally:
        db.close()

    out = mcp_app.update_cells(diagram_id, [{"cell_id": "c3", "text": "Renamed", "width": 200}])
    assert out["saved"] is True
    assert out["applied"] == ["c3"]

    shapes = mcp_app.outline_diagram(diagram_id)["pages"][0]["shapes"]
    changed = next(s for s in shapes if s["id"] == "c3")
    assert changed["text"] == "Renamed"
    assert changed["width"] == 200
    # and nothing else moved
    assert next(s for s in shapes if s["id"] == "c4")["text"] == "Shape 4"


def test_check_diagram_reports_a_label_that_will_not_fit():
    from draw.server import mcp_app

    tight = ('<mxfile><diagram id="p" name="P"><mxGraphModel><root>'
             '<mxCell id="0"/><mxCell id="1" parent="0"/>'
             '<mxCell id="tiny" value="Clinics and ethics committees and then some" '
             'style="whiteSpace=wrap;fontSize=8;" vertex="1" parent="1">'
             '<mxGeometry x="0" y="0" width="60" height="16" as="geometry"/></mxCell>'
             "</root></mxGraphModel></diagram></mxfile>")
    out = mcp_app.check_diagram(xml=tight)
    kinds = [f["kind"] for f in out["findings"]]
    assert "label_overflow" in kinds


def test_lock_reports_the_same_revision_the_save_returned(client, diagram_id):
    """The invariant the open editor leans on.

    The page decides "did this document move?" by comparing the revision a lock
    refresh reports against the one its own last save returned. If those two
    numbers could drift apart, every refresh would look like somebody else's
    change — which is the shape of the bug that put a "changed elsewhere" banner
    on a diagram nobody else had touched.
    """
    base = f"/api/d/{diagram_id}"
    saved = client.post(base + "/save", json={"session": "s1", "xml": XML_A}).json()
    lock = client.post(base + "/lock", json={"session": "s1"}).json()
    assert lock["revision"] == saved["revision"]


def test_every_write_moves_the_revision_exactly_once(client, diagram_id):
    base = f"/api/d/{diagram_id}"
    a = client.post(base + "/save", json={"session": "s1", "xml": XML_A}).json()["revision"]
    b = client.post(base + "/save", json={"session": "s1", "xml": XML_B}).json()["revision"]
    assert b == a + 1


def test_the_moved_banner_is_not_visible_by_default(client, diagram_id):
    """It carries `hidden`, and nothing in the markup may override it.

    The first version set `display:flex` inline next to the attribute. An inline
    display beats the browser's own `[hidden] { display: none }`, so the banner
    read as hidden in the markup and was on screen from the moment the page
    loaded — announcing a change on diagrams nobody had touched. The layout now
    lives in a class, and a global rule makes the attribute win regardless.
    """
    page = client.get(f"/app/d/{diagram_id}").text
    banner = page[page.index('id="moved-banner"'):]
    banner = banner[:banner.index(">")]
    assert "hidden" in banner
    assert "display" not in banner, "inline display would defeat the hidden attribute"


def test_the_keys_page_is_reachable_by_clicking(client, diagram_id):
    """A page nothing links to is a page that does not exist for the user.

    The MCP key manager worked from the first commit and was unreachable from
    the interface for as long: the only way in was typing the URL.
    """
    assert 'href="/app/keys"' in client.get("/app").text
    assert client.get("/app/keys").status_code == 200


def test_the_keys_link_never_reaches_a_guest_or_the_showcase(client, diagram_id):
    """It hangs off `user`, which those two surfaces never carry."""
    client.post(
        f"/app/d/{diagram_id}/links",
        data={"mode": "ro", "label": "G", "days": ""},
        follow_redirects=True,
    )
    token = _token(diagram_id, "ro")
    anon = TestClient(app)
    assert "/app/keys" not in anon.get("/").text
    assert "/app/keys" not in anon.get(f"/s/{token}").text
