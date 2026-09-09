"""
Schema and session handling.

Two things here are decisions rather than mechanics, and both are explained
where they sit: the lock lives on the diagram row (not in a table of its own),
and the current XML lives in a different column from its history (not in the
same table as the versions). SPEC.md §3 and §7 carry the reasoning; the short
version is that the first makes "take the lock and write" one transaction, and
the second stops autosave from multiplying megabyte documents.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

DATA_DIR = os.environ.get("DATA_DIR", "data")
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "draw.db"))

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """WAL, and it is not optional here.

    ArguMap says in its own header that it does not enable WAL, and it gets away
    with it because it has a single writer. This app has autosave from the owner
    and guests writing through share links at the same time; without WAL a read
    blocks a write and the editor stalls mid-session.
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    # The key is the subject and never the email: an email changes when someone
    # changes institution, and whoever keyed on it writes themselves a migration.
    borant_sub = Column(String, unique=True, nullable=True, index=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # foreign_keys is required, not decorative: `diagrams` has two paths back to
    # this table — the owner and whoever currently holds the lock — and without
    # naming one SQLAlchemy refuses to guess.
    diagrams = relationship(
        "Diagram", back_populates="owner", foreign_keys="Diagram.owner_id"
    )

    @property
    def label(self) -> str:
        return self.name or self.email


class Diagram(Base):
    __tablename__ = "diagrams"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False, default="Untitled")

    # The current state, uncompressed. Overwritten by every autosave, which is
    # why it is a column and not a row in the history: see storage.py.
    #
    # Uncompressed is the canonical form on purpose. Plain XML is greppable
    # (finding every diagram containing a word is a query), diffable, and shows
    # the cell ids a future page/cell merge would need. draw.io's own
    # deflate+base64 payload has to be inflated before anything can be done with
    # it anyway, and storing it that way buys nothing but loses search.
    xml = Column(Text, nullable=False, default="")
    size_bytes = Column(Integer, nullable=False, default=0)
    thumb_png = Column(LargeBinary, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)
    updated_by_label = Column(String, nullable=True)
    version_no = Column(Integer, nullable=False, default=0)

    # Bumped on **every** write to `xml`, which `version_no` is not: a version
    # row is only cut on the debounce, so it cannot answer "has the document
    # moved since I last saw it". That question is asked by every open editor
    # on every lock refresh, and the answer decides whether it reloads.
    revision = Column(Integer, nullable=False, default=0)

    # --- the soft lock (SPEC.md §4) ---
    #
    # Keyed on a session and not on a user, deliberately: the same person in two
    # tabs is two holders and sees the conflict, which is the case that happens
    # most often of all.
    lock_session = Column(String, nullable=True)
    lock_label = Column(String, nullable=True)
    lock_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    lock_expires_at = Column(DateTime, nullable=True)

    # Bin rather than immediate deletion: one click should not be final.
    deleted_at = Column(DateTime, nullable=True, index=True)

    owner = relationship("User", back_populates="diagrams", foreign_keys=[owner_id])
    versions = relationship(
        "DiagramVersion", back_populates="diagram", cascade="all, delete-orphan"
    )
    share_links = relationship(
        "ShareLink", back_populates="diagram", cascade="all, delete-orphan"
    )


class DiagramVersion(Base):
    __tablename__ = "diagram_versions"
    __table_args__ = (
        # With autosave many saves are byte-identical (a click, an undo back to
        # the same state). Keying on the content hash makes a no-op cost zero
        # rows instead of one more copy of a megabyte document.
        UniqueConstraint("diagram_id", "sha256", name="uq_version_content"),
    )

    id = Column(Integer, primary_key=True)
    diagram_id = Column(
        Integer, ForeignKey("diagrams.id"), nullable=False, index=True
    )
    version_no = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False)
    xml_z = Column(LargeBinary, nullable=False)  # zlib, at rest only
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    author_label = Column(String, nullable=True)
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    origin = Column(String, nullable=False, default="owner")  # owner | share
    share_link_id = Column(Integer, ForeignKey("share_links.id"), nullable=True)

    pinned = Column(Boolean, default=False, nullable=False)
    note = Column(String, nullable=True)

    # A save that arrived without a valid lock. It is never thrown away; it is
    # parked here with the reason written down, and the client is told which
    # version number it became. This rule, not the lock, is what makes level 1
    # safe: the worst case is a merge by hand, never an hour lost.
    orphan = Column(Boolean, default=False, nullable=False)
    orphan_reason = Column(String, nullable=True)

    diagram = relationship("Diagram", back_populates="versions")


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True)
    diagram_id = Column(
        Integer, ForeignKey("diagrams.id"), nullable=False, index=True
    )
    token = Column(String, unique=True, nullable=False, index=True)
    mode = Column(String, nullable=False)  # ro | rw
    label = Column(String, nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    # The field that makes managing links real instead of nominal. Without it,
    # six months in there is a list of links and no way to tell which are still
    # in use, so nobody revokes any of them.
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, nullable=False, default=0)

    diagram = relationship("Diagram", back_populates="share_links")

    def is_live(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return True


class ApiKey(Base):
    """An MCP key carries an identity, not a capability.

    Every call runs as its owner and goes through the same access checks as the
    web, so it reaches exactly what that person reaches. `last_used_at` earns
    its keep in one place, but a useful one: telling a live key from a forgotten
    one when deciding what to revoke.
    """

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, default="", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User")

    def is_live(self) -> bool:
        return self.revoked_at is None


def _add_missing_columns() -> None:
    """Idempotent column adds, because create_all does not alter tables.

    Small on purpose: a real migration tool for one app with a handful of
    columns is more machinery than the problem. What matters is that a deploy
    onto an existing database does not need anybody to remember an ALTER by
    hand — that is the step that gets skipped, at night, on the live one.
    """
    wanted = {"diagrams": {"revision": "INTEGER NOT NULL DEFAULT 0"}}
    with engine.begin() as conn:
        for table, columns in wanted.items():
            have = {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if not have:
                continue  # table not created yet; create_all will do it whole
            for name, ddl in columns.items():
                if name not in have:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    Base.metadata.create_all(engine)
    _add_missing_columns()
