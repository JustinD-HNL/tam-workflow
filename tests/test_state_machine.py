"""Tests for the approval state machine.

Verifies all valid transitions, invalid transitions, and available actions
for each status in the approval workflow.
"""

import pytest

from src.models.workflow import ApprovalStatus
from src.orchestrator.state_machine import (
    TRANSITIONS,
    can_transition,
    get_available_actions,
    get_next_status,
)


# ---------------------------------------------------------------------------
# Valid transition tests
# ---------------------------------------------------------------------------

class TestValidTransitions:
    """Test that all expected state transitions work correctly."""

    def test_draft_submit_to_in_review(self):
        assert can_transition(ApprovalStatus.DRAFT, "submit") is True
        assert get_next_status(ApprovalStatus.DRAFT, "submit") == ApprovalStatus.IN_REVIEW

    def test_draft_approve_to_approved(self):
        assert can_transition(ApprovalStatus.DRAFT, "approve") is True
        assert get_next_status(ApprovalStatus.DRAFT, "approve") == ApprovalStatus.APPROVED

    def test_draft_reject_to_rejected(self):
        assert can_transition(ApprovalStatus.DRAFT, "reject") is True
        assert get_next_status(ApprovalStatus.DRAFT, "reject") == ApprovalStatus.REJECTED

    def test_in_review_approve_to_approved(self):
        assert can_transition(ApprovalStatus.IN_REVIEW, "approve") is True
        assert get_next_status(ApprovalStatus.IN_REVIEW, "approve") == ApprovalStatus.APPROVED

    def test_in_review_reject_to_rejected(self):
        assert can_transition(ApprovalStatus.IN_REVIEW, "reject") is True
        assert get_next_status(ApprovalStatus.IN_REVIEW, "reject") == ApprovalStatus.REJECTED

    def test_approved_publish_to_published(self):
        assert can_transition(ApprovalStatus.APPROVED, "publish") is True
        assert get_next_status(ApprovalStatus.APPROVED, "publish") == ApprovalStatus.PUBLISHED

    def test_approved_reject_to_rejected(self):
        assert can_transition(ApprovalStatus.APPROVED, "reject") is True
        assert get_next_status(ApprovalStatus.APPROVED, "reject") == ApprovalStatus.REJECTED

    def test_rejected_submit_to_in_review(self):
        assert can_transition(ApprovalStatus.REJECTED, "submit") is True
        assert get_next_status(ApprovalStatus.REJECTED, "submit") == ApprovalStatus.IN_REVIEW

    def test_rejected_approve_to_approved(self):
        assert can_transition(ApprovalStatus.REJECTED, "approve") is True
        assert get_next_status(ApprovalStatus.REJECTED, "approve") == ApprovalStatus.APPROVED

    def test_published_archive_to_archived(self):
        assert can_transition(ApprovalStatus.PUBLISHED, "archive") is True
        assert get_next_status(ApprovalStatus.PUBLISHED, "archive") == ApprovalStatus.ARCHIVED


