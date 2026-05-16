import json

from thoth.app import run


def test_run_returns_zero_and_emits_json(capsys: object) -> None:
    assert run(message="smoke", session_id="sess_smoke") == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert payload["status"] == "success"
    assert payload["request_id"].startswith("req_")
