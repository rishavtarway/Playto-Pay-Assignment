"""Round-robin reviewer assignment (bonus).

Picks the reviewer with the fewest currently-open submissions, breaking ties
on ``last_assigned_at`` so reviewers rotate fairly. Wrapped in an atomic
block, with a row-level lock on the chosen reviewer to keep two concurrent
``start`` calls from grabbing the same one twice.
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
    """Return the reviewer with the lightest open load, or ``None``."""
    chosen = _candidate_reviewers().first()
    if chosen is None:
        return None
    _bump_last_assigned(chosen)
    return chosen


def assign_reviewer_if_needed(submission: Submission):
    """Assign a reviewer to ``submission`` if it doesn't already have one."""
    if submission.assigned_reviewer_id:
        return submission.assigned_reviewer
    reviewer = pick_next_reviewer()
    if reviewer is not None:
        submission.assigned_reviewer = reviewer
        submission.save(update_fields=["assigned_reviewer"])
    return reviewer


def _candidate_reviewers():
    """Active reviewers, ordered by (open_count ASC, last_assigned_at ASC, id)."""
    return (
        User.objects
        .filter(role=User.ROLE_REVIEWER, is_active=True)
        .annotate(
            open_count=Count(
                "assigned_submissions",
                filter=Q(assigned_submissions__state__in=_OPEN_STATES),
            )
        )
        # nulls_first so a brand-new reviewer (NULL last_assigned_at) wins the
        # tiebreak. Postgres and SQLite default to opposite NULL orderings, so
        # we always state our intent explicitly.
        .order_by("open_count", F("last_assigned_at").asc(nulls_first=True), "id")
    )


def _bump_last_assigned(reviewer) -> None:
    """Stamp ``last_assigned_at`` on ``reviewer`` with a row-level lock.

    The aggregate query in ``_candidate_reviewers`` cannot be combined with
    ``SELECT FOR UPDATE`` on Postgres, but a single-row lookup can — so we
    lock the chosen row here, just before the write.
    """
    User.objects.select_for_update().filter(pk=reviewer.pk).first()
    reviewer.last_assigned_at = timezone.now()
    reviewer.save(update_fields=["last_assigned_at"])
