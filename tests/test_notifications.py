"""Unit validation for notification outbox processing and recovery."""
import pytest

from itoms.services import notifications


def test_process_in_app_batch_only_completes_claimed_items(monkeypatch):
    monkeypatch.setattr(
        notifications, "claim_outbox_batch",
        lambda **kwargs: [{"outbox_id": 10}, {"outbox_id": 11}],
    )
    completed = []
    monkeypatch.setattr(
        notifications, "complete_outbox_item",
        lambda **kwargs: completed.append(kwargs),
    )
    assert notifications.process_in_app_outbox_batch(batch_size=2) == 2
    assert [item["outbox_id"] for item in completed] == [10, 11]
    assert all(item["success"] is True for item in completed)


def test_dead_letter_replay_requires_permission_before_database(monkeypatch):
    monkeypatch.setattr(notifications, "has_permission", lambda *_: False)
    monkeypatch.setattr(
        notifications, "get_connection",
        lambda: pytest.fail("database must not be opened for unauthorized replay"),
    )
    with pytest.raises(notifications.NotificationError, match="Not authorized"):
        notifications.replay_dead_letter(actor_employee_id=1, outbox_id=10)
