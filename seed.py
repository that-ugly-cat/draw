#!/usr/bin/env python3
"""
Create the schema, and a local account when there is none.

Reached with `docker exec` from DEPLOY.md, which is why it lives inside the
image: it is needed exactly when something has gone wrong and nobody wants to be
copying files onto a server.

    python seed.py                       # schema only
    python seed.py --user me@x.eu --pw s # schema + a local account

The account is for `AUTH_MODE=local`, which stays a working way back in when the
gate is down. In gateway mode profiles appear on first arrival and this is not
needed.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from draw.server.auth import hash_password  # noqa: E402
from draw.server.models import SessionLocal, User, init_db  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--pw")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    init_db()
    print("schema ok")

    if not args.user:
        return 0
    if not args.pw:
        print("--user needs --pw", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        email = args.user.strip().lower()
        if db.query(User).filter(User.email == email).first():
            print(f"{email} already exists")
            return 0
        db.add(
            User(
                email=email,
                name=args.name or email,
                password_hash=hash_password(args.pw),
                is_active=True,
            )
        )
        db.commit()
        print(f"created {email}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
