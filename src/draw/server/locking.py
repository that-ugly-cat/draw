"""
The soft lock — level 1 concurrency (SPEC.md §4).

What this does is reduce how often two people collide. What makes a collision
harmless is somewhere else: the rule in storage/main that a save arriving
without a valid lock is parked as an orphan version instead of being refused
into the void. If one of the two had to go, it would be this file.

The lock is keyed on a *session*, not a user. The same person in two tabs is two
holders and sees the conflict, which is the case that happens most often.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import Diagram, utcnow

# Short on purpose. With autosave refreshing every 30s this covers anyone who is
# actually working, and it frees a diagram a minute and a half after somebody
# shuts a laptop. A long TTL produces diagrams locked by forgotten tabs, which
# is how soft locks become hated.
LOCK_TTL = timedelta(seconds=90)
REFRESH_EVERY = timedelta(seconds=30)


def new_session_id() -> str:
    return secrets.token_urlsafe(16)


@dataclass
class LockState:
    held: bool            # by the caller's own session
    held_by_other: bool   # by any other session
    by_other_user: bool   # ...and that session belongs to a different person
    label: str | None
    since: datetime | None
    expires_at: datetime | None

    @property
    def free(self) -> bool:
        return not self.held and not self.held_by_other


def _expired(diagram: Diagram, now: datetime) -> bool:
    return diagram.lock_expires_at is None or diagram.lock_expires_at <= now


def inspect(
    diagram: Diagram,
    session_id: str | None,
    user_id: int | None = None,
    now: datetime | None = None,
) -> LockState:
    """Who holds it, and — the distinction that matters — whether they are you.

    A lock held by another session of the *same person* is not a conflict: you
    in a browser tab and you through a script are one intent, and refusing one
    of them produces an orphan version somebody then has to go and find.

    Two guests are a different matter, and it is the case a naive comparison
    gets wrong: both carry a null `lock_user_id`, so "equal ids" would call them
    the same person. Sameness therefore requires **both** sides to be a known
    user, which also makes guest-versus-owner a conflict, as it should be.
    """
    now = now or utcnow()
    if not diagram.lock_session or _expired(diagram, now):
        return LockState(False, False, False, None, None, None)
    mine = session_id is not None and diagram.lock_session == session_id
    same_person = user_id is not None and diagram.lock_user_id == user_id
    return LockState(
        held=mine,
        held_by_other=not mine,
        by_other_user=(not mine) and not same_person,
        label=diagram.lock_label,
        since=(diagram.lock_expires_at - LOCK_TTL) if diagram.lock_expires_at else None,
        expires_at=diagram.lock_expires_at,
    )


def acquire(
    db: Session,
    diagram: Diagram,
    session_id: str,
    label: str,
    user_id: int | None = None,
    *,
    steal: bool = False,
    now: datetime | None = None,
) -> LockState:
    """Take or refresh the lock. `steal` is the explicit takeover.

    Refusing is not an error condition the caller has to handle specially: the
    returned state says who holds it, and the UI turns that into a read-only
    view with a button. Nothing about a refusal blocks editing, only saving
    under a held lock — and even that is survivable (see main.save).
    """
    now = now or utcnow()
    state = inspect(diagram, session_id, user_id, now)

    if state.held_by_other and not steal:
        return state

    diagram.lock_session = session_id
    diagram.lock_label = label
    diagram.lock_user_id = user_id
    diagram.lock_expires_at = now + LOCK_TTL
    db.flush()
    return inspect(diagram, session_id, user_id, now)


def release(db: Session, diagram: Diagram, session_id: str) -> None:
    """Give it back, if it is ours. Silent when it is not.

    Silence is right: the common way to reach this is a browser closing after a
    takeover already happened, and there is nobody left to tell.
    """
    if diagram.lock_session == session_id:
        diagram.lock_session = None
        diagram.lock_label = None
        diagram.lock_user_id = None
        diagram.lock_expires_at = None
        db.flush()


def touch_if_ours(
    db: Session,
    diagram: Diagram,
    session_id: str,
    label: str,
    user_id: int | None,
    now: datetime | None = None,
) -> None:
    """Refresh the lock only when it is free or already this session's.

    The non-stealing counterpart of `acquire`, and the one a background writer
    wants. A script that saves must not end up **holding** a ninety-second lock
    on a document its owner has open in a browser: it would answer a write by
    blocking the person who asked for it.
    """
    now = now or utcnow()
    state = inspect(diagram, session_id, user_id, now)
    if state.held_by_other:
        return
    diagram.lock_session = session_id
    diagram.lock_label = label
    diagram.lock_user_id = user_id
    diagram.lock_expires_at = now + LOCK_TTL
    db.flush()


def holds(diagram: Diagram, session_id: str | None, now: datetime | None = None) -> bool:
    return inspect(diagram, session_id, None, now).held
