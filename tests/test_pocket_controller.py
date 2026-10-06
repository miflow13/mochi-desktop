"""Pocket orchestration and behavior-ownership regression coverage."""

from __future__ import annotations

import pytest

from mochi.behavior import (
    can_arm_pocket_hover,
    can_start_pocket_offer,
    can_start_pocket_receive,
    can_transition,
)
from mochi.pocket import PocketMutation, make_saved_image_item, make_text_item
from mochi.pocket_controller import PocketController
from mochi.state import MochiState


class _Store:
    def __init__(self, *, fail_add: bool = False) -> None:
        self.items = []
        self.fail_add = fail_add
        self.events: list[str] = []

    def load(self):
        return list(self.items)

    def add_items(self, current, incoming):
        self.events.append("persist")
        if self.fail_add:
            raise OSError("disk full")
        self.items = [*incoming, *current]
        return PocketMutation(tuple(self.items))

    def remove(self, current, item_id):
        self.events.append("remove")
        self.items = [item for item in current if item.id != item_id]
        return list(self.items)

    def clear(self, current):
        self.events.append("clear")
        self.items = []
        return []

    def save_raw_image(self, png_bytes):
        self.events.append("save-image")
        return make_saved_image_item("/tmp/managed-pocket-image.png")


class _Interaction:
    def __init__(self, state: MochiState = MochiState.IDLE) -> None:
        self.state = state
        self.events: list[str] = []
        self.feedback: list[str] = []

    def current_state(self) -> MochiState:
        return self.state

    def cancel_walk(self) -> None:
        self.events.append("cancel-walk")
        self.state = MochiState.IDLE

    def cancel_ambient(self) -> None:
        self.events.append("cancel-ambient")
        self.state = MochiState.IDLE

    def transition(self, state: MochiState) -> bool:
        self.events.append(f"transition:{state.name}")
        if not can_transition(self.state, state):
            return False
        self.state = state
        return True

    def play(self, name: str, after: str | None = None) -> None:
        self.events.append(f"play:{name}:{after}")

    def mark_interaction(self) -> None:
        self.events.append("mark-interaction")

    def resume_ambient(self) -> None:
        self.events.append("resume-ambient")

    def show_feedback(self, message: str) -> None:
        self.feedback.append(message)


def _controller(store: _Store, interaction: _Interaction) -> PocketController:
    return PocketController(
        store,
        current_state=interaction.current_state,
        cancel_walk=interaction.cancel_walk,
        cancel_ambient=interaction.cancel_ambient,
        transition=interaction.transition,
        play_animation=interaction.play,
        mark_interaction=interaction.mark_interaction,
        resume_ambient=interaction.resume_ambient,
        show_feedback=interaction.show_feedback,
    )


def test_receive_persists_before_one_reaction_for_the_whole_batch() -> None:
    store = _Store()
    interaction = _Interaction()
    events: list[str] = []
    store.events = events
    interaction.events = events
    controller = _controller(store, interaction)
    first = make_text_item("first", received_at=2)
    second = make_text_item("second", received_at=1)

    assert controller.receive([first, second]) is True

    assert events == [
        "persist",
        "cancel-ambient",
        "transition:EXCITED",
        "mark-interaction",
        "play:pocket_grab:idle",
    ]
    assert controller.items == (first, second)
    assert controller.count == 2


def test_hover_claims_presentation_once_and_loops_open_mouth_animation() -> None:
    store = _Store()
    interaction = _Interaction(MochiState.WATCHING)
    controller = _controller(store, interaction)

    assert controller.begin_hover() is True
    assert controller.begin_hover() is True

    assert interaction.events == [
        "cancel-ambient",
        "transition:EXCITED",
        "play:pocket_hover:None",
    ]
    assert controller.hover_active is True
    assert store.events == []


def test_hover_leave_restores_idle_and_resumes_ambient_once() -> None:
    store = _Store()
    interaction = _Interaction()
    controller = _controller(store, interaction)
    assert controller.begin_hover()
    interaction.events.clear()

    controller.end_hover()
    controller.end_hover()

    assert interaction.events == [
        "transition:IDLE",
        "play:idle:None",
        "resume-ambient",
    ]
    assert controller.hover_active is False


