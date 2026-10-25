import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings):
    # Tests don't need Redis: the in-memory layer behaves the same within one process.
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("alice", "alice@example.com", "s3cret-pass!")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user("bob", "bob@example.com", "s3cret-pass!")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def auth_api(api, user):
    api.force_authenticate(user)
    return api
