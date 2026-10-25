"""Build the fictional Kestrel Ridge insurance document set and its answer key.

    uv run --no-project --with reportlab --with pypdf python testdata/insurance/generate.py

Writes testdata/insurance/pdfs/*.pdf and testdata/insurance/cases.jsonl (an eval suite you can
import on the Benchmarks page). Every answer's evidence snippet is checked against the text
pypdf extracts from the PDF — the same parser the app uses — so the suite can't drift from the
documents. Output is deterministic (fixed random seed).
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pypdf import PdfReader  # noqa: E402

import common  # noqa: E402
import docs_commercial  # noqa: E402
import docs_home  # noqa: E402
import docs_internal  # noqa: E402
import docs_life  # noqa: E402
import docs_motor  # noqa: E402

BUILDERS = [
    docs_home.build,
    docs_motor.build,
    docs_commercial.build,
    docs_life.build,
    docs_internal.claims_manual,
    docs_internal.underwriting,
    docs_internal.complaints_tcf,
    docs_internal.privacy,
    docs_internal.financial_crime,
]

# Questions none of the documents answer: a good assistant says it doesn't know.
REFUSALS = [
    "What is Kestrel Ridge's share price on the JSE?",
    "Does the household policy cover damage on the moon?",
    "What was Kestrel Ridge's profit in 2024?",
    "Who won the 2023 Rugby World Cup?",
    "What is the excess for pet medical insurance?",
]


def norm(s: str) -> str:
    return " ".join(s.lower().split())


def main() -> None:
    out = HERE / "pdfs"
    out.mkdir(exist_ok=True)
    texts: dict[str, str] = {}
    total_pages = 0
    for build in BUILDERS:
        doc = build()
        path = out / doc.filename
        pages = doc.build(str(path))
        total_pages += pages
        reader = PdfReader(str(path))
        texts[doc.filename] = norm("\n".join(p.extract_text() or "" for p in reader.pages))
        size_kb = path.stat().st_size // 1024
        words = len(texts[doc.filename].split())
        print(f"{doc.filename:62} {pages:4} pages {words:7,} words {size_kb:6,} KB")

    for q in REFUSALS:
        common.refusal(q)

    missing = [
        c for c in common.CASES
        if c["kind"] == "qa" and norm(c["evidence"]) not in texts[c["relevant_documents"][0]]
    ]
    for c in missing:
        print(f"  evidence not found in {c['relevant_documents'][0]}: {c['evidence']!r}")
    if missing:
        sys.exit(f"{len(missing)} evidence snippets are missing — fix the content or the case")

    with (HERE / "cases.jsonl").open("w") as fh:
        for c in common.CASES:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    qa = sum(c["kind"] == "qa" for c in common.CASES)
    print(f"\n{len(BUILDERS)} documents, {total_pages} pages; cases.jsonl: {qa} questions + {len(REFUSALS)} refusals")


if __name__ == "__main__":
    main()
