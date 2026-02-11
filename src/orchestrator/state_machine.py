"""Approval state machine for workflow items."""

from src.models.workflow import ApprovalStatus

# Valid state transitions: {current_state: {action: new_state}}
TRANSITIONS = {
    ApprovalStatus.DRAFT: {
        "submit": ApprovalStatus.IN_REVIEW,
        "approve": ApprovalStatus.APPROVED,
        "reject": ApprovalStatus.REJECTED,
    },
    ApprovalStatus.IN_REVIEW: {
        "approve": ApprovalStatus.APPROVED,
        "reject": ApprovalStatus.REJECTED,
    },
    ApprovalStatus.APPROVED: {
        "publish": ApprovalStatus.PUBLISHED,
        "reject": ApprovalStatus.REJECTED,
    },
    ApprovalStatus.REJECTED: {
        "submit": ApprovalStatus.IN_REVIEW,
        "approve": ApprovalStatus.APPROVED,
    },
    ApprovalStatus.PUBLISHED: {
        "archive": ApprovalStatus.ARCHIVED,
    },
    ApprovalStatus.ARCHIVED: {},
}


def can_transition(current_status: ApprovalStatus, action: str) -> bool:
    """Check if a state transition is valid."""
    available = TRANSITIONS.get(current_status, {})
    return action in available


def get_next_status(current_status: ApprovalStatus, action: str) -> ApprovalStatus:
    """Get the next status for a given action, or raise ValueError."""
    available = TRANSITIONS.get(current_status, {})
    if action not in available:
        raise ValueError(
            f"Cannot perform '{action}' on item with status '{current_status.value}'. "
            f"Available actions: {list(available.keys())}"
        )
    return available[action]


def get_available_actions(current_status: ApprovalStatus) -> list[str]:
    """Get available actions for the current status."""
    return list(TRANSITIONS.get(current_status, {}).keys())
