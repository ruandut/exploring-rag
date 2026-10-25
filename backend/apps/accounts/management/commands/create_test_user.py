from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create (or reset) a user for the executable specs in acceptance/. DEBUG only."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")

    def handle(self, *args, username, password, **options):
        if not settings.DEBUG:
            raise CommandError("create_test_user only runs with DEBUG=true")
        user, _ = get_user_model().objects.get_or_create(username=username)
        user.set_password(password)
        user.save()
        self.stdout.write(str(user.id))
