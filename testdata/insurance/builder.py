"""A tiny document builder on top of reportlab, so the content in generate.py reads like a
document: h1/h2 headings are numbered automatically ("4.", "4.2"), clause lists continue the
numbering ("4.2.3"), and every PDF gets a cover page, a table of contents, and a running
header and footer — the parts a real policy wording has.

Fictional test data for RAG Lab. Nothing here describes a real insurer.
"""

from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import BaseDocTemplate, Frame, PageTemplate
from reportlab.platypus.tableofcontents import TableOfContents

COMPANY = "Kestrel Ridge Insurance Limited"
LIFE_COMPANY = "Kestrel Ridge Life Limited"
DISCLAIMER = (
    "FICTIONAL TEST DOCUMENT. Kestrel Ridge Insurance Limited and Kestrel Ridge Life Limited do "
    "not exist. This document was generated as test data for RAG Lab. It is not legal advice, "
    "insurance advice or a real policy, and any resemblance to a real insurer is coincidental."
)

_base = getSampleStyleSheet()
for _name in ("Heading1", "Heading2", "Heading3"):
    _base[_name].keepWithNext = 1  # never strand a heading at the bottom of a page
INK = colors.HexColor("#1f2a37")
ACCENT = colors.HexColor("#0f5c4c")
STYLES = {
    "title": ParagraphStyle("title", parent=_base["Title"], fontSize=24, leading=30, textColor=ACCENT),
    "subtitle": ParagraphStyle(
        "subtitle", parent=_base["Normal"], fontSize=13, leading=18, alignment=TA_CENTER, textColor=INK
    ),
    "h1": ParagraphStyle(
        "h1", parent=_base["Heading1"], fontSize=15, leading=19, spaceBefore=10, spaceAfter=6, textColor=ACCENT
    ),
    "h2": ParagraphStyle("h2", parent=_base["Heading2"], fontSize=12, leading=15, spaceBefore=8, spaceAfter=4),
    "h3": ParagraphStyle("h3", parent=_base["Heading3"], fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=3),
    "body": ParagraphStyle("body", parent=_base["BodyText"], fontSize=9.5, leading=13, spaceAfter=5),
    "clause": ParagraphStyle(
        "clause", parent=_base["BodyText"], fontSize=9.5, leading=13, leftIndent=34, firstLineIndent=-34,
        spaceAfter=4,
    ),
    "sub": ParagraphStyle(
        "sub", parent=_base["BodyText"], fontSize=9.5, leading=13, leftIndent=52, firstLineIndent=-18,
        spaceAfter=3,
    ),
    "note": ParagraphStyle(
        "note", parent=_base["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#4b5563"),
        spaceAfter=5,
    ),
    "cell": ParagraphStyle("cell", parent=_base["BodyText"], fontSize=8.5, leading=10.5),
    "cellhead": ParagraphStyle(
        "cellhead", parent=_base["BodyText"], fontSize=8.5, leading=10.5, textColor=colors.white,
        fontName="Helvetica-Bold",
    ),
    "toc1": ParagraphStyle("toc1", fontSize=9.5, leading=12.5, leftIndent=10),
    "toc2": ParagraphStyle("toc2", fontSize=8.5, leading=10.5, leftIndent=26, textColor=INK),
}


def P(text: str, style: str = "body") -> Paragraph:
    """Plain text in, safe Paragraph out (only <b>/<i> are kept as markup)."""
    safe = escape(text).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    safe = safe.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    return Paragraph(safe, STYLES[style])


