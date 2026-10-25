"""Retrieval against real Postgres + pgvector, with hand-made vectors (no LLM needed)."""

from types import SimpleNamespace

import pytest

from apps.library.models import Document, Folder
from apps.rag import retrieval
from apps.rag.models import Chunk, EmbeddingIndex

# 3-d toy space: x = payments, y = errors, z = everything else
PAYMENTS, ERRORS, OTHER = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]


def embedding_of(user, name="toy") -> EmbeddingIndex:
    return EmbeddingIndex.objects.get_or_create(
        owner=user, name=name, defaults={"model": "toy", "all_documents": True}
    )[0]


def add_doc(user, name, chunks, folder=None, index=None):
    doc = Document.objects.create(owner=user, folder=folder, name=name, size=1, file=f"x/{name}")
    for i, (text, vec) in enumerate(chunks):
        Chunk.objects.create(
            embedding_index=index or embedding_of(user),
            owner=user,
            document=doc,
            index=i,
            text=text,
            token_count=len(text.split()),
            embedding=vec,
            dimensions=len(vec),
            embedding_model="toy",
        )
    return doc


@pytest.fixture
def corpus(user):
    add_doc(
        user,
        "errors.md",
        [
            ("A fault means something broke.", ERRORS),
            ("Crashes are reported automatically.", [0.1, 0.99, 0.0]),
            ("E-4012: the payment gateway timed out.", PAYMENTS),
            ("Support answers on weekdays.", OTHER),
        ],
    )


def tags(chunks):
    return [c.tag for c in chunks]


def run(user, query, vector, method, top_k=2, **kw):
    return retrieval.search(
        user,
        query,
        config=retrieval.RetrievalConfig(method=method, top_k=top_k, **kw),
        index=embedding_of(user),
        embed=lambda texts: [vector for _ in texts],
        client=None,
        chat_model="m",
    )


def test_dense_ranks_by_meaning(db, user, corpus):
    assert tags(run(user, "Which error code is E-4012?", ERRORS, "dense")) == [
        "errors.md#0",
        "errors.md#1",
    ]


def test_keyword_finds_exact_codes_embeddings_miss(db, user, corpus):
    assert tags(run(user, "Which error code is E-4012?", ERRORS, "keyword")) == ["errors.md#2"]


def test_hybrid_fuses_both(db, user, corpus):
    found = tags(run(user, "Which error code is E-4012?", ERRORS, "hybrid"))
    assert found[0] in ("errors.md#0", "errors.md#2") and "errors.md#2" in found


def test_rrf_rewards_agreement():
    fused = retrieval.rrf([[(1, 0.9), (2, 0.8)], [(2, 5.0), (3, 4.0)]])
    assert [cid for cid, _ in fused] == [2, 1, 3]


def test_mmr_prefers_diversity(db, user, corpus):
    # #0 and #1 are near-duplicates in meaning; MMR picks #0 then something different.
    picked = tags(run(user, "errors", [0.2, 0.98, 0.0], "mmr", top_k=2))
    assert picked[0] == "errors.md#1" and picked[1] != "errors.md#0"


def test_other_users_chunks_are_never_returned(db, user, other_user, corpus):
    add_doc(other_user, "secret.md", [("Bob's error notes.", ERRORS)])
    assert all(c.document == "errors.md" for c in run(user, "error", ERRORS, "hybrid", top_k=10))


def test_folder_scoping_includes_subfolders(db, user):
    a = Folder.objects.create(owner=user, name="A")
    sub = Folder.objects.create(owner=user, name="Sub", parent=a)
    b = Folder.objects.create(owner=user, name="B")
    add_doc(user, "in-sub.md", [("plants are watered", OTHER)], folder=sub)
    add_doc(user, "in-b.md", [("plants are watered", OTHER)], folder=b)
    found = retrieval.search(
        user,
        "plants",
        config=retrieval.RetrievalConfig(method="hybrid", top_k=5),
        index=embedding_of(user),
        folder_ids=[a.pk],
        embed=lambda t: [OTHER for _ in t],
        client=None,
        chat_model="m",
    )
    assert {c.document for c in found} == {"in-sub.md"}


def test_at_0010_14_retrieval_never_crosses_embeddings(db, user, corpus):
    # Same model, same size, same text — but another embedding: never returned.
    other = embedding_of(user, "other")
    add_doc(user, "other.md", [("A fault means something broke.", ERRORS)], index=other)
    found = run(user, "fault", ERRORS, "hybrid", top_k=10)
    assert "other.md" not in {c.document for c in found}


def test_dimensions_must_match_the_query(db, user, corpus):
    assert run(user, "anything", [1.0, 0.0], "dense") == []


def test_llm_rerank_reorders(db, user, corpus, monkeypatch):
    monkeypatch.setattr(retrieval, "complete", lambda *a, **k: "[1, 0]")
    found = run(user, "error", ERRORS, "dense", top_k=2, rerank="llm")
    assert tags(found)[:2] == ["errors.md#1", "errors.md#0"]


def test_multi_query_searches_every_variant(db, user, corpus, monkeypatch):
    monkeypatch.setattr(retrieval, "complete", lambda *a, **k: "payment gateway\nE-4012 meaning")
    seen = []

    def embed(texts):
        seen.extend(texts)
        return [ERRORS for _ in texts]

    retrieval.search(
        user,
        "Which error code is E-4012?",
        config=retrieval.RetrievalConfig(method="hybrid", top_k=3, query_transform="multi_query"),
        index=embedding_of(user),
        embed=embed,
        client=SimpleNamespace(),
        chat_model="m",
    )
    assert seen == ["Which error code is E-4012?", "payment gateway", "E-4012 meaning"]


def test_hyde_embeds_a_hypothetical_answer(db, user, corpus, monkeypatch):
    monkeypatch.setattr(retrieval, "complete", lambda *a, **k: "The gateway timed out.")
    seen = []
    retrieval.search(
        user,
        "Why did my payment fail?",
        config=retrieval.RetrievalConfig(method="dense", top_k=1, query_transform="hyde"),
        index=embedding_of(user),
        embed=lambda texts: seen.extend(texts) or [PAYMENTS for _ in texts],
        client=SimpleNamespace(),
        chat_model="m",
    )
    assert seen == ["The gateway timed out."]
