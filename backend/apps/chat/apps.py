from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = "apps.chat"
    label = "chat"

    def ready(self):
        # Registers the agent.ask / agent.cancel websocket handlers.
        from . import ws_handlers  # noqa: F401
