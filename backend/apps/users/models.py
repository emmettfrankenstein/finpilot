from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    VIEWER = "VIEWER", "Viewer"
    ADMIN = "ADMIN", "Administrator"


class User(AbstractUser):
    """Internal service-team user. Role drives API authorisation (least privilege: VIEWER)."""

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        db_table = "app_user"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="app_user_role_valid"
            )
        ]

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN
