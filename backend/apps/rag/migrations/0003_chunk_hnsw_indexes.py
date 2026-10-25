"""HNSW indexes for approximate nearest-neighbour search on chunk embeddings.

`embedding` is an unsized `vector` (each user picks their own model), but HNSW needs a fixed
size. So we build one *partial expression index* per common size: it only covers rows with
that many dimensions, and indexes `embedding::vector(N)`. A query hits it when it uses the
same expression and filter, e.g.

    WHERE dimensions = 1536
    ORDER BY embedding::vector(1536) <=> %s::vector(1536)

Other sizes still work, with an exact (sequential) scan — fine for small libraries.
"""

from django.db import migrations

from apps.rag.models import HNSW_DIMENSIONS


def _create(dims: int) -> str:
    return (
        f"CREATE INDEX rag_chunk_hnsw_{dims} ON rag_chunk "
        f"USING hnsw ((embedding::vector({dims})) vector_cosine_ops) "
        f"WHERE dimensions = {dims};"
    )


class Migration(migrations.Migration):
    dependencies = [("rag", "0002_chunk")]

    operations = [
        migrations.RunSQL(_create(d), reverse_sql=f"DROP INDEX rag_chunk_hnsw_{d};")
        for d in HNSW_DIMENSIONS
    ]
