"""d2serve shim unit tests (ADR-0010 §8 fingerprint compat + wire contract).

The shim's module-level imports are stdlib-only, so it imports safely under
`tmp_home`; torch/transformers only load inside `_load` (runtime venv).
"""

from __future__ import annotations

import builtins
import hashlib
import json
import sys
import threading
import types
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from snapdec.runtime import d2serve


def _manifest_like_identity() -> dict[str, str]:
    """Backslash-keyed identity exactly as the vendored bug produces it."""
    return {
        "model_sha256": "wrong-composite",
        "files_sha256": {
            "backbone\\model-00001-of-00002.safetensors": "a" * 64,
            "backbone\\model-00002-of-00002.safetensors": "b" * 64,
            "decision_config.json": "c" * 64,
        },
    }


class TestPosixFingerprint:
    def test_normalizes_keys_and_recomputes_composite(self) -> None:
        identity = _manifest_like_identity()

        def vendored(path: object, source: object = None) -> dict[str, str]:
            return identity  # simulates infer.py:296 backslash keys

        wrapped = d2serve._posix_fingerprint(vendored)
        out = wrapped("ignored")
        expected_files = {key.replace("\\", "/"): value
                          for key, value in identity["files_sha256"].items()}
        expected_composite = hashlib.sha256(
            d2serve._canonical(expected_files).encode("utf-8")).hexdigest()
        assert out["files_sha256"] == expected_files
        assert out["model_sha256"] == expected_composite
        assert out["model_sha256"] != "wrong-composite"

    def test_idempotence_marker_blocks_double_wrap(self) -> None:
        wrapped_once = d2serve._posix_fingerprint(lambda *a, **k: {})
        assert wrapped_once._snapdec_posix is True
        # _patch_fingerprint_modules must not wrap an already-marked function
        module = types.ModuleType("fake._vendor.dev2model.infer")
        module.checkpoint_fingerprint = wrapped_once
        sys.modules["fake._vendor.dev2model.infer"] = module
        try:
            assert d2serve._patch_fingerprint_modules() == 0
        finally:
            del sys.modules["fake._vendor.dev2model.infer"]


class TestFingerprintCompat:
    def test_import_hook_patches_loaded_module_and_restores(self) -> None:
        module = types.ModuleType("fake._vendor.dev2model.infer")
        calls: list[object] = []

        def vendored(path: object, source: object = None) -> dict[str, object]:
            calls.append(path)
            return _manifest_like_identity()

        module.checkpoint_fingerprint = vendored
        sys.modules["fake._vendor.dev2model.infer"] = module
        original_import = builtins.__import__
        try:
            with d2serve._fingerprint_compat():
                import json  # noqa: F401 — any import triggers the rescan

                patched = module.checkpoint_fingerprint
                assert patched is not vendored
                assert patched._snapdec_posix is True
                # wrapped call still routes through the original
                out = patched("p")
                assert calls == ["p"]
                assert "\\" not in "".join(out["files_sha256"])
            assert module.checkpoint_fingerprint is patched  # stays patched
            assert builtins.__import__ is original_import  # hook removed
        finally:
            sys.modules.pop("fake._vendor.dev2model.infer", None)
            builtins.__import__ = original_import


class TestWireContract:
    def test_system_one_called_keyword_only(self) -> None:
        """Regression: Decision2Model.system_one is keyword-only; a positional
        call raised TypeError on every request once loading succeeded."""
        seen: dict[str, object] = {}
        lock = threading.Lock()

        class FakeModel:
            def system_one(self, *, state: object, questions: object) -> dict[str, object]:
                with lock:
                    seen["state"] = state
                    seen["questions"] = questions
                return {"answers": {"q1": {"type": "choice", "choice": "yes"}},
                        "usage": {"input_tokens": 3, "output_tokens": 0}}

        handler = d2serve.make_handler(FakeModel(), "vllm-sr/Decision-2.0-Eos-0.8B", 1)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = srv.server_address[1]
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"state": "the state", "questions": {
                "q1": {"type": "choice", "instructions": "pick",
                       "criteria": {"yes": "y", "no": "n"}}}}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/systemone", data=body,
                headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                out = json.loads(resp.read())
            assert resp.status == 200
            assert out["model"] == "vllm-sr/Decision-2.0-Eos-0.8B"
            assert out["answers"]["q1"]["choice"] == "yes"
            assert seen["state"] == "the state"
            assert seen["questions"] == {"q1": {"type": "choice",
                                                "instructions": "pick",
                                                "criteria": {"yes": "y", "no": "n"}}}
        finally:
            srv.shutdown()
            srv.server_close()

    def test_coerce_state_passthrough_and_dict(self) -> None:
        assert d2serve._coerce_state({"state": "text"}) == "text"
        assert json.loads(d2serve._coerce_state({"state": {"k": 1}})) == {"k": 1}
        assert d2serve._coerce_state({}) == ""


def test_canonical_matches_vendored_contract() -> None:
    value = {"b": [1, 2.5, "ü"], "a": {"n": None, "t": True}}
    assert d2serve._canonical(value) == json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False)
    with pytest.raises(ValueError):  # allow_nan=False
        d2serve._canonical(float("nan"))
