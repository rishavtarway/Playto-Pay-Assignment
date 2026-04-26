"""Custom user model with a role field (merchant or reviewer).

We keep Django's username for compatibility but identify users by email in
the API. Role decides which endpoints the user is allowed to hit.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_MERCHANT = "merchant"
    ROLE_REVIEWER = "reviewer"
    ROLE_CHOICES = [
        (ROLE_MERCHANT, "Merchant"),
        (ROLE_REVIEWER, "Reviewer"),
    ]

    # Email must be unique because the API logs users in by email.
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MERCHANT)
    last_assigned_at = models.DateTimeField(null=True, blank=True)

    # Helper booleans keep permission classes readable.
    def is_merchant(self) -> bool:
        return self.role == self.ROLE_MERCHANT

    def is_reviewer(self) -> bool:
        return self.role == self.ROLE_REVIEWER

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"