def test_hover_leave_does_not_overwrite_a_new_protected_owner() -> None:
    store = _Store()
    interaction = _Interaction()
    controller = _controller(store, interaction)
    assert controller.begin_hover()
    interaction.events.clear()
    interaction.state = MochiState.SLEEPING

    controller.end_hover()

    assert interaction.events == []
    assert interaction.state is MochiState.SLEEPING
    assert controller.hover_active is False


def test_repeated_hover_rejects_after_a_new_protected_owner_takes_over() -> None:
    store = _Store()
    interaction = _Interaction()
    controller = _controller(store, interaction)
    assert controller.begin_hover()
    interaction.events.clear()
    interaction.state = MochiState.SLEEPING

    assert controller.begin_hover() is False

    assert interaction.events == []
    assert interaction.state is MochiState.SLEEPING
    assert controller.hover_active is False


def test_drop_after_protected_takeover_releases_hover_without_writing() -> None:
    store = _Store()
    interaction = _Interaction()
    controller = _controller(store, interaction)
    assert controller.begin_hover()
    interaction.events.clear()
    interaction.state = MochiState.SLEEPING

    assert controller.receive([make_text_item("note")]) is False

    assert store.events == []
    assert interaction.events == []
    assert interaction.feedback == ["My paws are full"]
    assert controller.hover_active is False


@pytest.mark.parametrize(
    "state",
    [
        MochiState.SLEEPING,
        MochiState.WAKING,
        MochiState.PICKUP,
        MochiState.DRAGGED,
        MochiState.DROPPING,
        MochiState.FEDORA,
        MochiState.EXCITED,
        MochiState.EATING,
        MochiState.HEART,
        MochiState.BOUNCING,
        MochiState.SQUISHING,
    ],
)
def test_hover_rejects_protected_or_direct_owned_states(state: MochiState) -> None:
    store = _Store()
    interaction = _Interaction(state)
    controller = _controller(store, interaction)

    assert controller.begin_hover() is False

    assert interaction.events == []
    assert controller.hover_active is False
    assert store.events == []


def test_hovered_drop_persists_before_short_closing_tail() -> None:
    store = _Store()
    interaction = _Interaction()
    events: list[str] = []
    store.events = events
    interaction.events = events
    controller = _controller(store, interaction)
    assert controller.begin_hover()
    events.clear()

    assert controller.receive([make_text_item("note")]) is True

    assert events == [
        "persist",
        "mark-interaction",
        "play:pocket_finish:idle",
    ]
    assert controller.hover_active is False


def test_hovered_persistence_failure_restores_normal_presentation() -> None:
    store = _Store(fail_add=True)
    interaction = _Interaction()
    controller = _controller(store, interaction)
    assert controller.begin_hover()
    interaction.events.clear()

    assert controller.receive([make_text_item("note")]) is False

    assert interaction.events == [
        "transition:IDLE",
        "play:idle:None",
        "resume-ambient",
    ]
    assert interaction.feedback == ["I couldn't hold that"]
    assert controller.hover_active is False


@pytest.mark.parametrize(
    "state",
    [
        MochiState.IDLE,
        MochiState.WALKING,
        MochiState.BLINKING,
        MochiState.IDLE_EMOTE,
        MochiState.COMPUTER,
        MochiState.TYPING,
        MochiState.WATCHING,
        MochiState.DANCING,
        MochiState.SEARCHING,
    ],
)
def test_receive_can_claim_idle_and_ambient_states(state: MochiState) -> None:
    store = _Store()
    interaction = _Interaction(state)

    assert _controller(store, interaction).receive([make_text_item("note")])

    assert store.events == ["persist"]
    assert interaction.state is MochiState.EXCITED
    assert can_start_pocket_receive(state)
    assert can_transition(state, MochiState.EXCITED)


