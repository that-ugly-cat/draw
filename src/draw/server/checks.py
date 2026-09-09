"""
Static checks on a diagram, so a writer that cannot see the page can still be
told what is wrong with it.

The motivating case is concrete. A figure was authored through this app by
writing XML directly, and the defect that survived three rounds of review was a
chip 60 pixels wide containing "Clinics and ethics committees": nothing about
the XML looked wrong, and only rendering it showed the text spilling out. A
renderer would have caught it; so does arithmetic, for a fraction of the cost
and with an answer that says *which cell* rather than handing back a picture to
be interpreted.

What this is not: a judgement of whether the diagram is any good. It reports
things that are mechanically wrong or measurably tight — overflowing labels,
overlapping siblings, edges pointing at cells that do not exist — and says
nothing about composition.
"""

from __future__ import annotations

import html
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

# draw.io's own default when a style names no size.
DEFAULT_FONT_SIZE = 12.0

# Width of an average character as a fraction of the font size, for the sans
# stack draw.io uses. Deliberately a little generous: this check should not cry
# wolf on text that merely fills its box, only on text that cannot fit.
CHAR_WIDTH_RATIO = 0.52

# What a shape spends on padding before any text is drawn, and the height one
# line occupies including leading.
HORIZONTAL_PADDING = 10.0
LINE_HEIGHT_RATIO = 1.30

# The two cells draw.io puts at the root of every page.
ROOT_IDS = {"0", "1"}


@dataclass
class Finding:
    level: str          # error | warning
    kind: str
    page: str
    cell: str | None
    message: str

    def as_dict(self) -> dict:
        return {
            "level": self.level,
            "kind": self.kind,
            "page": self.page,
            "cell": self.cell,
            "message": self.message,
        }


@dataclass
class _Cell:
    id: str
    parent: str | None
    label: str
    style: dict
    x: float
    y: float
    w: float
    h: float
    is_vertex: bool
    is_edge: bool
    source: str | None
    target: str | None
    relative: bool


_TAG = re.compile(r"<[^>]+>")


def _text_of(raw: str) -> list[str]:
    """The label as lines of plain text, the way a reader would see it.

    Labels carry HTML: `<b>`, `<i>`, and `<br>` for the line breaks an author
    put in on purpose. Those breaks are the whole reason this returns a list —
    a two-line label in a short box fits where the same characters on one line
    would not.
    """
    if not raw:
        return []
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    return [ln.strip() for ln in text.split("\n")]


def _style_of(raw: str) -> dict:
    out: dict[str, str] = {}
    for part in (raw or "").split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip()] = v.strip()
        elif part.strip():
            out[part.strip()] = "1"
    return out


def _float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cells_of(page: ET.Element) -> list[_Cell]:
    cells = []
    for el in page.iter("mxCell"):
        geo = el.find("mxGeometry")
        style = _style_of(el.get("style", ""))
        cells.append(
            _Cell(
                id=el.get("id", ""),
                parent=el.get("parent"),
                label=el.get("value", "") or "",
                style=style,
                x=_float(geo.get("x") if geo is not None else 0),
                y=_float(geo.get("y") if geo is not None else 0),
                w=_float(geo.get("width") if geo is not None else 0),
                h=_float(geo.get("height") if geo is not None else 0),
                is_vertex=el.get("vertex") == "1",
                is_edge=el.get("edge") == "1",
                source=el.get("source"),
                target=el.get("target"),
                relative=(geo is not None and geo.get("relative") == "1"),
            )
        )
    return cells


def _label_overflows(c: _Cell) -> tuple[bool, float, float]:
    """Does the label need more room than the shape gives it?

    Returns (overflows, needed_height, available_height). Wrapping is honoured
    when the style asks for it; without `whiteSpace=wrap` draw.io does not wrap,
    so a long line simply runs out of the box sideways and the width comparison
    is the one that matters.
    """
    lines = [ln for ln in _text_of(c.label) if ln]
    if not lines or c.w <= 0 or c.h <= 0:
        return False, 0.0, 0.0

    size = _float(c.style.get("fontSize"), DEFAULT_FONT_SIZE)
    usable = max(c.w - HORIZONTAL_PADDING, 1.0)
    per_line = max(int(usable / (size * CHAR_WIDTH_RATIO)), 1)

    if c.style.get("whiteSpace") == "wrap":
        rows = sum(max(math.ceil(len(ln) / per_line), 1) for ln in lines)
    else:
        # No wrapping: every line stays one line, and the failure is horizontal.
        rows = len(lines)
        widest = max(len(ln) for ln in lines)
        if widest > per_line:
            needed_width = widest * size * CHAR_WIDTH_RATIO + HORIZONTAL_PADDING
            return True, needed_width, c.w

    needed = rows * size * LINE_HEIGHT_RATIO
    return needed > c.h, needed, c.h


