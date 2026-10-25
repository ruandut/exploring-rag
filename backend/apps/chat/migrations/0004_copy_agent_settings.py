"""Before 0010 an agent owned its connection, model and folders. Now the chat picks them, so
every conversation gets what its agent used: its connection + model, and the user's oldest
embedding ("My documents" after rag 0005). Folder scoping has no equivalent and is dropped —
make an embedding of those folders to get it back."""

from django.db import migrations


def forwards(apps, schema_editor):
    Conversation = apps.get_model("chat", "Conversation")
    EmbeddingIndex = apps.get_model("rag", "EmbeddingIndex")
    first = {}
    for index in EmbeddingIndex.objects.order_by("created_at", "pk"):
        first.setdefault(index.owner_id, index)
    for conv in Conversation.objects.select_related("agent"):
        if conv.agent is not None:
            conv.connection_id = conv.agent.connection_id
            conv.model = conv.agent.model
        index = first.get(conv.owner_id)
        if index is not None:
            conv.embedding, conv.embedding_name = index, index.name
        conv.save(update_fields=["connection", "model", "embedding", "embedding_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0003_agent_embedding_model"),
        ("agents", "0001_initial"),
        ("rag", "0006_drop_indexing_config"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
