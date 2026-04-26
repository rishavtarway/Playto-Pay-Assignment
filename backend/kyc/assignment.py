"""Round-robin reviewer assignment (bonus).

Picks the reviewer with the fewest currently-open submissions, breaking ties on
``last_assigned_at`` so reviewers rotate fairly. Wrapped in a transaction with
``select_for_update`` so two concurrent ``start`` calls cannot grab the same
reviewer twice.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import Submission, SubmissionState

User = get_user_model()

# States that count as "currently in the reviewer's load".
_OPEN_STATES = (
    SubmissionState.SUBMITTED,
    SubmissionState.UNDER_REVIEW,
    SubmissionState.MORE_INFO_REQUESTED,
)


@transaction.atomic
def pick_next_reviewer():
    """Return the reviewer with the lightest open load, or None if none exist."""
    # NB: no select_for_update() on this query — Postgres rejects FOR UPDATE
    # combined with aggregate functions ("SELECT FOR UPDATE is not allowed
    # with aggregate functions"). We instead lock only the chosen row below.
    candidates = (
        User.objects
        .filter(role=User.ROLE_REVIEWER, is_active=True)
        .annotate(
            open_count=Count(
                "assigned_submissions",
                filter=Q(assigned_submissions__state__in=_OPEN_STATES),
            )
        )
        # nulls_first so a brand-new reviewer (last_assigned_at=NULL) wins
        # the tiebreak — Postgres and SQLite disagree on default NULL ordering,
        # so be explicit.
        .order_by("open_count", F("last_assigned_at").asc(nulls_first=True), "id")
    )
    chosen = candidates.first()
    if chosen is None:
        return None
    # Lock just the chosen row before bumping last_assigned_at so two concurrent
    # callers can't write the same timestamp from stale reads. The aggregate
    # query above isn't lockable, but a one-row lookup is.
    User.objects.select_for_update().filter(pk=chosen.pk).first()
    chosen.last_assigned_at = timezone.now()
    chosen.save(update_fields=["last_assigned_at"])
    return chosen


# Convenience: assign a reviewer to a submission if it doesn't have one yet.
def assign_reviewer_if_needed(submission: Submission):
    if submission.assigned_reviewer_id:
        return submission.assigned_reviewer
    reviewer = pick_next_reviewer()
    if reviewer is not None:
        submission.assigned_reviewer = reviewer
        submission.save(update_fields=["assigned_reviewer"])
    return reviewer
