import json
from datetime import UTC, datetime
from pathlib import Path

from onespread.dashboard import journal_snapshot
from onespread.engine import Journal
from onespread.replay import generate_replay


def test_replay_exercises_real_risk_and_exit_lifecycle() -> None:
    replay = generate_replay()
    scenarios = {s["id"]: s for s in replay["scenarios"]}
    assert scenarios["entry"]["events"][-1]["action"] == "DRY_RUN_PROPOSAL"
    assert scenarios["veto"]["events"][-1]["reasons"] == ["stale_or_future_option_quote"]
    assert [e["action"] for e in scenarios["exit"]["events"]] == [
        "ENTRY_INTENT",
        "ENTRY_SUBMITTED",
        "HOLD",
        "EXIT_SUBMITTED",
        "CLOSED",
    ]
    assert all(
        e["synthetic"] and e["mode"] == "replay" for s in replay["scenarios"] for e in s["events"]
    )
    assert "client_order_id" not in json.dumps(replay)


def test_journal_view_is_read_only_and_filters_internal_fields(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    journal = Journal(path)
    journal.record(
        {
            "action": "WAIT",
            "reasons": ["market_closed"],
            "client_order_id": "private-order",
            "api_key": "DO-NOT-EXPOSE",
        },
        datetime.now(UTC),
    )
    journal.db.close()
    before = path.read_bytes()
    result = journal_snapshot(path)
    assert result["events"][0]["action"] == "WAIT"
    assert "private-order" not in json.dumps(result)
    assert "DO-NOT-EXPOSE" not in json.dumps(result)
    assert path.read_bytes() == before


def test_missing_journal_does_not_create_a_database(tmp_path: Path) -> None:
    path = tmp_path / "absent.sqlite3"
    assert journal_snapshot(path)["events"] == []
    assert not path.exists()
