"""Static checks on the GitHub workflow files (no YAML library in requirements: small regexes)."""
import re
from pathlib import Path

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _text(name: str) -> str:
    return (WF / name).read_text(encoding="utf-8")


def _group(text: str) -> str:
    return re.search(r"^concurrency:\s*\n\s+group:\s*(\S+)", text, re.M).group(1)


def test_daily_and_live_do_not_share_concurrency_group():
    assert _group(_text("daily.yml")) != _group(_text("live.yml"))


def test_live_runs_every_two_hours():
    crons = re.findall(r"^\s*-\s*cron:\s*'([^']+)'", _text("live.yml"), re.M)
    assert crons == ["0 */2 * * *"]


def test_live_does_not_apply_schema():
    assert "schema --apply" not in _text("live.yml")
    assert "schema --apply" in _text("daily.yml")

