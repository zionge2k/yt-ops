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



def test_daily_keep_alive_enables_both_workflows():
    daily = _text("daily.yml")
    assert "workflows/daily.yml/enable" in daily
    assert "workflows/live.yml/enable" in daily


def test_live_alert_step_tolerates_quota_only_failures():
    live = _text("live.yml")
    assert "quota_exhausted=1" in live and "collect.log" in live


def _step_block(text: str, marker: str) -> str:
    """The workflow step (from its `- name:` / `- run:` line to the next step) containing `marker`."""
    for block in re.split(r"(?m)^      - (?=\S)", text):
        if marker in block:
            return block
    raise AssertionError(marker)


def test_live_collect_step_keeps_python_exit_code():
    # `run:` without `shell:` is `bash -e`: a pipe to tee would hide python's exit code
    block = _step_block(_text("live.yml"), "--only live")
    assert re.search(r"^\s+shell:\s*bash\s*$", block, re.M) or "set -o pipefail" in block


def test_every_piped_python_step_has_pipefail():
    for name in ("live.yml", "daily.yml"):
        for block in re.split(r"(?m)^      - (?=\S)", _text(name)):
            if re.search(r"python -m ytops [^\n]*\|", block):
                assert re.search(r"^\s+shell:\s*bash\s*$", block, re.M) or "set -o pipefail" in block, name