@dataclass
class Doc:
    filename: str
    title: str
    subtitle: str
    code: str
    version: str = "Version 4.2 · Effective 1 March 2026"
    company: str = COMPANY
    audience: str = "Policyholders"
    story: list = field(default_factory=list)
    _h1: int = 0
    _h2: int = 0
    _clause: int = 0

    # --- structure ---------------------------------------------------------------------
    def h1(self, text: str, *, new_page: bool = False) -> None:
        if new_page and self.story:
            self.story.append(PageBreak())
        self._h1 += 1
        self._h2 = 0
        self._clause = 0
        para = P(f"{self._h1}. {text}", "h1")
        para._toc = (0, f"{self._h1}. {text}")
        self.story.append(para)

    def h2(self, text: str) -> None:
        self._h2 += 1
        self._clause = 0
        para = P(f"{self._h1}.{self._h2} {text}", "h2")
        para._toc = (1, f"{self._h1}.{self._h2} {text}")
        self.story.append(para)

    def h3(self, text: str) -> None:
        self.story.append(P(text, "h3"))

    def annexure(self, letter: str, text: str) -> None:
        """Annexures restart numbering under a letter, like real policy documents."""
        self.story.append(PageBreak())
        self._h1 = 0
        self._h2 = 0
        para = P(f"Annexure {letter}: {text}", "h1")
        para._toc = (0, f"Annexure {letter}: {text}")
        self.story.append(para)

    # --- content -----------------------------------------------------------------------
    def p(self, *texts: str) -> None:
        for t in texts:
            self.story.append(P(t))

    def note(self, text: str) -> None:
        self.story.append(P(text, "note"))

    def clauses(self, *items) -> None:
        """Numbered clauses. An item may be (text, [sub-items]) for (a), (b), (c) lists."""
        prefix = f"{self._h1}.{self._h2}" if self._h2 else f"{self._h1}"
        for item in items:
            text, subs = (item, []) if isinstance(item, str) else item
            self._clause += 1
            self.story.append(P(f"{prefix}.{self._clause}   {text}", "clause"))
            for i, sub in enumerate(subs):
                self.story.append(P(f"({chr(97 + i)}) {sub}", "sub"))

    def bullets(self, *items: str) -> None:
        for item in items:
            self.story.append(P(f"•  {item}", "sub"))

    def table(self, header: list[str], rows: list[list], widths: list[float] | None = None) -> None:
        data = [[P(str(h), "cellhead") for h in header]] + [
            [P(str(c), "cell") for c in row] for row in rows
        ]
        total = A4[0] - 40 * mm
        col_widths = [total * w for w in widths] if widths else None
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f4")]),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7d2cf")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        self.story.append(t)
        self.story.append(Spacer(1, 6))

    def keep(self, *texts: str) -> None:
        self.story.append(KeepTogether([P(t) for t in texts]))

    def page_break(self) -> None:
        self.story.append(PageBreak())

    # --- output ------------------------------------------------------------------------
    def build(self, path: str) -> int:
        """Write the PDF; returns its page count."""
        doc = _Template(path, self)
        toc = TableOfContents(levelStyles=[STYLES["toc1"], STYLES["toc2"]], dotsMinLevel=0)
        cover = [
            Spacer(1, 45 * mm),
            P(self.company, "subtitle"),
            Spacer(1, 6 * mm),
            P(self.title, "title"),
            P(self.subtitle, "subtitle"),
            Spacer(1, 10 * mm),
            P(f"Document {self.code} · {self.version}", "subtitle"),
            P(f"Audience: {self.audience}", "subtitle"),
            Spacer(1, 30 * mm),
            P(DISCLAIMER, "note"),
            PageBreak(),
            P("Contents", "h1"),
            toc,
            PageBreak(),
        ]
        doc.multiBuild(cover + self.story)
        return doc.page


class _Template(BaseDocTemplate):
    def __init__(self, path: str, spec: Doc):
        super().__init__(
            path,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=22 * mm,
            bottomMargin=20 * mm,
            title=spec.title,
            author=f"{spec.company} (fictional)",
            subject="Fictional test data for RAG Lab",
        )
        self.spec = spec
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=self._decorate)])

    def afterFlowable(self, flowable):
        toc = getattr(flowable, "_toc", None)
        if toc:
            self.notify("TOCEntry", (toc[0], toc[1], self.page))

    def _decorate(self, canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(20 * mm, A4[1] - 12 * mm, f"{self.spec.company} — {self.spec.title}")
        canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, self.spec.code)
        canvas.drawString(20 * mm, 10 * mm, "Fictional test document — RAG Lab")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()
