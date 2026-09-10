"""
The model-facing surface of draw.

It exists for one workflow that the web interface cannot serve: authoring a
diagram from a conversation. Before this, that meant writing .drawio XML blind,
handing over a file, and never seeing the result — three rounds on one figure,
with every correction paid in full round trips.

**The design constraint that shapes every tool here is context, not capability.**
A real diagram is forty kilobytes of XML; reading it whole to change one label
spends more of a conversation than the change is worth, and spends it again on
the next edit. So the surface is built as a pair: `outline_diagram` says what is
in the document in a tenth of the space, and `update_cells` changes shapes by id
without rewriting the file. `get_diagram` and `update_diagram` remain for the
cases that really are about the whole document — creating one, mostly.

Access. Every call runs as the human who owns the API key and reaches exactly
what that person reaches. A diagram belonging to somebody else answers "not
found" rather than "forbidden", because otherwise the model could enumerate what
it cannot read.

Writing. A write here is a save like any other: it goes through the same
function the browser uses, so a guest holding the lock still turns it into an
orphan version instead of losing it. What it does **not** do is take the lock —
a script that saves must not block the person who asked for the save. And a
write by the same person who has the document open in a browser is not treated
as a conflict at all: that editor notices the revision moved and reloads.

Errors come back as {"error": ...} rather than raised: a tool that throws gives
the model a stack trace to hallucinate around, while a message it can read lets
it correct course.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from mcp.server.mcpserver import MCPServer

from . import checks, storage
from .auth import current_caller
from .models import Diagram, DiagramVersion, SessionLocal, utcnow

mcp = MCPServer(
    name="draw",
    instructions=(
        "Diagrams in draw.io format, owned by the person whose key this is. "
        "Start with list_diagrams. **Reading a whole diagram is expensive** — a "
        "real one runs to tens of thousands of tokens — so reach for "
        "outline_diagram first: it gives every shape's id, text, size and "
        "position, which is what you need to decide what to change. Then change "
        "shapes with update_cells, by id, instead of rewriting the document. "
        "get_diagram and update_diagram are for whole-document work, mostly "
        "creating one from nothing. "
        "You cannot see the result, so use check_diagram after writing: it "
        "reports labels that do not fit their shape, overlapping boxes and edges "
        "pointing at cells that do not exist. It does not judge whether the "
        "diagram is any good, and it is not a substitute for asking the user to "
        "look. Reads are free; confirm with the user before writing."
    ),
)

# One session per key holder, stable across calls, so consecutive writes are one
# writer rather than a crowd. It never wins a lock from anyone (see main).
MCP_SESSION = "mcp"


def _fail(msg: str) -> dict:
    return {"error": msg}


def _mine(db, diagram_id: int) -> Diagram | None:
    user = current_caller()
    return (
        db.query(Diagram)
        .filter(Diagram.id == diagram_id, Diagram.owner_id == user.id)
        .first()
    )


def _brief(d: Diagram) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        "updated_by": d.updated_by_label,
        "revision": d.revision or 0,
        "size_bytes": d.size_bytes,
        "binned": d.deleted_at is not None,
    }


# --- reading -----------------------------------------------------------------


@mcp.tool()
def list_diagrams(include_binned: bool = False) -> dict:
    """Every diagram this key's owner has, newest change first."""
    db = SessionLocal()
    try:
        user = current_caller()
        q = db.query(Diagram).filter(Diagram.owner_id == user.id)
        if not include_binned:
            q = q.filter(Diagram.deleted_at.is_(None))
        rows = q.order_by(Diagram.updated_at.desc()).all()
        return {"diagrams": [_brief(d) for d in rows], "count": len(rows)}
    finally:
        db.close()


@mcp.tool()
def outline_diagram(diagram_id: int, page: str = "") -> dict:
    """The structure of a diagram without its XML — start here.

    Every shape with its id, text, position and size, and every connector with
    its ends. It is roughly a tenth of the document and it is what you need in
    order to decide what to change; `update_cells` then takes those same ids.
    """
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        try:
            root = ET.fromstring(d.xml)
        except ET.ParseError as exc:
            return _fail(f"The stored XML will not parse: {exc}")

        pages = []
        for p in root.findall(".//diagram") or [root]:
            name = p.get("name") or p.get("id") or "page"
            if page and name != page:
                continue
            shapes, edges = [], []
            for c in checks._cells_of(p):
                if c.id in checks.ROOT_IDS:
                    continue
                if c.is_edge:
                    edges.append({"id": c.id, "label": " ".join(checks._text_of(c.label)),
                                  "source": c.source, "target": c.target})
                elif c.is_vertex:
                    shapes.append({
                        "id": c.id,
                        "text": " ".join(checks._text_of(c.label)),
                        "x": c.x, "y": c.y, "width": c.w, "height": c.h,
                        "parent": c.parent,
                    })
            pages.append({"page": name, "shapes": shapes, "edges": edges})
        if not pages:
            return _fail(f"No page named '{page}'.")
        return {"id": d.id, "title": d.title, "revision": d.revision or 0, "pages": pages}
    finally:
        db.close()


