from rest_framework import mixins, viewsets

from . import selectors
from .serializers import ConversationDetailSerializer, ConversationSerializer


class ConversationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Read and delete conversations. New messages arrive over the websocket (agent.ask)."""

    def get_queryset(self):
        qs = selectors.conversations_for(self.request.user)
        return qs.prefetch_related("messages") if self.action == "retrieve" else qs

    def get_serializer_class(self):
        return ConversationDetailSerializer if self.action == "retrieve" else ConversationSerializer
