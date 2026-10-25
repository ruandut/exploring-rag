from django.db.models import QuerySet

from .models import Agent


def agents_for(user) -> QuerySet[Agent]:
    return Agent.objects.filter(owner=user).select_related("connection").prefetch_related("folders")


def get_agent(user, agent_id: int) -> Agent:
    return agents_for(user).get(pk=agent_id)
