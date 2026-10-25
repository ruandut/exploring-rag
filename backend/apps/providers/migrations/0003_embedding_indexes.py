"""Embedding models moved from the provider to each embedding (spec 0010).

Runs after rag 0005, which copies these fields into the user's "My documents" embedding.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("providers", "0002_connection"),
        ("rag", "0005_my_documents"),
    ]

    operations = [
        migrations.RemoveField(model_name="providerconfig", name="embedding_dimensions"),
        migrations.RemoveField(model_name="providerconfig", name="embedding_model"),
    ]