@mcp.tool()
def get_diagram(diagram_id: int, page: str = "") -> dict:
    """The raw XML. Large — prefer outline_diagram unless you need the document.

    `page` narrows it to one page of a multi-page file, which is usually the
    difference between a readable answer and an unreadable one.
    """
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        if not page:
            return {"id": d.id, "title": d.title, "revision": d.revision or 0, "xml": d.xml}
        try:
            root = ET.fromstring(d.xml)
        except ET.ParseError as exc:
            return _fail(f"The stored XML will not parse: {exc}")
        for p in root.findall(".//diagram"):
            if (p.get("name") or p.get("id")) == page:
                return {"id": d.id, "title": d.title, "page": page,
                        "revision": d.revision or 0,
                        "xml": ET.tostring(p, encoding="unicode")}
        return _fail(f"No page named '{page}'.")
    finally:
        db.close()


@mcp.tool()
def search_diagrams(query: str) -> dict:
    """Diagrams whose title or content contains this text.

    Possible because the XML is stored uncompressed: searching what is inside a
    diagram is a query rather than a scan.
    """
    if not query.strip():
        return _fail("Give something to search for.")
    db = SessionLocal()
    try:
        user = current_caller()
        like = f"%{query.strip()}%"
        rows = (
            db.query(Diagram)
            .filter(Diagram.owner_id == user.id, Diagram.deleted_at.is_(None))
            .filter(Diagram.title.ilike(like) | Diagram.xml.ilike(like))
            .order_by(Diagram.updated_at.desc())
            .all()
        )
        out = []
        for d in rows:
            where = []
            if query.lower() in (d.title or "").lower():
                where.append("title")
            if query.lower() in (d.xml or "").lower():
                where.append("content")
            out.append({**_brief(d), "matched": where})
        return {"diagrams": out, "count": len(out)}
    finally:
        db.close()


