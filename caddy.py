#!/usr/bin/env python3
"""
Print the Caddy site block for draw, from the paths declared in the code.

Generated rather than written, for the reason the house convention gives: the
list of public paths lives in exactly one place, so the day somebody adds a
public route they notice while writing it instead of six months later. After
touching routes, regenerate and diff against what is running.

    python caddy.py           # local mode: the app signs people in itself
    python caddy.py --gated   # behind Borant ID

Two upstreams here, which is the one thing this generator does that catena's
does not: /editor/* goes straight to the drawio container and never through the
app. The editor is static and heavy, and proxying megabytes of JavaScript
through Starlette to add nothing would be work in exchange for latency.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from draw.server.main import PUBLIC_PATHS  # noqa: E402

HOST = os.environ.get("PUBLIC_HOST", "draw.borant.eu")
PORT = os.environ.get("PORT", "8023")
EDITOR_PORT = os.environ.get("EDITOR_PORT", "8024")

# /editor/* is public in both modes and is matched *before* everything else, so
# it never picks up the gate and never reaches the app.
#
# The rewrite is not decoration. The jgraph/drawio image is Tomcat, and Tomcat
# deploys the war under its own name: the app lives at /draw/ inside the
# container, not at the root, so proxying a stripped path straight through
# answers 404 for everything including the assets. handle_path removes /editor,
# the rewrite puts /draw back, and the browser keeps /editor/ as its base so the
# editor's own relative URLs resolve.
EDITOR = """    handle_path /editor/* {{
        rewrite * /draw{{uri}}
        reverse_proxy localhost:{editor_port}
    }}
"""

PLAIN = """{host} {{
{editor}    reverse_proxy localhost:{port}
}}
"""

GATED = """{host} {{
{editor}    @public path {paths}
    handle @public {{
        import noforge
        import nocookie
        reverse_proxy localhost:{port}
    }}
    handle {{
        import borantid
        reverse_proxy localhost:{port}
    }}
}}
"""


def main() -> int:
    gated = "--gated" in sys.argv
    template = GATED if gated else PLAIN
    # /editor/* has its own handle_path above, so it does not belong in the
    # matcher list as well; everything else public does.
    paths = [p for p in PUBLIC_PATHS if not p.startswith("/editor")]
    print(
        template.format(
            host=HOST,
            port=PORT,
            editor=EDITOR.format(editor_port=EDITOR_PORT),
            paths=" ".join(paths),
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