@pytest.mark.parametrize(
    "state",
    [
        MochiState.SLEEPING,
        MochiState.WAKING,
        MochiState.PICKUP,
        MochiState.DRAGGED,
        MochiState.DROPPING,
        MochiState.FEDORA,
        MochiState.EXCITED,
        MochiState.EATING,
        MochiState.HEART,
        MochiState.BOUNCING,
        MochiState.SQUISHING,
    ],
)
def test_receive_rejects_protected_or_direct_owned_states(
    state: MochiState,
) -> None:
    store = _Store()
    interaction = _Interaction(state)
    controller = _controller(store, interaction)

    assert controller.receive([make_text_item("note")]) is False

    assert store.events == []
    assert interaction.events == []
    assert interaction.feedback == ["My paws are full"]
    assert not can_start_pocket_receive(state)


def test_busy_receive_rejects_without_writing_or_reacting() -> None:
    store = _Store()
    interaction = _Interaction()
    controller = _controller(store, interaction)
    controller._busy = True

    assert controller.receive([make_text_item("note")]) is False

    assert store.events == []
    assert interaction.events == []
    assert interaction.feedback == ["My paws are full"]


def test_raw_image_is_saved_then_persisted_before_one_reaction() -> None:
    store = _Store()
    interaction = _Interaction()
    events: list[str] = []
    store.events = events
    interaction.events = events
    controller = _controller(store, interaction)

    assert controller.receive_image(b"png-data") is True

    assert events == [
        "save-image",
        "persist",
        "cancel-ambient",
        "transition:EXCITED",
        "mark-interaction",
        "play:pocket_grab:idle",
    ]
    assert controller.count == 1


def test_busy_raw_image_receive_does_not_create_a_managed_file() -> None:
    store = _Store()
    interaction = _Interaction(MochiState.SLEEPING)
    controller = _controller(store, interaction)

    assert controller.receive_image(b"png-data") is False

    assert store.events == []
    assert interaction.feedback == ["My paws are full"]


def test_persistence_failure_keeps_live_items_and_skips_reaction() -> None:
    existing = make_text_item("existing", received_at=1)
    store = _Store(fail_add=True)
    store.items = [existing]
    interaction = _Interaction()
    controller = _controller(store, interaction)

    assert controller.receive([make_text_item("new", received_at=2)]) is False

    assert controller.items == (existing,)
    assert interaction.events == []
    assert interaction.feedback == ["I couldn't hold that"]
    assert controller.busy is False


def test_remove_persists_then_publishes_count_change() -> None:
    item = make_text_item("remove me")
    store = _Store()
    store.items = [item]
    interaction = _Interaction()
    changed: list[int] = []
    controller = PocketController(
        store,
        current_state=interaction.current_state,
        cancel_walk=interaction.cancel_walk,
        cancel_ambient=interaction.cancel_ambient,
        transition=interaction.transition,
        play_animation=interaction.play,
        mark_interaction=interaction.mark_interaction,
        resume_ambient=interaction.resume_ambient,
        show_feedback=interaction.show_feedback,
        on_changed=lambda items: changed.append(len(items)),
    )

    assert controller.remove(item.id) is True

    assert store.events == ["remove"]
    assert controller.items == ()
    assert controller.count == 0
    assert changed == [0]


def test_failed_remove_preserves_live_item() -> None:
    item = make_text_item("keep me")
    store = _Store()
    store.items = [item]
    interaction = _Interaction()
    controller = _controller(store, interaction)

    def fail_remove(current, item_id):
        raise OSError("read only")

    store.remove = fail_remove

    assert controller.remove(item.id) is False
    assert controller.items == (item,)
    assert interaction.feedback == ["I couldn't update Pocket"]


def test_pocket_reaction_uses_normal_idle_completion_contract() -> None:
    store = _Store()
    interaction = _Interaction()
    controller = _controller(store, interaction)

    assert controller.receive([make_text_item("note")])

    assert "play:pocket_grab:idle" in interaction.events
    assert can_transition(MochiState.EXCITED, MochiState.IDLE)



def test_clear_all_persists_then_publishes_empty_count() -> None:
    store = _Store()
    store.items = [make_text_item("one"), make_text_item("two")]
    interaction = _Interaction()
    changed: list[int] = []
    controller = PocketController(
        store,
        current_state=interaction.current_state,
        cancel_walk=interaction.cancel_walk,
        cancel_ambient=interaction.cancel_ambient,
        transition=interaction.transition,
        play_animation=interaction.play,
        mark_interaction=interaction.mark_interaction,
        resume_ambient=interaction.resume_ambient,
        show_feedback=interaction.show_feedback,
        on_changed=lambda items: changed.append(len(items)),
    )

    assert controller.clear_all() is True

    assert store.events == ["clear"]
    assert controller.items == ()
    assert controller.count == 0
    assert changed == [0]


