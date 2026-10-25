from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from . import selectors, services
from .models import Conversation
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

    def destroy(self, request, *args, **kwargs):
        # Through the service, not instance.delete(): it also cancels a reply still streaming.
        try:
            services.delete_conversation(request.user, int(kwargs["pk"]))
        except (Conversation.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
        return Response(status=status.HTTP_204_NO_CONTENT)
