from app.db.enums import LeadState

# The one place lead transitions are defined. PENDING → REACHED_OUT is the only edge.
ALLOWED_TRANSITIONS: dict[LeadState, set[LeadState]] = {
    LeadState.PENDING: {LeadState.REACHED_OUT},
}


def can_transition(source: LeadState, target: LeadState) -> bool:
    return target in ALLOWED_TRANSITIONS.get(source, set())


def sources_for(target: LeadState) -> set[LeadState]:
    """States that have an edge into `target` (used as the guard in a conditional UPDATE)."""
    return {source for source, targets in ALLOWED_TRANSITIONS.items() if target in targets}
