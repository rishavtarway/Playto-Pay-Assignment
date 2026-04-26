"""Tests for the central state machine.

The required test (per the assignment) is
``test_illegal_transition_approved_to_draft`` — but we cover all terminal
states and the happy paths too.
"""

import pytest

from kyc.models import Submission
from kyc.state_machine import IllegalTransition, can_transition, transition


# Required: terminal "approved" cannot move back to "draft".
def test_illegal_transition_approved_to_draft(db, merchant_a, reviewer):
    submission = Submission.objects.create(merchant=merchant_a, state="approved")
    with pytest.raises(IllegalTransition):
        transition(submission, "draft", actor=reviewer)


# Both terminal states are locked against any further movement.
@pytest.mark.parametrize("from_state", ["approved", "rejected"])
@pytest.mark.parametrize("to_state", ["draft", "submitted", "under_review", "more_info_requested"])
def test_terminal_states_are_locked(db, merchant_a, reviewer, from_state, to_state):
    submission = Submission.objects.create(merchant=merchant_a, state=from_state)
    with pytest.raises(IllegalTransition):
        transition(submission, to_state, actor=reviewer)


# Happy path: draft → submitted sets submitted_at.
def test_draft_to_submitted_sets_timestamp(db, merchant_a):
    submission = Submission.objects.create(
        merchant=merchant_a,
        full_name="Test",
        email="t@t.com",
        phone="1",
        business_name="biz",
        business_type="freelance",
        expected_monthly_volume_usd=100,
    )
    transition(submission, "submitted", actor=merchant_a)
    submission.refresh_from_db()
    assert submission.state == "submitted"
    assert submission.submitted_at is not None


# Happy path: full review cycle ends in approved + writes a Notification per step.
def test_full_cycle_writes_notifications(db, merchant_a, reviewer):
    submission = Submission.objects.create(merchant=merchant_a)
    transition(submission, "submitted", actor=merchant_a)
    transition(submission, "under_review", actor=reviewer)
    transition(submission, "approved", actor=reviewer)
    submission.refresh_from_db()
    assert submission.state == "approved"
    assert submission.notifications.count() == 3


# can_transition() is a pure function with no side effects.
def test_can_transition_pure_check():
    assert can_transition("draft", "submitted") is True
    assert can_transition("approved", "draft") is False
    assert can_transition("under_review", "more_info_requested") is True
