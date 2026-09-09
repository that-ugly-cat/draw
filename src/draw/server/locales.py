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
