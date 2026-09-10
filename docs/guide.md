# draw — User Guide

draw is the draw.io editor with a workspace behind it. The editor is the real one, unmodified, running in a container next door; everything around it — the account, the storage, the version history, the share links — is what this app adds. Diagrams belong to a person, keep their history, and travel as links rather than as files.

---

## 1. What it is, and what it is not

draw.io itself has no memory of you: no accounts, no storage of its own, so it opens and saves to your disk or to a cloud drive. The consequence is the one everybody knows — the diagram lives on one machine, and showing it to a colleague means emailing a copy that is out of date the moment it is sent and cannot be taken back.

What this app adds is an owner, a history and a link. What it does **not** add is live co-editing: no other cursors, no cells moving under your hands. draw.io's real-time layer talks to draw.io's own servers, and using it would mean forking the editor — which is the one thing this project refuses, because not forking is what makes an editor upgrade a version change instead of a merge. What you get instead is §5.

It is also not a general document store: there are no folders, no permissions between accounts, and no server-side rendering. A diagram is reached by its owner, or through a link its owner made.

## 2. Getting in

Sign-in is **Borant ID**, the single login shared by every borant tool, so if you already use one of them you already have an account here.

1. If you do not: register at `id.borant.eu` and confirm your email address. Borant ID handles the password and, where it is switched on, the second factor.
2. A new account opens nothing. It starts with **zero grants** — registering earns you the right to *ask* — so ask Spit for access to draw — by hand, for now — and wait for the grant. That is deliberate: opening registration must not open any app.
3. Go to `draw.borant.eu`. The page at `/` is a public showcase that never looks at who is reading it; the app is behind the **Enter** button, which is where the gate runs.

The language switcher in the top bar offers Italian, English, German and French. German and French currently render the English strings; Italian is the fallback for anything untranslated. Diagram titles are yours and are never translated.

## 3. Your workspace

`/app` is the whole of what you can see: every diagram you own, newest change first, and nothing else.

- **Create** one with the box at the top. Give it a title there — an empty title becomes *Untitled*, and titles are cut at 200 characters. There is no rename button in the web app today: a chat client can rename (§8), otherwise name it when you create it.
- Each tile carries a **thumbnail**, produced by your own browser after a save and posted back — which is why a brand-new diagram shows an empty tile until you have drawn something and it has saved.
- A tile shows a warning badge when somebody else is editing that diagram, and a count of its live share links.
- **Delete** moves the diagram to the **bin** at the bottom of the page, where **Restore** brings it back — one click should not be final. The bin is a grace period and not a second archive: take out of it anything you mean to keep.

## 4. Drawing, and how saving works

Opening a diagram loads the editor in an iframe and hands it the XML. The editor never sees the database: XML goes in, XML comes out, and every decision — who holds the lock, what becomes a version, what happens to a late save — is made by the server. If the editor image were ever compromised, what it reaches is the document open at that moment, not the archive.

**Saving is automatic.** Every change the editor reports is sent and written; the badge in the bar says *Saving…* and then *Saved*. Identical states are skipped, because the editor re-emits them often. There is no Save button to forget.

**The limit is 10 MB per diagram**, checked on every save, and what trips it is almost always a pasted screenshot: draw.io embeds it as a data URI and the document grows tenfold. The save is refused with a message that says so and gives the current size — the document stays open in the editor and nothing is lost. Remove the image, or link it instead of embedding it.

The stored form is **plain XML**, not draw.io's compressed payload, and that is a deliberate choice with two consequences you can use: searching inside your diagrams is possible at all (§8), and cell ids stay stable, which is what makes editing one shape by id possible.

## 5. Two people, one diagram

Opening a diagram takes a **soft lock** that lasts 90 seconds and is refreshed every 30 while the page is open, so it covers anyone actually working and frees a diagram a minute and a half after somebody shuts a laptop — a long lock produces diagrams held by forgotten tabs, which is how soft locks become hated. Closing the tab releases it immediately, when it can.

