# CLAUDE.md — draw

*Instructions for anyone working on this repository with Claude Code.*

## Before touching authentication, routes, Caddy, MCP, the look or the languages

**Read the borant tool conventions before writing, not after.** They are written
out in full on a single page (in Italian), reachable two ways:

- if you have the `Ono3` repository at hand:
  `wiki/projects/strumenti/convenzioni-tool-borant.md`
- otherwise, from any machine: the **`onopedia`** MCP,
  `get_page("convenzioni-tool-borant")`

The operational version with the code sits in `borant-id/SPEC.md` §20, which is
**gitignored**: it exists only on the disk of whoever has that clone.

The sections that apply to this repository are authentication (`local` is the
default, the key is the `subject` and never the email), **public paths** — the
delicate part here, because the guest surface includes a `POST` that saves — the
showcase and home rule (`/` is a showcase that never looks at who is reading it,
the app lives at `/app`, gated), failing closed instead of bouncing to the login,
the look and the languages.

**Do not copy the conventions in here.** Two copies diverge, and the wrong one is
always the nearer.

## The thing specific to this repository

> **Under `/s/` no method ever looks at `X-Borant-*`, by construction.**

The guest surface is authorised by the token and never by an identity. The day a
route in there needs to know *who* is asking, that route does not belong under
`/s/`: it moves under the gated prefix, and it is not carved out by method. The
reasoning is in `SPEC.md` §5.

## The three sources in this repository

- `README.md` — how to use it
- `DEPLOY.md` — the server, without addresses, users or key paths
- `SPEC.md` — the why. **Gitignored**, because it holds the failure-mode analysis
  and the discarded decisions. If you do not have it, ask: it does not arrive
  with a `git pull`.

## The Caddy block is not written by hand

It is generated: `python caddy.py --gated` reads `PUBLIC_PATHS` from the server
module. The list of public paths lives in exactly one place, so whoever adds a
public route notices while writing it. After touching routes, regenerate and diff
against what is running in production.

## The editor is not to be touched

`jgraph/drawio` runs in a container next door, served under `/editor/*`, with a
**pinned** tag. Not one line of the editor is modified: that is the decision that
makes an upgrade a tag change instead of a merge. If a request seems to require
modifying the editor, it is a level-3 request (see `SPEC.md` §11) and it gets
discussed first, not implemented.

## Language

Code, comments and documentation in this repository are in **English**. The user
interface is translated, and the strings live in `locales.py` — that is the only
place other languages belong. A string written straight into a template is a
defect even when it happens to be in the right language.
