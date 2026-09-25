from app.db.enums import LeadState
from app.leads.state_machine import ALLOWED_TRANSITIONS, can_transition, sources_for


def test_pending_to_reached_out_is_allowed() -> None:
    assert can_transition(LeadState.PENDING, LeadState.REACHED_OUT)


def test_no_way_back_or_self_loops() -> None:
    assert not can_transition(LeadState.REACHED_OUT, LeadState.PENDING)
    assert not can_transition(LeadState.PENDING, LeadState.PENDING)
    assert not can_transition(LeadState.REACHED_OUT, LeadState.REACHED_OUT)


def test_sources_for_is_derived_from_the_table() -> None:
    assert sources_for(LeadState.REACHED_OUT) == {LeadState.PENDING}
    assert sources_for(LeadState.PENDING) == set()


def test_reached_out_is_terminal() -> None:
    assert LeadState.REACHED_OUT not in ALLOWED_TRANSITIONS