def test_clear_all_empty_pocket_is_successful_noop() -> None:
    store = _Store()
    interaction = _Interaction()
    controller = _controller(store, interaction)

    assert controller.clear_all() is True

    assert store.events == []
    assert controller.items == ()


def test_failed_clear_all_preserves_live_items_and_reports_feedback() -> None:
    item = make_text_item("keep me")
    store = _Store()
    store.items = [item]
    interaction = _Interaction()
    controller = _controller(store, interaction)

    def fail_clear(current):
        raise OSError("read only")

    store.clear = fail_clear

    assert controller.clear_all() is False
    assert controller.items == (item,)
    assert interaction.feedback == ["I couldn't update Pocket"]


HOVER_ARM_STATES = {
    MochiState.IDLE,
    MochiState.BLINKING,
    MochiState.IDLE_EMOTE,
    MochiState.HEART,
    MochiState.COMPUTER,
    MochiState.TYPING,
    MochiState.WATCHING,
    MochiState.DANCING,
    MochiState.SEARCHING,
    MochiState.SLEEPING,
    MochiState.WAKING,
}


@pytest.mark.parametrize("state", tuple(MochiState))
def test_hover_tray_arms_only_from_calm_ambient_or_sleep_states(
    state: MochiState,
) -> None:
    assert can_arm_pocket_hover(state) is (state in HOVER_ARM_STATES)


@pytest.mark.parametrize("state", tuple(MochiState))
def test_offer_may_replace_receive_states_and_the_hover_heart(
    state: MochiState,
) -> None:
    expected = can_start_pocket_receive(state) or state is MochiState.HEART
    assert can_start_pocket_offer(state) is expected


def test_offer_cancels_the_hover_heart_before_claiming_excited() -> None:
    store = _Store()
    interaction = _Interaction(MochiState.HEART)
    controller = _controller(store, interaction)

    assert controller.begin_offer() is True

    assert interaction.events == [
        "cancel-ambient",
        "transition:EXCITED",
        "mark-interaction",
        "play:pocket_offer:idle",
    ]
    assert interaction.state is MochiState.EXCITED
    assert store.events == []
    assert interaction.feedback == []


def test_offer_cancels_a_walk_instead_of_an_emote() -> None:
    interaction = _Interaction(MochiState.WALKING)
    controller = _controller(_Store(), interaction)

    assert controller.begin_offer() is True

    assert interaction.events[0] == "cancel-walk"
    assert "cancel-ambient" not in interaction.events


@pytest.mark.parametrize(
    "state",
    (
        MochiState.SLEEPING,
        MochiState.WAKING,
        MochiState.PICKUP,
        MochiState.DRAGGED,
        MochiState.DROPPING,
        MochiState.FEDORA,
        MochiState.EATING,
        MochiState.EXCITED,
        MochiState.BOUNCING,
        MochiState.SQUISHING,
    ),
)
def test_offer_never_claims_protected_or_direct_owned_states(
    state: MochiState,
) -> None:
    interaction = _Interaction(state)
    controller = _controller(_Store(), interaction)

    assert controller.begin_offer() is False

    assert interaction.events == []
    assert interaction.state is state


def test_offer_is_skipped_while_a_drag_in_owns_pocket() -> None:
    interaction = _Interaction(MochiState.IDLE)
    controller = _controller(_Store(), interaction)
    assert controller.begin_hover() is True
    interaction.events.clear()

    assert controller.begin_offer() is False
    assert interaction.events == []


def test_rejected_offer_transition_plays_nothing() -> None:
    interaction = _Interaction(MochiState.IDLE)

    def reject(state: MochiState) -> bool:
        interaction.events.append(f"transition:{state.name}")
        return False

    interaction.transition = reject
    controller = _controller(_Store(), interaction)

    assert controller.begin_offer() is False
    assert interaction.events == ["cancel-ambient", "transition:EXCITED"]
