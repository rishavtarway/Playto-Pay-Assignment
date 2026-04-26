"""The single source of truth for KYC state transitions.

Every view that wants to change ``submission.state`` MUST call ``transition()``
in this module. Setting ``submission.state = ...`` directly anywhere else is a
bug — it bypasses the transition rules and the notification log.
"""

from __future__ import annotations

from typing import Optional

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone


# The only transitions we accept. Anything else raises IllegalTransition.
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "draft":               {"submitted"},
    "submitted":           {"under_review"},
    "under_review":        {"approved", "rejected", "more_info_requested"},
    "more_info_requested": {"submitted"},
    "approved":            set(),  # terminal
    "rejected":            set(),  # terminal
}


# Custom exception so the DRF exception handler can return a clean 400 shape.
class IllegalTransition(Exception):
    """Raised when a state transition is not allowed."""


# Cheap pure check — used in serializers/UI hints. No side effects.
def can_transition(current: str, target: str) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, set())


@transaction.atomic
def transition(
    submission,
    target_state: str,
    *,
    actor,
    reason: str = "",
    assigned_reviewer=None,
) -> None:
    """Move ``submission`` from its current state to ``target_state``.

    Atomic. Validates the transition, updates timestamps, writes a
    Notification row, and (best-effort) sends an email. Raises
    ``IllegalTransition`` if the move is not allowed.
    """
    current = submission.state
    if not can_transition(current, target_state):
        allowed = LEGAL_TRANSITIONS.get(current, set())
        allowed_str = ", ".join(sorted(allowed)) if allowed else "none (terminal state)"
        raise IllegalTransition(
            f"Cannot move '{current}' → '{target_state}'. "
            f"Allowed from '{current}': {allowed_str}."
        )

    submission.state = target_state

    # Set submitted_at the first time we move into "submitted".
    if target_state == "submitted" and submission.submitted_at is None:
        submission.submitted_at = timezone.now()

    if target_state == "rejected":
        submission.rejection_reason = reason
    elif target_state == "more_info_requested":
        submission.info_request_reason = reason

    if assigned_reviewer is not None:
        submission.assigned_reviewer = assigned_reviewer

    submission.save(update_fields=[
        "state",
        "submitted_at",
        "rejection_reason",
        "info_request_reason",
        "assigned_reviewer",
        "updated_at",
    ])

    # Local import keeps the module import-light and avoids circular imports.
    from kyc.models import Notification

    payload = {
        "actor_id": str(getattr(actor, "id", "")),
        "actor_email": getattr(actor, "email", ""),
        "from_state": current,
        "to_state": target_state,
        "reason": reason or None,
    }
    Notification.objects.create(
        merchant=submission.merchant,
        submission=submission,
        event_type=target_state,
        payload=payload,
    )

    # Bonus: try to send a real email. Console backend in dev, SMTP in prod.
    _try_send_email(submission, current, target_state, reason)


# Best-effort email send. We never let email failures break the transition.
def _try_send_email(submission, from_state: str, to_state: str, reason: Optional[str]) -> None:
    try:
        subject = f"Your KYC submission is now {to_state.replace('_', ' ')}"
        lines = [
            f"Hi {submission.full_name or 'there'},",
            "",
            f"Your KYC submission moved from '{from_state}' to '{to_state}'.",
        ]
        if reason:
            lines += ["", f"Note from reviewer: {reason}"]
        lines += ["", "— Playto Pay"]
        send_mail(
            subject=subject,
            message="\n".join(lines),
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[submission.merchant.email],
            fail_silently=True,
        )
    except Exception:
        # We log to Notification regardless; email is best-effort.
        pass
