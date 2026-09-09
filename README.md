# draw

Diagrammi draw.io con un workspace per utente, cronologia delle versioni e link
di condivisione per singolo diagramma.

L'app possiede i diagrammi; l'editor è **draw.io non modificato**, servito da un
container accanto e incorporato in un iframe attraverso il suo protocollo embed.
XML entra, XML esce, e tutto ciò che decide qualcosa — chi tiene il lock, cosa
diventa una versione, cosa succede a un salvataggio arrivato tardi — sta nel
server.

## Uso

Ogni diagramma appartiene a una persona. Dal workspace si creano, si aprono, si
rinominano e si cestinano (il cestino trattiene 30 giorni).

**Condivisione.** Per ogni diagramma si creano link, in sola lettura o in lettura
e scrittura, ciascuno con un'etichetta, una scadenza facoltativa e una revoca. La
tabella mostra l'**ultimo uso**: è il campo che serve per decidere cosa revocare.
Chi arriva da un link in scrittura viene chiesto un nome, che è **un'etichetta e
non un'identità** — serve a mostrare chi sta lavorando e ad attribuire le
versioni, e non autorizza niente. Autorizza il token.

**Lavoro in parallelo.** Chi apre un diagramma prende un lock morbido di 90
secondi, rinfrescato dall'autosave. Chi lo trova occupato vede chi lo tiene e può
prenderlo con un'azione esplicita. La regola che conta è un'altra: **un
salvataggio senza lock valido non viene mai buttato via** — diventa una versione
marcata orfana, con la ragione scritta, e chi ha salvato riceve il numero di
versione. Il caso peggiore è una fusione a mano.

**Versioni.** Il documento corrente si sovrascrive a ogni autosave; le versioni
nascono dopo cinque minuti di attività, alla chiusura, e a ogni salvataggio
orfano. Si possono appuntare, e quelle appuntate non vengono mai sfoltite. Ogni
versione si scarica come `.drawio`.

**Limite: 10 MB per diagramma.** Di solito lo fa scattare un'immagine incollata,
che draw.io incorpora come data URI. Il salvataggio viene rifiutato ma il
documento resta aperto nell'editor: non si perde niente.

## Sviluppo

```bash
pip install -e ".[dev]"
JWT_SECRET=dev AUTH_MODE=local python seed.py --user me@example.org --pw secret
JWT_SECRET=dev AUTH_MODE=local uvicorn draw.server.main:app --reload --port 8023
```

L'editor in locale può puntare a un container draw.io (`docker compose up
editor`) impostando `EDITOR_URL=http://localhost:8024/`.

Il blocco Caddy **non si scrive a mano**: `python caddy.py --gated` lo genera
leggendo `PUBLIC_PATHS` in `src/draw/server/main.py`.

## Dati personali

Una richiesta di cancellazione arriva prima o poi, e cancellare in Borant ID non
cancella qui. Le tabelle da guardare:

| tabella | cosa contiene |
|---|---|
| `users` | nome, indirizzo email, subject del gate |
| `diagrams` | titolo, `updated_by_label`, `lock_label` (nomi, anche di ospiti) |
| `diagram_versions` | `author_label` e `author_user_id` |
| `share_links` | `label` e chi ha creato il link |

Il contenuto dei diagrammi è scritto dagli utenti e può contenere qualunque cosa.
