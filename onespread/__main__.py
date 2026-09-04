"""Run from the repository with uv run python -m onespread."""

import argparse
import fcntl
import json
import time

from onespread.adapters import ROOT, Alpaca, Featherless, Settings
from onespread.domain import Calendar
from onespread.engine import Engine, Journal


def main() -> None:
    parser = argparse.ArgumentParser(description="OneSpread paper-only agent; dry run by default")
    parser.add_argument(
        "--paper", action="store_true", help="Enable paper order submissions/cancellations"
    )
    parser.add_argument(
        "--cycles", type=int, default=1, help="Bounded number of decision cycles (1-288)"
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="Seconds between cycles (minimum 30)"
    )
    args = parser.parse_args()
    if not 1 <= args.cycles <= 288 or args.interval < 30:
        parser.error("Use 1-288 cycles and interval >=30 seconds")
    private = ROOT / ".local/onespread"
    private.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    with (private / "agent.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "Another OneSpread agent is already running.\n")
        journal = Journal(private / "journal.sqlite3")
        for cycle in range(args.cycles):
            path = private / "calendar.json"
            calendar = Calendar.model_validate_json(path.read_text()) if path.exists() else None
            engine = Engine(
                Alpaca(settings),
                Featherless(settings),
                journal,
                execute=args.paper,
                calendar=calendar,
            )
            report = engine.run()
            latest = private / "latest.json"
            latest.write_text(json.dumps(report, indent=2))
            latest.chmod(0o600)
            print(
                json.dumps({k: v for k, v in report.items() if k not in {"evidence"}}, indent=2),
                flush=True,
            )
            if cycle + 1 < args.cycles:
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