The bar tells you whether nobody is editing, you are, or somebody else is — by name. When somebody else holds it you can **Take over** with an explicit confirmation that states what happens: they lose the lock, and their work is not lost because it becomes a version.

**The rule that matters is not the lock.**

> A save that arrives without a valid lock is never thrown away.

It is kept as a version marked **orphan**, with the reason recorded, and whoever saved is told which version number it became. The lock only reduces how often two people collide; the orphan rule is what makes a collision harmless. Of the two, the orphan rule is the one that would survive. In practice this means you are never blocked from drawing while someone else holds the lock — your saves land as orphan versions rather than as the current document, and reconciling them is a comparison by hand, never an hour lost.

Two details that look odd until you see the reason:

- **The lock is keyed on a browser session, not on a person.** You in two tabs are two holders and you will see the conflict. That is the case that happens most often of all, and hiding it would be worse than showing it.
- **But another session of the same person is not a conflict.** You in a browser and you through a chat client are one intent; orphaning half of your own work would only hide it somewhere you then have to go and find. Two guests, on the other hand, are two people and do conflict — they carry no identity, so treating them as the same person would be wrong in the dangerous direction.

Because your own second session can write, an open editor asks on every lock refresh whether the document moved. If it did and you have nothing unsaved, the page quietly reloads what the server holds. If you do have unsaved work, a banner offers **Reload** — which replaces what you see — or **Keep mine**. Keeping yours is safe: whatever it overwrites is already a version.

## 6. Versions

The current document is overwritten by every autosave; the history is a separate thing, because the two have different write frequencies. A version is cut on the first save more than five minutes after the last one, and on every orphan save. Byte-identical content never produces a second row. Without that split, an afternoon's work would leave hundreds of complete copies of a document that can weigh megabytes.

`/app/d/{id}/versions` lists the most recent 200, with the version number, the time, who saved it, and a badge on orphans carrying the reason they were parked.

- **Pin** anything you might need to point at later. The retention policy keeps everything from the last day, then one version an hour for a week, then one a day — and it never touches a pinned version, nor an orphan, because an orphan is the record of a conflict somebody may still have to resolve.
- Every version downloads as a **`.drawio` file**, which opens in any draw.io.

There is no one-click restore of an old version. To bring one back you download it and open it, or you use a chat client to read that version and write it back as the current document (§8). Merging two versions is human work, and the tool promises exactly what it can keep: nothing is lost, not that nothing has to be reconciled.

## 7. Share links

Sharing is per diagram and per link, not per person. There are no permissions between accounts: **whoever holds the URL has the capability the link carries.**

From `/app/d/{id}/links` you make as many links as you want:

| Field | What it does |
|---|---|
| Mode | **Read only** opens the diagram as a view with no editing tools. **Read and write** lets the holder edit and save |
| Label | For you, so a list of tokens is a list of people six months later |
| Expires | A number of days, or blank for never |

The table shows each live link's URL (click to select it), its mode, its expiry, and **last used** with a use count. That last column is the one that makes managing links real rather than nominal: without it, six months in there is a list of links and no way to tell which anyone still needs, so nobody revokes any. **Revoke** kills a link immediately; a revoked or expired link answers *not found*, and so does one whose diagram is in the bin.

Somebody arriving through a read-write link is asked, once per browser, for a name. That name is **a label and not an identity**: it is used to show who is working and to attribute versions, it is not verified, and nothing is authorised by it. The token authorises; identity never enters that side of the app at all, by construction.

**What a guest cannot do:** anything except open and save. No version history, no link list, no creating or revoking links, no deleting, no renaming, and no sight of the rest of your workspace. Management verbs live only on the owner's side. A guest holding the lock does count as another person, so a save of yours arriving under it becomes an orphan version.

## 8. Working from a chat (MCP)

If you work with an AI assistant, draw plugs into it. It exists for one thing the web interface cannot do: composing a diagram inside a conversation, instead of writing `.drawio` XML blind, handing over a file, and never seeing the result.

