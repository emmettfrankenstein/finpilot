import os

from django.core.management.base import BaseCommand, CommandError

from apps.users.models import Role, User

DEMO_USERS = [
    ("viewer", Role.VIEWER, "DEMO_VIEWER_PASSWORD"),
    ("admin", Role.ADMIN, "DEMO_ADMIN_PASSWORD"),
]


class Command(BaseCommand):
    help = "Create or update the demo VIEWER and ADMIN users. Passwords come from the environment."

    def handle(self, *args, **options):
        for username, role, env_name in DEMO_USERS:
            password = os.environ.get(env_name)
            if not password:
                raise CommandError(f"{env_name} is not set; refusing to create '{username}'")
            user, created = User.objects.get_or_create(username=username)
            user.role = role
            user.first_name = "Demo"
            user.last_name = role.label
            user.set_password(password)
            user.save()
            self.stdout.write(f"{'created' if created else 'updated'} {username} ({role})")
