# CLAUDE.md — draw.borant.eu

*Istruzioni per chi lavora su questo repository con Claude Code.*

## Prima di toccare autenticazione, rotte, Caddy, MCP, faccia o lingue

**Leggi le convenzioni dei tool borant prima di scrivere, non dopo.** Sono
scritte per intero in una pagina sola, e si raggiungono in due modi:

- se hai il repository `Ono3` sotto mano:
  `wiki/projects/strumenti/convenzioni-tool-borant.md`
- altrimenti, da qualunque macchina: l'MCP **`onopedia`**,
  `get_page("convenzioni-tool-borant")`

La versione operativa col codice sta in `borant-id/SPEC.md` §20, **gitignorata**:
esiste solo sul disco di chi ha quel clone.

Le sezioni che toccano questo repository sono autenticazione (`local` è il
default, la chiave è il `subject` e mai l'email), **path pubblici** — che qui
sono la parte delicata, perché la superficie ospite include una `POST` che salva
— la vetrina e la home (`/` vetrina che non guarda chi la legge, `/app` gated),
fallire chiusi invece di rimbalzare sul login, faccia e lingue.

**Non ricopiare le convenzioni qui dentro.** Due copie divergono, e quella
sbagliata è sempre la più vicina.

## La cosa specifica di questo repository

> **Sotto `/s/` nessun metodo guarda mai `X-Borant-*`, per costruzione.**

La superficie ospite è autorizzata dal token e non dall'identità. Il giorno che
una rotta lì dentro ha bisogno di sapere *chi* sta chiedendo, quella rotta non
appartiene a `/s/` e va spostata sotto il prefisso gated, non ritagliata per
metodo. Il perché sta in `SPEC.md` §5.

## Le tre fonti di questo repository

- `README.md` — l'uso
- `DEPLOY.md` — il server, senza IP, utenti e percorsi di chiavi
- `SPEC.md` — il perché. **Gitignorata**, perché contiene l'analisi dei modi di
  guasto e le decisioni scartate. Se non ce l'hai, chiedila: non arriva con un
  `git pull`.

## Il blocco Caddy non si scrive a mano

È generato: `python caddy.py --gated` legge `PUBLIC_PATHS` nel modulo del
server. La lista dei path pubblici vive in un posto solo, così chi aggiunge una
rotta pubblica se ne accorge mentre la scrive. Dopo aver toccato le rotte,
rigenera e confronta con quello che gira in produzione.

## L'editor non si tocca

`jgraph/drawio` gira in un container accanto, servito sotto `/editor/*`, con il
tag **pinnato**. Nessuna riga dell'editor viene modificata: è la decisione che
rende l'aggiornamento un cambio di tag invece di un merge. Se una richiesta
sembra richiedere una modifica all'editor, è una richiesta di livello 3 (vedi
`SPEC.md` §11) e va discussa prima, non implementata.
