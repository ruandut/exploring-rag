from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):
    """Enable pgvector so later apps can declare VectorField columns."""

    dependencies = []

    operations = [VectorExtension()]
