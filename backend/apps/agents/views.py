from rest_framework import viewsets

from . import selectors, services
from .serializers import AgentSerializer


class AgentViewSet(viewsets.ModelViewSet):
    serializer_class = AgentSerializer

    def get_queryset(self):
        return selectors.agents_for(self.request.user)

    def perform_create(self, serializer):
        serializer.instance = services.save_agent(self.request.user, data=serializer.validated_data)

    def perform_update(self, serializer):
        services.save_agent(
            self.request.user, data=serializer.validated_data, instance=serializer.instance
        )
