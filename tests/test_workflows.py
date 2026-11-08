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


def test_both_workflows_read_quota_before_render_and_pass_it():
    for name in ("daily.yml", "live.yml"):
        text = _text(name)
        auth = _step_block(text, "GCP_MONITOR_ADC")
        assert re.search(r"^\s+continue-on-error:\s*true\s*$", auth, re.M), name
        assert "GCP_MONITOR_ADC: ${{ secrets.GCP_MONITOR_ADC }}" in auth, name  # secret only via env:
        assert "umask 077" in auth, name
        quota_step = _step_block(text, "python -m ytops quota")
        assert re.search(r"^\s+continue-on-error:\s*true\s*$", quota_step, re.M), name
        assert 'rm -f "$GOOGLE_APPLICATION_CREDENTIALS"' in quota_step, name  # credential file does not outlive the read
        render_step = _step_block(text, "python -m ytops render")
        assert '--quota "$RUNNER_TEMP/quota.json"' in render_step, name
        assert text.index("GCP_MONITOR_ADC") < text.index("python -m ytops quota") < text.index("python -m ytops render"), name
        assert re.search(r"^\s+id-token:\s*write\s*$", text, re.M), name


def test_tests_run_before_schema_and_collect():
    for name in ("daily.yml", "live.yml"):
        text = _text(name)
        assert "python -m pytest" in text, name
        t = text.index("python -m pytest")
        assert t < text.index("python -m ytops"), name
        if name == "daily.yml":
            assert t < text.index("schema --apply"), name


def test_test_workflow_has_no_secrets():
    assert "secrets." not in _text("test.yml")
