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
import threading
import urllib.parse
import zlib
from datetime import datetime, timedelta

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Diagram, DiagramVersion, engine, utcnow

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
#
# The policy was written down in three places — SPEC.md §7, the README, the copy
# on the showcase — and had no caller anywhere: `thin` existed and nothing ran
# it, and `deleted_at` was only ever set and cleared, so the bin that says it
# holds for thirty days held for ever. `sweep` is the pass that makes those
# sentences true, and `main.lifespan` is what runs it.

KEEP_ALL = timedelta(hours=24)
KEEP_HOURLY_FOR = timedelta(days=7)

# What the bin promises, in README, in `mcp_app.delete_diagram`'s own docstring
# and in SPEC.md §3. The number lives here now, so a change moves one constant
# rather than three sentences.
BIN_KEEP = timedelta(days=30)

# Nightly, as SPEC.md §7 asks, and once shortly after startup so a pass happens
# on a box that gets restarted more often than it stays up for a day. The
# granularity is a day because the policy's own is: everything for 24 hours,
# then one an hour, then one a day.
SWEEP_EVERY = timedelta(hours=24)
FIRST_SWEEP_AFTER = timedelta(minutes=2)

# One pass at a time in this process. Two at once is not corruption — the
# deletes are the outcome both of them want — but it is wasted work, and the
# guard is two lines.
_SWEEP_LOCK = threading.Lock()


def thin(db: Session, diagram_id: int, now: datetime | None = None) -> int:
    """Drop versions the retention policy no longer wants. Returns how many.

    Everything from the last 24 hours, then one per hour for a week, then one
    per day. Pinned versions are never touched, and neither are orphans: an
    orphan is the record of a conflict somebody may still need to resolve.

    One diagram at a time, and it does not commit: `sweep` is the caller that
    walks the whole table and decides the transaction boundaries.
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


def purge_bin(db: Session, now: datetime | None = None) -> int:
    """Delete the diagrams binned longer than `BIN_KEEP`. Returns how many.

    The bin was documented as a grace period and implemented as an archive:
    `deleted_at` was set by the delete route and cleared by restore, and nothing
    ever looked at it again. Deleting the diagram row takes its versions, its
    share links and its thumbnail with it, because those relationships cascade —
    which is the point. A purge that emptied the list and left the content
    behind would keep the promise on the page and break it in the database.

    Restoring is the escape hatch and it stays open for the whole window: what
    is deleted here has been in the bin for a month.
    """
    cutoff = (now or utcnow()) - BIN_KEEP
    rows = (
        db.query(Diagram)
        .filter(Diagram.deleted_at.isnot(None), Diagram.deleted_at <= cutoff)
        .all()
    )
    for row in rows:
        log.info("purging diagram %s, binned %s", row.id, row.deleted_at)
        db.delete(row)
    return len(rows)


def sweep(db: Session, now: datetime | None = None) -> dict:
    """One retention pass: thin every history, then purge the bin.

    Called from a background task in the app's lifespan and never from a
    handler. That is not fastidiousness: thinning walks every version row of
    every diagram, and a save that waited for it would be a save somebody feels.

    Committed diagram by diagram, so a failure on one costs that one and not the
    whole pass, and so a long pass does not hold a single write transaction open
    for its duration. A row a concurrent pass already deleted is not an error
    worth stopping for.

    The pass also returns the freed pages to the filesystem, incrementally: see
    `reclaim` for why it is that and not a `VACUUM`.
    """
    if not _SWEEP_LOCK.acquire(blocking=False):
        log.info("retention: a pass is already running, skipping this one")
        return {"diagrams": 0, "thinned": 0, "purged": 0, "skipped": True}
    try:
        now = now or utcnow()
        ids = [row[0] for row in db.query(Diagram.id).all()]
        thinned = 0
        for diagram_id in ids:
            try:
                thinned += thin(db, diagram_id, now)
                db.commit()
            except Exception:
                db.rollback()
                log.exception("retention: thinning diagram %s failed", diagram_id)
        try:
            purged = purge_bin(db, now)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("retention: purging the bin failed")
            purged = 0
        freed = reclaim(db)
        return {"diagrams": len(ids), "thinned": thinned, "purged": purged,
                "freed_pages": freed, "skipped": False}
    finally:
        _SWEEP_LOCK.release()


# How many free pages to hand back per pass. Incremental vacuum moves the pages
# it is asked for and stops, so the number is a budget for how long the database
# is busy: 2000 pages is 8 MB at the 4 KB page size, more than a day of thinning
# will ever free here, and small enough to be uninteresting if it ever is not.
RECLAIM_PAGES = 2000


def enable_incremental_vacuum() -> bool:
    """Switch the database to incremental auto-vacuum, once, at startup.

    SQLite never gives space back on its own: deleted rows leave free pages on a
    freelist inside the file, reused by later writes. That is a ceiling, not a
    leak — but a review that bins a large diagram keeps the file at its high
    water mark for ever.

    `auto_vacuum` lives in the file header, so switching it on an existing
    database takes one full `VACUUM` — which rebuilds the file under an
    exclusive lock. That is the reason to do it now and not later: the cost
    scales with the file, and this one is under a megabyte. After it, each pass
    hands pages back with `PRAGMA incremental_vacuum`, which moves a bounded
    number of them and takes no exclusive rebuild.

    Returns True when it did the switch. A failure is logged and swallowed: a
    disk too full for the rebuild is a reason to keep serving, not to refuse to
    start.
    """
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        mode = conn.execute(text("PRAGMA auto_vacuum")).scalar()
        if mode == 2:
            return False
        try:
            conn.execute(text("PRAGMA auto_vacuum=INCREMENTAL"))
            conn.execute(text("VACUUM"))  # cannot run inside a transaction
        except Exception:
            log.exception("retention: could not switch on incremental auto-vacuum")
            return False
        now_mode = conn.execute(text("PRAGMA auto_vacuum")).scalar()
        log.info("retention: incremental auto-vacuum on (auto_vacuum=%s)", now_mode)
        return now_mode == 2


def reclaim(db: Session) -> int:
    """Hand free pages back to the filesystem. Returns how many were freed.

    Zero is the ordinary answer: it means the file had no slack, not that
    something failed. Zero is also what comes back if the one-time switch never
    happened, because without incremental auto-vacuum the pragma is a no-op —
    and that is the honest failure mode, since the alternative would be a full
    VACUUM under an exclusive lock decided by a background task nobody watched.
    """
    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            # Through the driver's own cursor, and stepped to the end. Both
            # halves are load-bearing, and both were measured rather than
            # assumed: incremental_vacuum does its work as the statement is
            # stepped, and it returns no rows — so SQLAlchemy closes the result
            # before stepping it and the pragma frees exactly one page (1 of
            # 3000 in the probe), while execute + fetchall on the sqlite3
            # cursor frees the number asked for.
            raw = conn.connection.dbapi_connection
            cur = raw.cursor()
            try:
                before = cur.execute("PRAGMA freelist_count").fetchone()[0] or 0
                if not before:
                    return 0
                cur.execute(f"PRAGMA incremental_vacuum({RECLAIM_PAGES})")
                cur.fetchall()
                after = cur.execute("PRAGMA freelist_count").fetchone()[0] or 0
            finally:
                cur.close()
        return max(0, before - after)
    except Exception:
        log.exception("retention: reclaiming free pages failed")
        return 0
