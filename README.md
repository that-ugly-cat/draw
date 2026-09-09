# draw

draw.io diagrams with a workspace behind them: one per account, with version
history and share links you create per diagram.

The app owns the diagrams; the editor is **unmodified draw.io**, served from a
container next door and embedded in an iframe through its embed protocol. XML
goes in, XML comes out, and everything that decides anything — who holds the
lock, what becomes a version, what happens to a save that arrives late — lives
in the server.

## Using it

Every diagram belongs to a person. From the workspace you create, open, rename
and bin them; the bin holds for 30 days.

**Sharing.** Each diagram takes any number of links, read-only or read-write,
each with a label, an optional expiry and a revoke button. The table shows
**last used**: that is the field you need in order to decide what to revoke.
Someone arriving through a read-write link is asked for a name, which is **a
label and not an identity** — it shows who is working and attributes versions,
and it authorises nothing. The token authorises.

**Working in parallel.** Opening a diagram takes a soft lock of 90 seconds,
refreshed by autosave. Whoever finds it held sees by whom, and can take it over
with an explicit action. The rule that matters is a different one: **a save
without a valid lock is never thrown away** — it becomes a version marked as an
orphan, with the reason written down, and whoever saved is told which version
number it became. The worst case is a merge by hand.

**Versions.** The current document is overwritten on every autosave; versions
are created after five minutes of activity, on close, and on every orphan save.
They can be pinned, and pinned ones are never thinned out. Each version
downloads as a `.drawio` file.

**Limit: 10 MB per diagram.** What usually trips it is a pasted image, which
draw.io embeds as a data URI. The save is refused but the document stays open in
the editor: nothing is lost.

## Two modes

The app authenticates either way and neither mode is a degraded version of the
other. In `AUTH_MODE=local` it signs people in itself against its own users
table, and accounts are created with `seed.py`. In `AUTH_MODE=gateway` it trusts
an identity gate in front of it, profiles appear on first arrival, and the
session belongs to the gate rather than to the app — so sign-out is only offered
when a gate logout endpoint is configured.

`local` is the default in the code, for security before portability: an app that
believes identity headers with nothing in front of it hands identity to anyone
who can send a header. `DEPLOY.md` covers both.

## Development

```bash
pip install -e ".[dev]"
JWT_SECRET=dev AUTH_MODE=local python seed.py --user me@example.org --pw secret
JWT_SECRET=dev AUTH_MODE=local uvicorn draw.server.main:app --reload --port 8023
```

Locally the editor can point at a drawio container (`docker compose up editor`)
by setting `EDITOR_URL=http://localhost:8024/`.

The Caddy block is **not written by hand**: `python caddy.py --gated` generates
it by reading `PUBLIC_PATHS` in `src/draw/server/main.py`.

## Personal data

A deletion request arrives sooner or later, and deleting upstream in the
identity provider does not delete here. The tables to look at:

| table | what it holds |
|---|---|
| `users` | name, email address, gate subject |
| `diagrams` | title, `updated_by_label`, `lock_label` (names, guests included) |
| `diagram_versions` | `author_label` and `author_user_id` |
| `share_links` | `label`, and who created the link |

Diagram content is written by users and can contain anything.
