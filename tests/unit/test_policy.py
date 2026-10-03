from __future__ import annotations

from snapdec.decisions.envelope import failure_envelope, make_envelope
from snapdec.decisions.policy import apply_decision, decide


def test_auto_when_confident_and_decisive():
    d, top, margin = decide({"a": 0.93, "b": 0.07})
    assert d == "auto" and top > 0.9 and margin > 0.8


def test_review_on_low_margin():
    assert decide({"a": 0.55, "b": 0.45})[0] == "review"


def test_review_when_truncated_or_empty():
    assert decide({"a": 0.99}, truncated=True)[0] == "review"
    assert decide({})[0] == "review"
    assert decide({"a": 0.99}, backend_ready=False)[0] == "review"


def test_safety_asymmetric_thresholds():
    # 0.86 ≥ 0.85 normally auto, but safety-class raises the bar → review
    assert decide({"a": 0.86, "b": 0.14})[0] == "auto"
    assert decide({"a": 0.86, "b": 0.14}, safety=True)[0] == "review"
    assert decide({"a": 0.95, "b": 0.05}, safety=True)[0] == "auto"


def test_apply_decision_decorates_row():
    row = apply_decision({"id": "x", "probabilities": {"yes": 0.9, "no": 0.1}})
    assert row["decision"] == "auto"
    assert row["probability"] == 0.9
    assert abs(row["margin"] - 0.8) < 1e-9


def test_envelope_summary_counts():
    env = make_envelope(
        [{"id": "1", "decision": "auto"}, {"id": "2", "decision": "review"}],
        backend={"name": "mock"},
    )
    assert env["summary"] == {"items": 2, "auto": 1, "review": 1}


def test_failure_envelope_never_empty_reason():
    env = failure_envelope("warming", "wait")
    assert env["decision"] == "review" and env["reason"] == "warming"


def test_mock_backend_deterministic():
    from snapdec.backends.mock import MockBackend
    from snapdec.decisions.envelope import SystemOneRequest

    be = MockBackend()
    req = SystemOneRequest(state="same input",
                           questions={"q": {"type": "choice",
                                            "criteria": {"a": "", "b": ""}}})
    r1 = be.system_one(req).answers["q"].probabilities
    r2 = be.system_one(req).answers["q"].probabilities
    assert r1 == r2
    assert abs(sum(r1.values()) - 1.0) < 1e-6
