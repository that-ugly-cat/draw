# Deploy

Due container: l'app (porta **8023**) e draw.io non modificato (porta **8024**,
solo su `127.0.0.1`). Caddy sta sull'host e li raggiunge entrambi.

Indirizzi, utenti e percorsi delle chiavi non stanno qui: stanno nella pagina
privata del VPS.

## `.env`

```
JWT_SECRET=<stringa lunga e casuale>
AUTH_MODE=gateway
BORANT_TRUSTED_PROXY=<gateway della rete docker>,<altre reti>
EDITOR_URL=/editor/
DATA_DIR=/app/data
```

`AUTH_MODE=local` è il default del codice ed è il ritorno indietro quando il gate
è giù: un riavvio con la variabile cambiata, non una procedura d'emergenza.

## `BORANT_TRUSTED_PROXY` accetta una lista, e deve

Docker sceglie fra i gateway delle reti di un container in **ordine alfabetico di
nome di rete**. Aggiungere una rete sposta l'indirizzo da cui il proxy sembra
arrivare, e un gateway spostato spegne il login senza dire perché. È successo
l'8 settembre 2026 su un'altra app, nel minuto in cui è arrivata una rete nuova.

Quindi: **quando aggiungi una rete a questo container, allarghi la lista.** E la
verifica non è «l'app risponde 200» — una pagina gated risponde 302 sia perché
non sei loggato sia perché l'app ha buttato via la tua identità. Si prova con una
**sessione vera** e si legge il log dell'app, dove il rifiuto ha una riga che lo
dice per nome.

## Caddy

Il blocco si **genera**, non si scrive:

```bash
python caddy.py --gated
```

Legge `PUBLIC_PATHS` dal codice. Dopo aver toccato le rotte, rigenera e confronta
con quello che gira. Nota la forma: `/editor/*` ha un `handle_path` suo che va
dritto al container dell'editor e non passa né dal gate né dall'app.

## Cloudflare, per questo host

- **Email Address Obfuscation** (Scrape Shield) va spenta con una Configuration
  Rule: riscrive le email nell'HTML e inietta uno script di terze parti, che in
  una pagina che ospita un iframe è solo rumore in più da escludere quando
  qualcosa non va.
- Gli asset portano già l'impronta nell'URL (`?v=`), perché la zona cacha gli
  statici quattro ore.

## Borant ID

Costo d'ingresso: una riga in `PERIMETER` e un `seed --apps`. **Nessun
vocabolario di ruoli**, perché il codice non ne legge nessuno: dichiararne uno
offrirebbe un menu che non apre niente.

## Da dove arriva il codice

Clone di `github.com/that-ugly-cat/draw` nella cartella di deploy. Aggiornare:

```bash
git pull && docker compose up -d --build
```

Due file **non** arrivano con il `pull` e vivono solo sul server: il `.env`, e la
`SPEC.md`, che è gitignorata perché contiene l'analisi dei modi di guasto. Chi
clona da zero non ha la seconda e non ha modo di accorgersene.

Se dopo un `pull` `git status` segnala modificati `caddy.py`, `seed.py` o
`dev-run.py` senza righe di differenza, sono i bit di permesso: `git config
core.fileMode false` e non se ne parla più.

## Prima messa in piedi

```bash
docker compose up -d --build
docker exec draw python seed.py
curl -s localhost:8023/healthz
```

`/healthz` sta fuori dal gate e resta verde **anche se il gate è morto e nessuno
riesce più a entrare**: un controllo utile punta anche a una rotta gated.

## Manutenzione

Lo sfoltimento delle versioni non restituisce lo spazio da solo. Dopo una
potatura, o periodicamente:

```bash
docker exec draw python -c "from draw.server.models import engine; engine.raw_connection().execute('VACUUM')"
```

Backup: il database sta in `data/`, montato come volume. È l'unica cosa da
salvare — non ci sono file di diagramma accanto, per scelta.
