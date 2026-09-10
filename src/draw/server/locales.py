"""
Four languages, one dictionary each, Italian as the net for anything missing.

The rule that shapes this file: an error travels as a code, never as a sentence.
Whoever produces an error does not know what language it will be read in;
whoever renders the page does. So `storage.DiagramTooLarge` carries
`diagram_too_large` and the words live here.

If a surface shows the language switcher it has to be translated, admin panels
included — a switcher that promises and does not deliver costs more than the
lines it saves. Diagram titles are written by users and stay as they are.
"""

from __future__ import annotations

LANGUAGES = {"it": "Italiano", "en": "English", "de": "Deutsch", "fr": "Français"}
DEFAULT = "it"

STRINGS: dict[str, dict[str, str]] = {
    "it": {
        "app_name": "draw",
        "tagline": "Diagrammi, dove sta il resto del lavoro",
        "showcase_lead": "Un editor di diagrammi con i tuoi diagrammi dentro: "
                         "workspace personale, cronologia delle versioni e link "
                         "di condivisione per singolo diagramma.",
        "enter": "Entra",
        "workspace": "Workspace",
        "new_diagram": "Nuovo diagramma",
        "untitled": "Senza titolo",
        "open": "Apri",
        "rename": "Rinomina",
        "rename_ask": "Nuovo titolo",
        "close": "Chiudi",
        "delete": "Elimina",
        "restore": "Ripristina",
        "bin": "Cestino",
        "empty_workspace": "Non c'è ancora nessun diagramma. Creane uno.",
        "updated": "Aggiornato",
        "by": "da",
        "versions": "Versioni",
        "version": "Versione",
        "pinned": "Appuntata",
        "pin": "Appunta",
        "unpin": "Togli l'appunto",
        "orphan": "Orfana",
        "orphan_hint": "Salvata mentre il lock era di qualcun altro. Non è andata "
                       "persa: va confrontata a mano.",
        "share": "Condivisione",
        "share_links": "Link di condivisione",
        "new_link": "Nuovo link",
        "mode_ro": "Sola lettura",
        "mode_rw": "Lettura e modifica",
        "revoke": "Revoca",
        "revoked": "Revocato",
        "expires": "Scade",
        "days": "giorni",
        "never": "mai",
        "last_used": "Ultimo uso",
        "never_used": "mai usato",
        "copy_link": "Copia il link",
        "link_label": "Etichetta",
        "guest_name_ask": "Come ti chiami? Serve solo a mostrare chi sta "
                          "lavorando sul diagramma.",
        "guest_name_note": "Non è una verifica d'identità: è un'etichetta.",
        "continue": "Continua",
        "read_only": "Sola lettura",
        "lock_free": "Nessuno sta modificando",
        "lock_yours": "Stai modificando tu",
        "lock_other": "In modifica da {who}",
        "take_over": "Prendi il controllo",
        "take_over_warn": "Chi sta modificando perderà il lock. Il lavoro già "
                          "fatto non si perde: diventa una versione.",
        "saved": "Salvato",
        "saving": "Salvataggio…",
        "save_orphan": "Il lock è di {who}. Il tuo lavoro è stato conservato "
                       "come versione {n}.",
        "moved_elsewhere": "Modificato altrove",
        "moved_reload": "Questo diagramma è stato modificato altrove. Ricaricare "
                        "sostituisce quello che vedi; le tue modifiche non salvate "
                        "andrebbero perse.",
        "reload_it": "Ricarica",
        "keep_mine": "Tieni le mie",
        "reloaded": "Aggiornato da un'altra sessione",
        "keys": "Chiavi MCP",
        "keys_lead": "Una chiave per client, revocabile. Porta la tua identità: "
                     "raggiunge esattamente ciò che raggiungi tu, niente di più.",
        "new_key": "Nuova chiave",
        "endpoint": "Endpoint",
        "created": "Creata",
        # --- landing ---
        "land_lead": "L'editor draw.io con un workspace dietro: i diagrammi "
                     "appartengono a un account, conservano la loro storia, e "
                     "viaggiano come link invece che come file.",
        "p1_title": "Niente di quello che disegni va perso",
        "p1_body": "Un salvataggio che non si pu\u00f2 applicare viene conservato come "
                   "versione marcata, mai rifiutato. La storia si sfoltisce nel "
                   "tempo, ma le versioni appuntate non si toccano.",
        "p2_title": "Si condivide un diagramma, non un account",
        "p2_body": "Link per singolo diagramma, in lettura o in scrittura, ognuno "
                   "con scadenza, revoca e data di ultimo uso \u2014 il campo che "
                   "trasforma il revocare da indovinello a decisione.",
        "p3_title": "L'editor \u00e8 quello vero, non modificato",
        "p3_body": "draw.io gira in un container accanto, a versione fissata e "
                   "senza una riga toccata. \u00c8 ci\u00f2 che rende un aggiornamento un "
                   "cambio di tag; il prezzo, dichiarato invece che nascosto, \u00e8 "
                   "che non c'\u00e8 la modifica simultanea in tempo reale.",
        "plain_words": "in parole semplici",
        "plain_title": "Cos'\u00e8, e perch\u00e9 non \u00e8 solo draw.io su un dominio",
        "plain_1": "**Il problema.** draw.io \u00e8 un editor eccellente che non ha "
                   "memoria di te: non ha account e non ha uno storage suo, apre e "
                   "salva su Drive, sul disco, su qualunque cosa gli indichi. Cos\u00ec "
                   "i diagrammi finiscono su una macchina sola, e mostrarne uno a "
                   "qualcuno significa allegare un file a una mail \u2014 cio\u00e8 una "
                   "copia, vecchia dall'istante dopo, che non si pu\u00f2 pi\u00f9 ritirare.",
        "plain_2": "**Cosa aggiunge questo.** Un account, un workspace, una "
                   "cronologia e dei link. L'editor \u00e8 lo stesso: \u00e8 tutto il resto "
                   "a essere nuovo.",
        "plain_3": "**In due sullo stesso disegno.** Chi apre un diagramma prende "
                   "un lock morbido, e l'altro vede da chi. Se un salvataggio "
                   "arriva lo stesso non viene rifiutato: resta come versione "
                   "marcata, cos\u00ec il caso peggiore \u00e8 confrontare due versioni a "
                   "mano e non perdere un pomeriggio. Quella regola conta pi\u00f9 del "
                   "lock.",
        "plain_4": "**Tu due volte.** Una scheda del browser e uno script sono la "
                   "stessa persona, quindi non litigano: l'editor aperto si accorge "
                   "che il documento si \u00e8 mosso e lo ricarica.",
        "geek_mode": "modalit\u00e0 tecnica",
        "geek_title": "Stessa storia, meccanismo",
        "geek_1": "**Architettura.** `jgraph/drawio` non modificato, in un container "
                  "suo, servito sotto `/editor/` sullo stesso host perch\u00e9 l'iframe "
                  "resti same-origin; l'app ci parla col protocollo embed, XML "
                  "dentro e XML fuori. L'editor non vede mai il database.",
        "geek_2": "**Storage.** Documento corrente e storia stanno separati perch\u00e9 "
                  "hanno frequenze di scrittura diverse: l'autosave sovrascrive il "
                  "primo, le versioni nascono su debounce, deduplicate per SHA-256 "
                  "e compresse a riposo. La forma canonica \u00e8 XML in chiaro, quindi "
                  "cercare dentro un diagramma \u00e8 una query e gli id delle celle "
                  "restano stabili.",
        "geek_3": "**Concorrenza.** Lock morbido chiavato su una sessione e non su "
                  "una persona, pi\u00f9 una `revision` che si muove a ogni scrittura e "
                  "viaggia su ogni rinfresco del lock. Un salvataggio sotto il lock "
                  "di un altro viene parcheggiato come versione orfana, con la "
                  "ragione scritta.",
        "geek_4": "**Superficie per i modelli.** Un endpoint MCP con chiave per "
                  "utente, disegnato attorno al costo del contesto: un outline al "
                  "posto del documento, patch per id di cella al posto delle "
                  "riscritture, pi\u00f9 un controllo statico che riporta etichette che "
                  "non stanno nella loro forma, sovrapposizioni e archi che puntano "
                  "a celle inesistenti.",
        "language": "Lingua",
        "sign_out": "Esci",
        # error codes
        "err_diagram_too_large": "Il diagramma supera il limite di {limit} MB "
                                 "(adesso {size} MB). Di solito è un'immagine "
                                 "incollata: toglila o collegala invece di "
                                 "incorporarla. Il documento non è perso.",
        "err_not_found": "Non trovato.",
        "err_link_dead": "Questo link non è più valido.",
        "err_read_only": "Questo link è di sola lettura.",
        "err_gate": "Configurazione: il gate non è davanti a questa richiesta.",
    },
    "en": {
        "app_name": "draw",
        "tagline": "Diagrams, where the rest of the work lives",
        "showcase_lead": "A diagram editor with your diagrams in it: a personal "
                         "workspace, version history, and share links per diagram.",
        "enter": "Enter",
        "workspace": "Workspace",
        "new_diagram": "New diagram",
        "untitled": "Untitled",
        "open": "Open",
        "rename": "Rename",
        "rename_ask": "New title",
        "close": "Close",
        "delete": "Delete",
        "restore": "Restore",
        "bin": "Bin",
        "empty_workspace": "No diagrams yet. Create one.",
        "updated": "Updated",
        "by": "by",
        "versions": "Versions",
        "version": "Version",
        "pinned": "Pinned",
        "pin": "Pin",
        "unpin": "Unpin",
        "orphan": "Orphan",
        "orphan_hint": "Saved while someone else held the lock. Nothing was "
                       "lost: it needs comparing by hand.",
        "share": "Sharing",
        "share_links": "Share links",
        "new_link": "New link",
        "mode_ro": "Read only",
        "mode_rw": "Read and write",
        "revoke": "Revoke",
        "revoked": "Revoked",
        "expires": "Expires",
        "days": "days",
        "never": "never",
        "last_used": "Last used",
        "never_used": "never used",
        "copy_link": "Copy link",
        "link_label": "Label",
        "guest_name_ask": "What should we call you? It is only used to show who "
                          "is working on the diagram.",
        "guest_name_note": "This is not an identity check: it is a label.",
        "continue": "Continue",
        "read_only": "Read only",
        "lock_free": "Nobody is editing",
        "lock_yours": "You are editing",
        "lock_other": "Being edited by {who}",
        "take_over": "Take over",
        "take_over_warn": "Whoever is editing will lose the lock. Their work is "
                          "not lost: it becomes a version.",
        "saved": "Saved",
        "saving": "Saving…",
        "save_orphan": "{who} holds the lock. Your work was kept as version {n}.",
        "moved_elsewhere": "Changed elsewhere",
        "moved_reload": "This diagram was changed elsewhere. Reloading replaces "
                        "what you see; unsaved changes of yours would be lost.",
        "reload_it": "Reload",
        "keep_mine": "Keep mine",
        "reloaded": "Updated from another session",
        "keys": "MCP keys",
        "keys_lead": "One key per client, revocable. It carries your identity: "
                     "it reaches exactly what you reach, and nothing more.",
        "new_key": "New key",
        "endpoint": "Endpoint",
        "created": "Created",
        # --- landing ---
        "land_lead": "The draw.io editor with a workspace behind it: diagrams "
                     "belong to an account, keep their history, and travel as "
                     "links rather than as files.",
        "p1_title": "Nothing you draw is lost",
        "p1_body": "A save that cannot be applied is kept as a marked version, "
                   "never refused. The history thins over time, but pinned "
                   "versions are never touched.",
        "p2_title": "You share a diagram, not an account",
        "p2_body": "Per-diagram links, read-only or read-write, each with an "
                   "expiry, a revoke button and a last-used stamp \u2014 the field "
                   "that turns revoking from a guess into a decision.",
        "p3_title": "The editor is the real one, unmodified",
        "p3_body": "draw.io runs in a container next door, at a pinned version, "
                   "with not a line patched. That is what makes an upgrade a tag "
                   "change; the price, stated rather than hidden, is that there is "
                   "no live co-editing.",
        "plain_words": "plain words",
        "plain_title": "What this is, and why it is not just draw.io on a domain",
        "plain_1": "**The problem.** draw.io is an excellent editor with no memory "
                   "of you. It has no accounts and no storage of its own: it opens "
                   "and saves to Drive, to your disk, to whatever you point it at. "
                   "So diagrams end up on one machine, and showing one to somebody "
                   "means attaching a file to an email \u2014 a copy, out of date from "
                   "the moment it is sent, and impossible to take back.",
        "plain_2": "**What this adds.** An account, a workspace, a history and "
                   "links. The editor is the same one: everything around it is "
                   "what is new.",
        "plain_3": "**Two people on one drawing.** Whoever opens a diagram takes a "
                   "soft lock, and the other sees whose it is. If a save arrives "
                   "anyway it is not refused: it is kept as a marked version, so "
                   "the worst case is comparing two versions by hand rather than "
                   "losing an afternoon. That rule matters more than the lock does.",
        "plain_4": "**You, twice.** A browser tab and a script are the same person, "
                   "so they do not fight: the open editor notices the document "
                   "moved and reloads it.",
        "geek_mode": "geek mode",
        "geek_title": "Same story, mechanism",
        "geek_1": "**Architecture.** Unmodified `jgraph/drawio` in its own "
                  "container, served under `/editor/` on the same host so the "
                  "iframe stays same-origin; the app talks to it over the embed "
                  "protocol, XML in and XML out. The editor never sees the database.",
        "geek_2": "**Storage.** The current document and its history are kept "
                  "apart, because they have different write frequencies: autosave "
                  "overwrites the first, versions are cut on a debounce, "
                  "deduplicated by SHA-256 and compressed at rest. The canonical "
                  "form is plain XML, so searching inside a diagram is a query and "
                  "cell ids stay stable.",
        "geek_3": "**Concurrency.** A soft lock keyed on a session rather than on a "
                  "person, plus a `revision` that moves on every write and rides "
                  "along on every lock refresh. A save under somebody else's lock "
                  "is parked as an orphan version with the reason recorded.",
        "geek_4": "**Model-facing surface.** An MCP endpoint with a per-user key, "
                  "designed around context cost: an outline instead of the "
                  "document, patches by cell id instead of rewrites, plus a static "
                  "check that reports labels that will not fit their shape, "
                  "overlapping shapes, and edges pointing at cells that are not "
                  "there.",
        "language": "Language",
        "sign_out": "Sign out",
        "err_diagram_too_large": "This diagram is over the {limit} MB limit "
                                 "(currently {size} MB). Usually it is a pasted "
                                 "image: remove it, or link it instead of "
                                 "embedding it. Nothing has been lost.",
        "err_not_found": "Not found.",
        "err_link_dead": "This link is no longer valid.",
        "err_read_only": "This link is read only.",
        "err_gate": "Configuration: the gate did not run in front of this request.",
    },
}

# German and French start as copies of English and get translated in one pass;
# every key is added to all four together, so a missing one is a mistake and not
# a stage of work. Italian is the net underneath.
STRINGS["de"] = dict(STRINGS["en"])
STRINGS["fr"] = dict(STRINGS["en"])

DATE_FORMAT = {
    # No %b outside English: without setlocale Python renders it in English
    # anyway, so there it would be an untranslated word dressed as a format.
    "it": "%d/%m/%Y %H:%M",
    "en": "%d %b %Y %H:%M",
    "de": "%d.%m.%Y %H:%M",
    "fr": "%d/%m/%Y %H:%M",
}


def t(lang: str, key: str, **kw) -> str:
    table = STRINGS.get(lang) or STRINGS[DEFAULT]
    value = table.get(key) or STRINGS[DEFAULT].get(key) or key
    return value.format(**kw) if kw else value


def pick(header: str | None, cookie: str | None) -> str:
    if cookie in STRINGS:
        return cookie
    for chunk in (header or "").split(","):
        code = chunk.split(";")[0].strip().lower()[:2]
        if code in STRINGS:
            return code
    return DEFAULT