# ---------------------------------------------------------------------------
# Invalid transition tests
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    """Test that invalid transitions are properly rejected."""

    def test_draft_cannot_publish(self):
        assert can_transition(ApprovalStatus.DRAFT, "publish") is False

    def test_draft_cannot_archive(self):
        assert can_transition(ApprovalStatus.DRAFT, "archive") is False

    def test_in_review_cannot_publish(self):
        assert can_transition(ApprovalStatus.IN_REVIEW, "publish") is False

    def test_in_review_cannot_submit(self):
        assert can_transition(ApprovalStatus.IN_REVIEW, "submit") is False

    def test_approved_cannot_submit(self):
        assert can_transition(ApprovalStatus.APPROVED, "submit") is False

    def test_approved_cannot_approve(self):
        assert can_transition(ApprovalStatus.APPROVED, "approve") is False

    def test_approved_cannot_archive(self):
        assert can_transition(ApprovalStatus.APPROVED, "archive") is False

    def test_published_cannot_approve(self):
        assert can_transition(ApprovalStatus.PUBLISHED, "approve") is False

    def test_published_cannot_reject(self):
        assert can_transition(ApprovalStatus.PUBLISHED, "reject") is False

    def test_published_cannot_submit(self):
        assert can_transition(ApprovalStatus.PUBLISHED, "submit") is False

    def test_archived_is_terminal(self):
        """Archived status allows no further transitions."""
        assert can_transition(ApprovalStatus.ARCHIVED, "approve") is False
        assert can_transition(ApprovalStatus.ARCHIVED, "reject") is False
        assert can_transition(ApprovalStatus.ARCHIVED, "publish") is False
        assert can_transition(ApprovalStatus.ARCHIVED, "submit") is False
        assert can_transition(ApprovalStatus.ARCHIVED, "archive") is False

    def test_rejected_cannot_publish(self):
        assert can_transition(ApprovalStatus.REJECTED, "publish") is False

    def test_rejected_cannot_reject(self):
        assert can_transition(ApprovalStatus.REJECTED, "reject") is False

    def test_rejected_cannot_archive(self):
        assert can_transition(ApprovalStatus.REJECTED, "archive") is False

    def test_nonsense_action_returns_false(self):
        """Completely unknown actions should return False."""
        assert can_transition(ApprovalStatus.DRAFT, "yeet") is False
        assert can_transition(ApprovalStatus.APPROVED, "explode") is False


# ---------------------------------------------------------------------------
# get_next_status raises ValueError on invalid transitions
# ---------------------------------------------------------------------------

class TestGetNextStatusRaises:
    """Test that get_next_status raises ValueError for invalid transitions."""

    def test_raises_on_invalid_action(self):
        with pytest.raises(ValueError, match="Cannot perform"):
            get_next_status(ApprovalStatus.DRAFT, "publish")

    def test_raises_on_archived_any_action(self):
        with pytest.raises(ValueError, match="Cannot perform"):
            get_next_status(ApprovalStatus.ARCHIVED, "approve")

    def test_raises_on_unknown_action(self):
        with pytest.raises(ValueError, match="Cannot perform"):
            get_next_status(ApprovalStatus.IN_REVIEW, "unknown_action")

    def test_error_message_includes_available_actions(self):
        with pytest.raises(ValueError, match="Available actions"):
            get_next_status(ApprovalStatus.DRAFT, "archive")


# ---------------------------------------------------------------------------
# get_available_actions
# ---------------------------------------------------------------------------

class TestGetAvailableActions:
    """Test that get_available_actions returns the correct list for each status."""

    def test_draft_actions(self):
        actions = get_available_actions(ApprovalStatus.DRAFT)
        assert set(actions) == {"submit", "approve", "reject"}

    def test_in_review_actions(self):
        actions = get_available_actions(ApprovalStatus.IN_REVIEW)
        assert set(actions) == {"approve", "reject"}

    def test_approved_actions(self):
        actions = get_available_actions(ApprovalStatus.APPROVED)
        assert set(actions) == {"publish", "reject"}

    def test_rejected_actions(self):
        actions = get_available_actions(ApprovalStatus.REJECTED)
        assert set(actions) == {"submit", "approve"}

    def test_published_actions(self):
        actions = get_available_actions(ApprovalStatus.PUBLISHED)
        assert set(actions) == {"archive"}

    def test_archived_actions(self):
        actions = get_available_actions(ApprovalStatus.ARCHIVED)
        assert actions == []


# ---------------------------------------------------------------------------
# TRANSITIONS dict completeness
# ---------------------------------------------------------------------------

class TestTransitionsCompleteness:
    """Verify the TRANSITIONS dict covers every ApprovalStatus value."""

    def test_all_statuses_present(self):
        for status in ApprovalStatus:
            assert status in TRANSITIONS, f"{status} missing from TRANSITIONS dict"

    def test_all_next_statuses_are_valid(self):
        """Every transition target must be a valid ApprovalStatus."""
        for _current, actions in TRANSITIONS.items():
            for _action, target in actions.items():
                assert isinstance(target, ApprovalStatus), (
                    f"Transition target {target} is not an ApprovalStatus"
                )
