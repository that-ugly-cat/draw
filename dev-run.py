#!/usr/bin/env python3
"""
Run the app locally, in `local` auth mode, against a throwaway database.

The environment is set here rather than in a launch config so that starting it
is one command on any machine, and so that nobody has to remember that
JWT_SECRET is required before the first import.

EDITOR_URL points at a drawio container if one is up (`docker compose up -d
editor`); without it the editor frame stays empty and everything else — the
workspace, the share links, the lock, the versions — still works.
"""

import os
import sys

os.environ.setdefault("JWT_SECRET", "dev-only-not-a-secret")
os.environ.setdefault("AUTH_MODE", "local")
os.environ.setdefault("DB_PATH", os.path.join("draw", "data", "dev.db"))
os.environ.setdefault("EDITOR_URL", "http://localhost:8024/")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("draw.server.main:app", host="127.0.0.1", port=8023, reload=False)
