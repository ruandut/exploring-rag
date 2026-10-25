"""Every chunk now belongs to an embedding (0005 attached them), and chunking settings live on
each embedding, so the per-user IndexingConfig goes."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rag", "0005_my_documents")]

    operations = [
        migrations.AlterField(
            model_name="chunk",
            name="embedding_index",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chunks",
                to="rag.embeddingindex",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="indexingconfig", name="rag_indexing_overlap_lt_size"
        ),
        migrations.DeleteModel(name="IndexingConfig"),
    ]