**Getting a key.** Open **MCP keys** in the top bar, create one, and paste the endpoint (`https://draw.borant.eu/mcp`) and the key into your client's MCP settings as an `X-API-Key` header. Clients that cannot set headers can use `https://draw.borant.eu/mcp/k/<your-key>/` instead — there the key sits in the URL, where access logs may keep it, so use one key per client and revoke rather than share. The table shows each key's last use, which is what turns revoking from a guess into a decision.

**Read cheaply, and know which call to make.** A real diagram is tens of thousands of tokens of XML, so reading it whole to change one label costs more than the change is worth and costs it again on the next edit. The surface is built around that: ask for the **outline** — every shape's id, text, position and size, at roughly a tenth of the document — and change shapes **by id**, which touches only what it names and so cannot drop a page by accident. Reach for the whole document only when the job really is the whole document, which in practice means creating one from nothing.

**What the assistant can do.** List and search your diagrams — the search reads their *content* and not only their titles, which is possible because the XML is stored plain; read an outline or the XML; create one; patch shapes by id; replace a whole document; rename; bin and restore; list the history and read any version; and run the **check**.

**The check is what a writer who cannot see the page needs.** It reports labels that need more room than their shape gives them, shapes overlapping their siblings, connectors pointing at cells that do not exist, empty pages, cell ids reused across pages. It is arithmetic on the XML, and it says *which cell*. It says nothing about whether the diagram reads well: silence there means no measurable defect, not a good figure. Look at the result yourself.

**What it reaches.** Exactly what you reach — the key carries your identity, so somebody else's diagram does not exist as far as your assistant is concerned. A write through the key is a save like any other and goes through the same code the browser uses, so a guest's lock still turns it into an orphan rather than losing it. It never *takes* the lock, because a script that saves must not block the person who asked for the save.

## 9. Data protection

- **Stored per diagram:** the full XML, which is whatever you drew and typed; every retained version of it, compressed; a PNG thumbnail; the title; and the display name of whoever saved last, guests included.
- **Stored per person:** your name, email address and Borant ID subject; the labels you gave your share links and your MCP keys, with their last-used stamps.
- **A share link is a capability held by whoever has the URL.** There is no account behind it and no identity check. Sending one sends the diagram's whole current content to anybody the URL reaches, and a read-write link in the wrong hands is write access — mitigated by an expiry, immediate revocation and the last-used column, not by anything stronger. A link does not expose the rest of your workspace, the version history, or your other links.
- **An MCP key is a second door onto the same diagrams**, and whatever your assistant reads reaches whichever model that client talks to. Decide that once, deliberately, and revoke the key when the project ends.
- Diagram content is unconstrained, so treat a figure like any other document: personal data and special categories of data do not belong in one that will travel as a link. Deleting your account upstream in Borant ID does **not** delete anything here — ask for the removal you actually want.

## 10. Good practices

- **Share a link, never a file.** The whole point is that the thing you sent stays current and can be taken back. An attachment is a copy that is stale immediately and cannot be revoked.
- **Read-only unless there is a reason.** Give read-write to the person who is going to draw, and put an expiry on it — a link with no expiry is one you will have to remember to revoke.
- **Pin before a deadline**, and pin the version you actually submitted. Pinning is free, thinning is not selective, and "the figure as it went to the reviewer" is a thing you will want to point at a year later.
- **Do not paste screenshots into a diagram.** It is the one reliable way to hit the 10 MB ceiling, and an embedded bitmap is not a diagram anybody can edit.
- **If you see somebody else's name in the bar, talk to them before taking over.** The tool guarantees nothing is lost; it does not guarantee that merging two versions of a figure by hand is quick.
- **Draft from a chat, finish in the editor.** Composing structure in a conversation is fast and the check catches what arithmetic can catch; composition, spacing and whether the figure actually reads are yours, and they are decided by looking at it.
