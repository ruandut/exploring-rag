"""Chunking strategies are pure functions — test the edge cases here, not in scenarios."""

import pytest

from apps.rag import chunking
from apps.rag.tokens import count_tokens

PROSE = " ".join(f"Sentence number {i} talks about topic {i % 5}." for i in range(200))


@pytest.mark.parametrize("strategy", ["fixed", "recursive", "markdown", "parent_document"])
def test_every_chunk_fits_the_size(strategy):
    drafts = chunking.chunk(PROSE, strategy=strategy, size=50, overlap=10)
    assert len(drafts) > 5
    assert all(0 < d.token_count <= 50 for d in drafts)
    assert all(d.token_count == count_tokens(d.text) for d in drafts)


def test_fixed_overlap_repeats_tokens_between_neighbours():
    text = " ".join(f"w{i}" for i in range(100))
    a, b, *_ = chunking.fixed(text, size=20, overlap=5)
    assert a.text.split()[-5:] == b.text.split()[:5]


def test_fixed_covers_all_text():
    text = " ".join(f"w{i}" for i in range(97))
    drafts = chunking.fixed(text, size=20, overlap=0)
    assert " ".join(d.text for d in drafts) == text


def test_recursive_prefers_paragraph_boundaries():
    paras = ["Alpha " * 10, "Beta " * 10, "Gamma " * 10]
    drafts = chunking.recursive("\n\n".join(paras), size=15, overlap=0)
    assert [d.text.split()[0] for d in drafts] == ["Alpha", "Beta", "Gamma"]


def test_recursive_short_text_is_one_chunk():
    assert [d.text for d in chunking.recursive("Just a little text.", 50, 5)] == [
        "Just a little text."
    ]


def test_recursive_cuts_words_longer_than_size():
    drafts = chunking.recursive("x" * 10 + " " + ("word " * 200), size=20, overlap=0)
    assert all(d.token_count <= 20 for d in drafts)


def test_markdown_keeps_sections_apart_and_records_heading_path():
    text = "# Setup\n\nIntro text.\n\n## Install\n\nRun the installer.\n\n# Usage\n\nOpen the app."
    drafts = chunking.markdown(text, size=100, overlap=0)
    assert [(d.heading, d.text) for d in drafts] == [
        ("Setup", "Intro text."),
        ("Setup › Install", "Run the installer."),
        ("Usage", "Open the app."),
    ]


def test_markdown_text_before_first_heading_is_kept():
    drafts = chunking.markdown("Preface.\n\n# One\n\nBody.", size=100, overlap=0)
    assert [(d.heading, d.text) for d in drafts] == [("", "Preface."), ("One", "Body.")]


def test_semantic_splits_where_meaning_shifts():
    sentences = ["Cats purr.", "Cats nap.", "Cats hunt.", "Taxes are due.", "Taxes are high."]

    def embed(texts):
        # Two "topics": cat sentences point one way, tax sentences another.
        return [[1.0, 0.0] if t.startswith("Cats") else [0.0, 1.0] for t in texts]

    drafts = chunking.semantic(" ".join(sentences), size=100, overlap=0, embed=embed)
    assert [d.text for d in drafts] == [
        "Cats purr. Cats nap. Cats hunt.",
        "Taxes are due. Taxes are high.",
    ]


def test_parent_document_children_point_at_a_bigger_parent():
    drafts = chunking.parent_document(PROSE, size=20, overlap=0)
    assert all(d.token_count <= 20 for d in drafts)
    assert all(d.text in d.parent_text for d in drafts)
    assert all(count_tokens(d.parent_text) <= 80 for d in drafts)


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunking.chunk("text", strategy="fixed", size=10, overlap=10)


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError):
        chunking.chunk("text", strategy="magic", size=10, overlap=0)
