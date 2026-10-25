from django.apps import AppConfig


class RagConfig(AppConfig):
    name = "apps.rag"
    label = "rag"

    def ready(self):
        from . import signals  # noqa: F401 - registers the receivers
