# Deploy

Two containers: the app (port **8023**) and unmodified draw.io (port **8024**,
bound to `127.0.0.1` only). Caddy runs on the host and reaches both.

Addresses, users and key paths are not in here: they live in the private notes
for the server.

## `.env`

```
JWT_SECRET=<long random string>
AUTH_MODE=gateway
BORANT_TRUSTED_PROXY=<docker network gateway>,<any other networks>
EDITOR_URL=/editor/
DATA_DIR=/app/data
```

`AUTH_MODE=local` is the code's own default and it is the way back in when the
gate is down: a restart with the variable changed, not an emergency procedure.

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

## `BORANT_TRUSTED_PROXY` takes a list, and it has to

Docker picks between the gateways of a container's networks in **alphabetical
order of network name**. Adding a network moves the address the proxy appears to
come from, and a moved gateway switches off the login without saying why. It
happened to another app on 8 September 2026, in the minute a new network
arrived.

So: **when you add a network to this container, you widen the list.** And the
check is not "the app answers 200" — a gated page answers 302 both because you
are not signed in and because the app threw your identity away. Test with a
**real session** and read the app log, where the refusal has a line that names
itself.

## Caddy

The site block is **generated**, not written:

```bash
python caddy.py --gated
```

It reads `PUBLIC_PATHS` from the code. After touching routes, regenerate and
diff against what is running.

Note the shape: `/editor/*` has a `handle_path` of its own that goes straight to
the editor container and passes through neither the gate nor the app. It carries
a `rewrite * /draw{uri}`, and that is not decoration: the `jgraph/drawio` image
is Tomcat and deploys its war under `/draw/`, so proxying the stripped path
answers 404 for everything including the assets.

## Behind a CDN

- Turn off any HTML email-address obfuscation for this host: it rewrites
  addresses in the markup and injects a third-party script, which inside a page
  hosting an iframe is one more thing to rule out when something misbehaves.
- Static assets already carry a fingerprint in the URL (`?v=`), because the zone
  caches them for hours.

## First run

```bash
docker compose up -d --build
docker exec draw python seed.py
curl -s localhost:8023/healthz
```

`/healthz` sits outside the gate and stays green **even when the gate is dead
and nobody can get in any more**: a useful check also points at a gated route.

## Maintenance

Thinning the version history does not return the disk space on its own. After a
prune, or periodically:

```bash
docker exec draw python -c "from draw.server.models import engine; engine.raw_connection().execute('VACUUM')"
```

Backups: the database is in `data/`, mounted as a volume. It is the only thing
to back up — there are no diagram files beside it, by design.