def _overlap(a: _Cell, b: _Cell) -> float:
    """Area shared by two boxes, 0 when they merely touch."""
    dx = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    dy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    return dx * dy if dx > 0 and dy > 0 else 0.0


def check(xml: str) -> list[dict]:
    """Every finding in the document, ordered error first."""
    findings: list[Finding] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        return [Finding("error", "unparseable", "", None, f"XML will not parse: {exc}").as_dict()]

    pages = root.findall(".//diagram") or [root]
    seen_ids: dict[str, str] = {}

    for page in pages:
        name = page.get("name") or page.get("id") or "page"
        cells = _cells_of(page)
        by_id = {c.id: c for c in cells}
        vertices = [c for c in cells if c.is_vertex]

        if not vertices:
            findings.append(Finding("warning", "empty_page", name, None, "The page has no shapes."))

        for c in cells:
            # "0" and "1" are the root pair every page carries by construction:
            # they repeat across pages by design, and reporting them would cry
            # wolf on every multi-page file.
            if not c.id or c.id in ROOT_IDS:
                continue
            if c.id in seen_ids and seen_ids[c.id] != name:
                findings.append(Finding(
                    "error", "duplicate_id", name, c.id,
                    f"Cell id also used on page '{seen_ids[c.id]}'. Ids must be unique "
                    "across the file, or edits by id land on the wrong shape.",
                ))
            seen_ids.setdefault(c.id, name)

        # Edges whose ends do not exist. A silent one draws nothing and leaves
        # the reader wondering where the arrow went.
        for c in cells:
            if not c.is_edge:
                continue
            for end, ref in (("source", c.source), ("target", c.target)):
                if ref and ref not in by_id:
                    findings.append(Finding(
                        "error", "dangling_edge", name, c.id,
                        f"Edge {end} points at '{ref}', which is not a cell on this page.",
                    ))

        for c in vertices:
            if c.w <= 0 or c.h <= 0:
                findings.append(Finding(
                    "warning", "no_size", name, c.id,
                    "Vertex has no width or height, so it renders as a dot.",
                ))
                continue
            if c.x < 0 or c.y < 0:
                findings.append(Finding(
                    "warning", "negative_position", name, c.id,
                    f"Sits at ({c.x:g}, {c.y:g}), above or left of the origin.",
                ))
            over, needed, have = _label_overflows(c)
            if over:
                text = " ".join(_text_of(c.label))[:60]
                findings.append(Finding(
                    "warning", "label_overflow", name, c.id,
                    f"Label needs about {needed:.0f}px where the shape gives {have:.0f}px "
                    f"— \"{text}\". Widen it, shorten the text, or drop the font size.",
                ))

        # Overlaps only between siblings: children of a container carry
        # coordinates relative to it, so comparing across parents compares
        # numbers that do not live in the same space.
        for i, a in enumerate(vertices):
            if a.relative:
                continue
            for b in vertices[i + 1:]:
                if b.relative or a.parent != b.parent:
                    continue
                shared = _overlap(a, b)
                if shared <= 0:
                    continue
                smaller = min(a.w * a.h, b.w * b.h)
                if smaller and shared / smaller > 0.15:
                    findings.append(Finding(
                        "warning", "overlap", name, a.id,
                        f"Overlaps '{b.id}' over {shared / smaller:.0%} of the smaller shape.",
                    ))

    order = {"error": 0, "warning": 1}
    findings.sort(key=lambda f: (order.get(f.level, 9), f.page, f.cell or ""))
    return [f.as_dict() for f in findings]


def summary(findings: list[dict]) -> str:
    if not findings:
        return "No findings."
    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = len(findings) - errors
    return f"{errors} error(s), {warnings} warning(s)."
