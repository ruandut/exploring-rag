import pytest

from apps.core.testing import make_docx, make_pdf
from apps.rag.parsing import ParseError, parse


def test_pdf_text_is_extracted():
    assert "refund window is 30 days" in parse("a.pdf", make_pdf("The refund window is 30 days"))


def test_docx_headings_become_markdown():
    data = make_docx([("Heading 1", "Intro"), ("Normal", "Hello there"), ("Heading 2", "More")])
    assert parse("a.docx", data) == "# Intro\n\nHello there\n\n## More"


def test_text_and_markdown_are_decoded():
    assert parse("a.md", b"# Title\r\n\r\nBody\n") == "# Title\n\nBody"
    assert parse("a.txt", "café".encode()) == "café"


def test_empty_documents_fail_with_a_reason():
    with pytest.raises(ParseError, match="No text"):
        parse("a.txt", b"   \n ")


def test_corrupt_pdf_fails_with_a_reason():
    with pytest.raises(ParseError):
        parse("a.pdf", b"not a pdf")


def test_unsupported_types_fail():
    with pytest.raises(ParseError, match="Unsupported"):
        parse("a.exe", b"MZ")
