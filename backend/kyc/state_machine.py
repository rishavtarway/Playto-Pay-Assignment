"""The single source of truth for KYC state transitions.

Every place in the codebase that wants to change ``submission.state`` MUST
call :func:`transition`. Setting ``submission.state = ...`` directly anywhere
else is a bug — it bypasses the legality check and the notification log.

The module owns three concerns and nothing else:

    1. legality — ``LEGAL_TRANSITIONS`` + :func:`can_transition`
    2. mutation — :func:`_apply_transition` updates the row
    3. side-effects — :func:`_record_notification`, :func:`_try_send_email`
"""

from __future__ import annotations

from typing import Optional

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import SubmissionState

# The only state moves we accept. Anything else raises ``IllegalTransition``.
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    SubmissionState.DRAFT:               {SubmissionState.SUBMITTED},
    SubmissionState.SUBMITTED:           {SubmissionState.UNDER_REVIEW},
    SubmissionState.UNDER_REVIEW:        {
        SubmissionState.APPROVED,
        SubmissionState.REJECTED,
        SubmissionState.MORE_INFO_REQUESTED,
    },
    SubmissionState.MORE_INFO_REQUESTED: {SubmissionState.SUBMITTED},
    SubmissionState.APPROVED:            set(),  # terminal
    SubmissionState.REJECTED:            set(),  # terminal
}

# Fields touched by ``_apply_transition``. Listed once so ``save(update_fields=)``
# stays in sync with what the function actually mutates.
_TRANSITION_UPDATE_FIELDS = (
    "state",
    "submitted_at",
    "rejection_reason",
    "info_request_reason",
    "assigned_reviewer",
    "updated_at",
)


class IllegalTransition(Exception):
    """Raised when a state transition is not allowed by ``LEGAL_TRANSITIONS``."""


def can_transition(current: str, target: str) -> bool:
    """Pure check — used by serializers/UI hints. No side effects."""
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

    Atomic. Validates the transition, mutates the row, writes a Notification
    record, and (best-effort) emails the merchant. Raises
    :class:`IllegalTransition` if the move is not allowed.
    """
    current_state = submission.state
    _ensure_legal(current_state, target_state)
    _apply_transition(submission, target_state, reason, assigned_reviewer)
    _record_notification(submission, current_state, target_state, reason, actor)
    _try_send_email(submission, current_state, target_state, reason)


def _ensure_legal(current_state: str, target_state: str) -> None:
    if can_transition(current_state, target_state):
        return
    allowed = LEGAL_TRANSITIONS.get(current_state, set())
    allowed_str = ", ".join(sorted(allowed)) if allowed else "none (terminal state)"
    raise IllegalTransition(
        f"Cannot move '{current_state}' → '{target_state}'. "
        f"Allowed from '{current_state}': {allowed_str}."
    )


def _apply_transition(submission, target_state: str, reason: str, assigned_reviewer) -> None:
    """Mutate fields on the submission row. Caller is inside an atomic block."""
    submission.state = target_state

    # First time the submission enters "submitted" — stamp the queue clock.
    if target_state == SubmissionState.SUBMITTED and submission.submitted_at is None:
        submission.submitted_at = timezone.now()

    if target_state == SubmissionState.REJECTED:
        submission.rejection_reason = reason
    elif target_state == SubmissionState.MORE_INFO_REQUESTED:
        submission.info_request_reason = reason

    if assigned_reviewer is not None:
        submission.assigned_reviewer = assigned_reviewer

    submission.save(update_fields=list(_TRANSITION_UPDATE_FIELDS))


def _record_notification(submission, from_state: str, to_state: str, reason: str, actor) -> None:
    """Append a Notification row — the audit log of state changes."""
    # Local import keeps this module's import graph light and avoids a cycle.
    from kyc.models import Notification

    payload = {
        "actor_id":    str(getattr(actor, "id", "")),
        "actor_email": getattr(actor, "email", ""),
        "from_state":  from_state,
        "to_state":    to_state,
        "reason":      reason or None,
    }
    Notification.objects.create(
        merchant=submission.merchant,
        submission=submission,
        event_type=to_state,
        payload=payload,
    )


def _try_send_email(submission, from_state: str, to_state: str, reason: Optional[str]) -> None:
    """Best-effort notification email. Failures never break a transition."""
    try:
        send_mail(
            subject=_email_subject(to_state),
            message=_email_body(submission, from_state, to_state, reason),
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[submission.merchant.email],
            fail_silently=True,
        )
    except Exception:
        # Notification row is already saved; email is just a courtesy.
        pass


def _email_subject(to_state: str) -> str:
    return f"Your KYC submission is now {to_state.replace('_', ' ')}"


def _email_body(submission, from_state: str, to_state: str, reason: Optional[str]) -> str:
    greeting = f"Hi {submission.full_name or 'there'},"
    summary = f"Your KYC submission moved from '{from_state}' to '{to_state}'."
    lines = [greeting, "", summary]
    if reason:
        lines += ["", f"Note from reviewer: {reason}"]
    lines += ["", "— Playto Pay"]
    return "\n".join(lines)
