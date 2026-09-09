"""
The rules worth a test are the ones that would be expensive to get wrong.

Not coverage: four behaviours. That a save arriving without the lock is kept
rather than refused; that the guest surface never looks at an identity; that the
size cap answers with a code; and that draw.io's own compressed payload is
normalised on the way in.
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


def test_save_without_the_lock_is_kept_not_refused(client, diagram_id):
    """The rule that makes level 1 safe."""
    base = f"/api/d/{diagram_id}"
    first = client.post(base + "/save", json={"session": "sess-one", "xml": XML_A})
    assert first.json()["ok"] is True

    # A second session saves while the first still holds the lock.
    second = client.post(base + "/save", json={"session": "sess-two", "xml": XML_B})
    body = second.json()
    assert body["ok"] is False
    assert body["reason"] == "lock_held"
    # The important half: it did not vanish.
    assert body["version"] is not None

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
