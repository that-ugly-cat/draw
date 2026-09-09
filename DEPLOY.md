# Deploy

Two containers either way: the app (port **8023**) and unmodified draw.io (port
**8024**, bound to `127.0.0.1` only). A reverse proxy on the host reaches both.

The app runs in **two modes**, and neither is a degraded version of the other:

| | `AUTH_MODE=local` | `AUTH_MODE=gateway` |
|---|---|---|
| who authenticates | the app, email + password | an identity gate in front of it |
| sessions | a cookie this app signs | the gate's, and not ours to end |
| accounts created by | `seed.py --user` | on first arrival, from the gate's headers |
| reverse proxy config | `python caddy.py` | `python caddy.py --gated` |
| needs anything else running | no | the gate |

`local` is the **default in the code**, and that is deliberate: an app that
believes identity headers with nothing in front of it hands identity to anyone
who can send a header. The gateway path stays dead code until someone turns it
on, and even then the request has to arrive from the expected proxy.

It also means `local` is the way back in when the gate is down — a restart with
the variable changed, not an emergency procedure.

Addresses, users and key paths are not in here: they live in the private notes
for the server.

---

## Standalone

### `.env`

```
JWT_SECRET=<long random string>
AUTH_MODE=local
EDITOR_URL=/editor/
DATA_DIR=/app/data
```

`BORANT_TRUSTED_PROXY` and `GATE_LOGOUT_URL` are not read in this mode and can be
left out.

### First run

```bash
docker compose up -d --build
docker exec draw python seed.py --user you@example.org --pw '<password>'
curl -s localhost:8023/healthz
```

There is no self-registration: accounts are made with `seed.py`. Run it again per
person.

### Reverse proxy

```bash
python caddy.py            # no --gated
```

The generated block proxies everything to the app, plus the `/editor/*` branch
that goes straight to the editor container. Nothing is gated, and the app signs
people in at `/login`.

---

## Behind an identity gate

### `.env`

```
JWT_SECRET=<long random string>
AUTH_MODE=gateway
BORANT_TRUSTED_PROXY=<proxy gateway>,<any other networks>
GATE_LOGOUT_URL=https://<gate host>/logout
EDITOR_URL=/editor/
DATA_DIR=/app/data
```

`GATE_LOGOUT_URL` is optional and it is a URL rather than a hardwired constant on
purpose: this app must keep working with no gate anywhere in sight. Leave it out
and the app simply stops offering a sign-out it cannot perform, which is better
than a button that clears nothing while the gate cookie stays alive.

Profiles appear on first arrival, keyed on the gate's **subject** and never on
the email — an email changes when somebody changes institution, and whoever keyed
on it writes themselves a migration.

### `BORANT_TRUSTED_PROXY` takes a list, and it has to

Docker picks between the gateways of a container's networks in **alphabetical
order of network name**. Adding a network moves the address the proxy appears to
come from, and a moved gateway switches off the login without saying why. It
happened to a sibling app on 8 September 2026, in the minute a new network
arrived.

So: **when you add a network to this container, you widen the list.** And the
check is not "the app answers 200" — a gated page answers 302 both because you
are not signed in and because the app threw your identity away. Test with a
**real session** and read the app log, where the refusal has a line that names
itself.

A useful audit compares, for every app, the gateways declared in the variable
against those of the networks the container is actually attached to. Print the
networks found next to the verdict: a check that fails to *collect* the data
otherwise reports success for everything.

### Reverse proxy

```bash
python caddy.py --gated
```

Both variants read `PUBLIC_PATHS` from the code, so the list of public paths
lives in exactly one place and whoever adds a public route notices while writing
it. After touching routes, regenerate and diff against what is running.

Note the shape: `/editor/*` has a `handle_path` of its own that goes straight to
the editor container and passes through neither the gate nor the app. It carries
a `rewrite * /draw{uri}`, and that is not decoration — the `jgraph/drawio` image
is Tomcat and deploys its war under `/draw/`, so proxying the stripped path
answers 404 for everything including the assets.

`/s/*` is public in both modes. Everything under it is authorised by a share
token and no handler there ever looks at an identity, which is what lets a `POST`
that saves live on a public branch.

---

## Where the code comes from

A clone of `github.com/that-ugly-cat/draw` in the deploy directory. To update:

```bash
git pull && docker compose up -d --build
```

Two files do **not** arrive with the pull and live only on the server: the
`.env`, and `SPEC.md`, which is gitignored because it holds the failure-mode
analysis. Whoever clones from scratch does not have the second one and has no
way of noticing.

If after a pull `git status` reports `caddy.py`, `seed.py` or `dev-run.py` as
modified with no differing lines, those are permission bits: `git config
core.fileMode false` and it stops.

## Behind a CDN

- Turn off any HTML email-address obfuscation for this host: it rewrites
  addresses in the markup and injects a third-party script, which inside a page
  hosting an iframe is one more thing to rule out when something misbehaves.
- Static assets already carry a fingerprint in the URL (`?v=`), because such
  zones cache them for hours.

## Health

`/healthz` sits outside the gate in both modes and stays green **even when the
gate is dead and nobody can get in any more**: a useful check also points at a
gated route.

## Maintenance

Thinning the version history does not return the disk space on its own. After a
prune, or periodically:

```bash
docker exec draw python -c "from draw.server.models import engine; engine.raw_connection().execute('VACUUM')"
```

Backups: the database is in `data/`, mounted as a volume. It is the only thing to
back up — there are no diagram files beside it, by design.
