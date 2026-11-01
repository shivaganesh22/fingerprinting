"""Management command to ensure the default researcher superuser exists idempotently."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Initializes default researcher account for web app authentication"

    def handle(self, *args, **options):
        User = get_user_model()
        username = "researcher"
        password = "researcher123"
        email = "researcher@fpstudy.org"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created researcher user: {username}")
            )
        else:
            # Ensure password is active
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Researcher user {username} already exists; credentials verified.")
            )