@mcp.tool()
def list_versions(diagram_id: int, limit: int = 20) -> dict:
    """The history, newest first. Orphans are saves that arrived under someone
    else's lock and were kept rather than refused."""
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        rows = (
            db.query(DiagramVersion)
            .filter(DiagramVersion.diagram_id == d.id)
            .order_by(DiagramVersion.version_no.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return {"versions": [{
            "version_no": v.version_no,
            "created_at": v.created_at.isoformat(),
            "author": v.author_label,
            "origin": v.origin,
            "pinned": v.pinned,
            "orphan": v.orphan,
            "orphan_reason": v.orphan_reason,
            "size_bytes": v.size_bytes,
        } for v in rows]}
    finally:
        db.close()


@mcp.tool()
def get_version(diagram_id: int, version_no: int) -> dict:
    """One version's XML, for comparing or restoring by hand."""
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        v = (
            db.query(DiagramVersion)
            .filter(DiagramVersion.diagram_id == d.id,
                    DiagramVersion.version_no == version_no)
            .first()
        )
        if not v:
            return _fail(f"No version {version_no} on that diagram.")
        return {"version_no": v.version_no, "orphan": v.orphan,
                "xml": storage.decompress(v.xml_z)}
    finally:
        db.close()


# --- checking ----------------------------------------------------------------


@mcp.tool()
def check_diagram(diagram_id: int = 0, xml: str = "") -> dict:
    """What is mechanically wrong with a diagram, since you cannot look at it.

    Pass a diagram_id to check what is stored, or xml to check something before
    saving it. Reports labels that need more room than their shape gives them,
    shapes overlapping their siblings, connectors pointing at cells that do not
    exist, pages with nothing on them.

    It says nothing about whether the diagram reads well. Silence here means no
    measurable defect, not that the figure is good.
    """
    if xml:
        found = checks.check(xml)
        return {"summary": checks.summary(found), "findings": found}
    if not diagram_id:
        return _fail("Give a diagram_id, or xml to check directly.")
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        found = checks.check(d.xml)
        return {"id": d.id, "title": d.title,
                "summary": checks.summary(found), "findings": found}
    finally:
        db.close()


# --- writing -----------------------------------------------------------------


def _save(db, d: Diagram, xml: str) -> dict:
    from .main import _apply_save

    user = current_caller()
    try:
        out = _apply_save(db, d, xml, MCP_SESSION, label=f"{user.label} (mcp)",
                          user_id=user.id, origin="owner")
    except storage.DiagramTooLarge as exc:
        return _fail(
            f"Over the {exc.limit // (1024 * 1024)} MB limit at "
            f"{exc.size / (1024 * 1024):.1f} MB. Usually an embedded image. "
            "Nothing was saved."
        )
    if out.get("ok") is False:
        return {
            "saved": False,
            "reason": "Somebody else holds the lock on this diagram.",
            "holder": out.get("holder"),
            "kept_as_version": out.get("version"),
            "note": "Your XML was kept as an orphan version rather than discarded.",
        }
    return {"saved": True, "revision": out["revision"], "version": out["version"]}


@mcp.tool()
def create_diagram(title: str, xml: str = "") -> dict:
    """A new diagram. With no xml it starts as an empty page."""
    if not title.strip():
        return _fail("A diagram needs a title.")
    db = SessionLocal()
    try:
        user = current_caller()
        body = storage.normalise(xml) if xml else storage.EMPTY_DIAGRAM
        try:
            size = storage.check_size(body)
        except storage.DiagramTooLarge as exc:
            return _fail(f"Over the size limit at {exc.size / (1024 * 1024):.1f} MB.")
        d = Diagram(owner_id=user.id, title=title.strip()[:200], xml=body,
                    size_bytes=size, updated_by_label=f"{user.label} (mcp)", revision=1)
        db.add(d)
        db.commit()
        found = checks.check(body)
        return {"id": d.id, "title": d.title, "revision": d.revision,
                "check": checks.summary(found), "findings": found}
    finally:
        db.close()


@mcp.tool()
def update_diagram(diagram_id: int, xml: str) -> dict:
    """Replace the whole document. For one shape, prefer update_cells."""
    if not xml.strip():
        return _fail("Refusing to save an empty document.")
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        out = _save(db, d, xml)
        if out.get("saved"):
            found = checks.check(d.xml)
            out["check"] = checks.summary(found)
            out["findings"] = found
        return out
    finally:
        db.close()


@mcp.tool()
def update_cells(diagram_id: int, changes: list[dict]) -> dict:
    """Change shapes by id, without rewriting the document.

    Each change is {"cell_id": "...", and any of "text", "style", "x", "y",
    "width", "height"}. Ids come from outline_diagram. This is the cheap way to
    edit: it touches only what you name, so it cannot drop a page by accident,
    and it costs a fraction of a full rewrite.
    """
    if not changes:
        return _fail("No changes given.")
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        try:
            root = ET.fromstring(d.xml)
        except ET.ParseError as exc:
            return _fail(f"The stored XML will not parse: {exc}")

        index = {c.get("id"): c for c in root.iter("mxCell")}
        applied, missing = [], []
        for ch in changes:
            cid = str(ch.get("cell_id") or "")
            el = index.get(cid)
            if el is None:
                missing.append(cid)
                continue
            if "text" in ch:
                el.set("value", str(ch["text"]))
            if "style" in ch:
                el.set("style", str(ch["style"]))
            geo = el.find("mxGeometry")
            for key in ("x", "y", "width", "height"):
                if key in ch:
                    if geo is None:
                        geo = ET.SubElement(el, "mxGeometry")
                        geo.set("as", "geometry")
                    geo.set(key, str(ch[key]))
            applied.append(cid)

        if not applied:
            return _fail(f"None of those cell ids exist: {', '.join(missing) or '—'}")

        out = _save(db, d, ET.tostring(root, encoding="unicode"))
        if out.get("saved"):
            found = checks.check(d.xml)
            out["check"] = checks.summary(found)
            out["findings"] = found
        out["applied"] = applied
        if missing:
            out["not_found"] = missing
        return out
    finally:
        db.close()


@mcp.tool()
def rename_diagram(diagram_id: int, title: str) -> dict:
    if not title.strip():
        return _fail("A diagram needs a title.")
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        d.title = title.strip()[:200]
        db.commit()
        return {"id": d.id, "title": d.title}
    finally:
        db.close()


@mcp.tool()
def delete_diagram(diagram_id: int) -> dict:
    """Move to the bin, which holds for thirty days. Not a purge.

    Thirty days is the retention pass, not a figure of speech: after that the
    diagram is deleted along with its versions and its links.
    """
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        d.deleted_at = utcnow()
        db.commit()
        return {"id": d.id, "binned": True,
                "note": "Recoverable with restore_diagram."}
    finally:
        db.close()


@mcp.tool()
def restore_diagram(diagram_id: int) -> dict:
    db = SessionLocal()
    try:
        d = _mine(db, diagram_id)
        if not d:
            return _fail("No diagram with that id.")
        d.deleted_at = None
        db.commit()
        return {"id": d.id, "binned": False}
    finally:
        db.close()
