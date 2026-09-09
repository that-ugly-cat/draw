"""
What happens to the XML between the editor and the database.

Three jobs: normalise what draw.io sends into the canonical form, decide when a
save becomes a version rather than just an overwrite, and keep the history from
growing without bound.

The size cap lives here too, because the only place worth enforcing it is the
one place every write passes through.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import urllib.parse
import zlib
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Diagram, DiagramVersion, utcnow

log = logging.getLogger("draw.storage")

# SPEC.md §7. Enforced on the current XML at save time. The case that trips it
# is somebody pasting a screenshot: draw.io embeds it as a data URI and the
# document grows tenfold.
MAX_DIAGRAM_BYTES = 10 * 1024 * 1024

# A save becomes a version after this much activity, not on every autosave
# event. Separating the two frequencies is what stops an afternoon's work from
# producing hundreds of complete copies of a large document.
VERSION_DEBOUNCE = timedelta(minutes=5)

EMPTY_DIAGRAM = (
    '<mxfile host="draw.borant.eu">'
    '<diagram id="page-1" name="Page-1">'
    '<mxGraphModel dx="1100" dy="800" grid="1" gridSize="10" guides="1" '
    'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
    'pageWidth="850" pageHeight="1100" math="0" shadow="0">'
    "<root>"
    '<mxCell id="0" />'
    '<mxCell id="1" parent="0" />'
    "</root>"
    "</mxGraphModel>"
    "</diagram>"
    "</mxfile>"
)


class DiagramTooLarge(Exception):
    """Carries a code, not a sentence.

    Whoever raises an error does not know what language it will be read in;
    whoever renders the page does. The template turns `diagram_too_large` into
    words, and the size travels alongside as a number.
    """

    code = "diagram_too_large"

    def __init__(self, size: int):
        super().__init__(self.code)
        self.size = size
        self.limit = MAX_DIAGRAM_BYTES


_DIAGRAM_TAG = re.compile(
    r"(<diagram\b[^>]*>)(.*?)(</diagram>)", re.DOTALL | re.IGNORECASE
)


def _inflate_payload(payload: str) -> str | None:
    """Undo draw.io's own compression of a <diagram> body, or return None.

    The format is base64 -> raw deflate -> percent-encoded UTF-8, which is the
    inverse of what the editor does on the way out. Returning None rather than
    raising is deliberate: an uncompressed body is the common case and must not
    look like a failure.
    """
    payload = payload.strip()
    if not payload or payload.startswith("<"):
        return None
    try:
        raw = base64.b64decode(payload, validate=True)
        inflated = zlib.decompress(raw, -15).decode("utf-8")
        return urllib.parse.unquote(inflated)
    except Exception:
        return None


def normalise(xml: str) -> str:
    """The canonical form: uncompressed XML, whatever the editor sent.

    draw.io can write the body of each <diagram> as deflate+base64. It is
    inflated here, once, on the way in — see the note on `Diagram.xml` for why
    the plain form is the one worth keeping.
    """
    if not xml:
        return EMPTY_DIAGRAM

    def repl(m: re.Match) -> str:
        inflated = _inflate_payload(m.group(2))
        return m.group(1) + inflated + m.group(3) if inflated else m.group(0)

    return _DIAGRAM_TAG.sub(repl, xml)


def digest(xml: str) -> str:
    return hashlib.sha256(xml.encode("utf-8")).hexdigest()


def compress(xml: str) -> bytes:
    return zlib.compress(xml.encode("utf-8"), 6)


def decompress(blob: bytes) -> str:
    return zlib.decompress(blob).decode("utf-8")


def check_size(xml: str) -> int:
    size = len(xml.encode("utf-8"))
    if size > MAX_DIAGRAM_BYTES:
        raise DiagramTooLarge(size)
    return size


def should_version(diagram: Diagram, db: Session, now: datetime | None = None) -> bool:
    """True when enough has happened since the last version to keep one."""
    now = now or utcnow()
    last = (
        db.query(func.max(DiagramVersion.created_at))
        .filter(DiagramVersion.diagram_id == diagram.id)
        .scalar()
    )
    return last is None or (now - last) >= VERSION_DEBOUNCE


def snapshot(
    db: Session,
    diagram: Diagram,
    xml: str,
    *,
    author_label: str | None,
    author_user_id: int | None = None,
    origin: str = "owner",
    share_link_id: int | None = None,
    orphan: bool = False,
    orphan_reason: str | None = None,
    note: str | None = None,
) -> DiagramVersion | None:
    """Keep this XML as a version. Returns None when it is a duplicate.

    Duplicates are not an error and not worth a log line: with autosave running,
    identical content arrives constantly, and the unique constraint on
    (diagram_id, sha256) is the whole point.
    """
    sha = digest(xml)
    diagram.version_no = (diagram.version_no or 0) + 1
    version = DiagramVersion(
        diagram_id=diagram.id,
        version_no=diagram.version_no,
        sha256=sha,
        xml_z=compress(xml),
        size_bytes=len(xml.encode("utf-8")),
        author_label=author_label,
        author_user_id=author_user_id,
        origin=origin,
        share_link_id=share_link_id,
        orphan=orphan,
        orphan_reason=orphan_reason,
        note=note,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        diagram.version_no = (diagram.version_no or 1) - 1
        return None
    return version


# --- retention ---------------------------------------------------------------

KEEP_ALL = timedelta(hours=24)
KEEP_HOURLY_FOR = timedelta(days=7)


def thin(db: Session, diagram_id: int, now: datetime | None = None) -> int:
    """Drop versions the retention policy no longer wants. Returns how many.

    Everything from the last 24 hours, then one per hour for a week, then one
    per day. Pinned versions are never touched, and neither are orphans: an
    orphan is the record of a conflict somebody may still need to resolve.

    Note for whoever runs this: SQLite does not return the space on its own.
    Thinning without a periodic VACUUM is a policy that exists on paper.
    """
    now = now or utcnow()
    rows = (
        db.query(DiagramVersion)
        .filter(
            DiagramVersion.diagram_id == diagram_id,
            DiagramVersion.pinned.is_(False),
            DiagramVersion.orphan.is_(False),
        )
        .order_by(DiagramVersion.created_at.desc())
        .all()
    )

    seen_buckets: set[tuple] = set()
    removed = 0
    for row in rows:
        age = now - row.created_at
        if age <= KEEP_ALL:
            continue
        if age <= KEEP_HOURLY_FOR:
            bucket = ("h", row.created_at.strftime("%Y-%m-%d-%H"))
        else:
            bucket = ("d", row.created_at.strftime("%Y-%m-%d"))
        # Rows arrive newest first, so the first one in a bucket is the one kept.
        if bucket in seen_buckets:
            db.delete(row)
            removed += 1
        else:
            seen_buckets.add(bucket)
    return removed
