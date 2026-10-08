# ADR-0011: imajev family as fourth managed local backend (`imajev`)

Date: 2026-10-07 · Status: accepted

## Context

The owner requested adding the imajev family (GitHub `mohit67890/imajev`,
Apache-2.0) — typed Jev-contract decision models on Qwen3.5 bases (2B/4B/9B),
image-capable (snapdec uses the text-only path). Standing on the board
(2026-09): #1 JevBench v1.4.2.2 and #1 Image JevBench v0.1.3 (imajev-4b).
The §5.4/§10 human gate is satisfied: the owner requested the family
explicitly, and every license in the chain — repo, all three Qwen3.5 bases,
all three adapter repos — is Apache-2.0 OSI. Unlike ADR-0010 there is **no
`trust_remote_code`**: the bases are native transformers + a PEFT adapter.

Research (2026-10-07) verified from the pinned tree:

- **They ship their own server** — `scripts/playground/server.py`
  (FastAPI + uvicorn). Their official benchmarks ran on it with
  `--rotations 1 --calibration calibration.json`. Served on 127.0.0.1.
- The server self-inserts `ROOT/src` + `ROOT/scripts` into `sys.path`
  from `__file__` — launches need **no PYTHONPATH** (deviation from the
  original plan, which assumed one; recorded here).
- `POST /v1/systemone` strips the `"images"` and `"model"` keys and holds
  a per-request lock (serialized inference). Errors answer HTTP 422/500
  `{"error", "detail"}` — our `RemoteSystemOne.system_one`
  `raise_for_status()` plus the daemon catch-all already convert that to
  a 200 fail-closed review envelope (NFR-4, zero code change).
- `GET /v1/models` answers a **flat** body
  `{"model", "adapter", "backend", "loaded", ...}`. There is **no
  `/health`**; uvicorn binds the port only after `build_backend`, so a
  connected port means the model is built — but `/v1/models` can still
  say `loaded:false` while it finishes, so health checks it.
- `scripts/download_model.py` takes a size key (`2b|4b|9b`), downloads
  the pinned base snapshot, and writes a bundle json **relative to the
  CWD** (→ run with `cwd=repo root`). Its `HF_HOME` is a `setdefault`
  with a relative default — our absolute env var wins. It imports only
  stdlib + `huggingface_hub`.
- On CPU (no CUDA) the server loads **float32** (`torch_dtype=bfloat16`
  only on cuda) — the plan's bf16 residency estimate (8/16/24 GB floors)
  was wrong; FP32 weights + calibration + headroom gives **12/24/48 GB**.
  Apple Silicon gets a real MLX fast path (`adapter/mlx` subdir,
  `--backend mlx`, fp16) → unified-memory floors **8/16/32 GB**.

## Decisions

1. **Fourth kind `imajev`, port 8904, shared runtime venv.** Verbatim pin
   table (all resolved via GitHub/HF APIs 2026-10-07):

   | what | pin |
   |---|---|
   | repo tarball | `ccf586d43d2a580319b6535c893668904d909eb9` |
   | adapter `mohit67890/imajev-2b` | `0426f7b1c73804b64fab5802e04f401420ec774c` |
   | adapter `mohit67890/imajev-4b` | `f8d8234cebc6c99065c07731e59716dc0a6e27ab` |
   | adapter `mohit67890/imajev-9b` | `9a69dd0f0d99d465638a9f872ef29ce37c21e888` |
   | base `Qwen/Qwen3.5-2B` | `15852e8c16360a2fea060d615a32b45270f8a8fc` |
   | base `Qwen/Qwen3.5-4B` | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |
   | base `Qwen/Qwen3.5-9B` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` |

   Base bundles live in-tree after download: `artifacts/model.json` (2B),
   `artifacts/model-qwen4b.json` (4B), `artifacts/model-qwen9b.json` (9B) —
   mirroring their `PINNED` dict at the pinned commit.
   `IMAJEV_INSTALL_SPECS` is the **full server closure, all `==`-pinned**
   (resolved via `uv pip install --dry-run` + `uv pip list` against the real
   runtime venv 2026-10-07, zero upgrades, §0.3):
   `transformers==5.18.0, torch==2.14.1, safetensors==0.8.0, peft==0.21.2,
   accelerate==1.15.0, huggingface-hub==1.33.0, fastapi==0.142.2,
   uvicorn==0.54.0, python-multipart==0.0.32, pydantic==2.13.5,
   pillow==12.3.0`. Deltas only would be wrong twice: (a) their server
   imports fastapi/uvicorn/pydantic + PIL via `vision_decision.images` —
   PIL crashed the first real launch (`ModuleNotFoundError: No module
   named 'PIL'`); (b) on a fresh venv where imajev is provisioned before
   laya, peft would pull an **unpinned torch**. The marker gates the
   tarball extract only; `_pip_install` always runs (idempotent no-op
   when the venv satisfies the specs), so a spec list grown across
   releases reaches existing installs. `mlx-vlm==0.7.1` (upstream's own
   pin) is appended **only on darwin** at install time.

2. **Run their server, author no shim** (contrast ADR-0010 §2). Their
   pinned `scripts/playground/server.py` is launched directly with
   explicit absolute flags — `--backend torch|mlx`, `--adapter`,
   `--model-bundle`, `--calibration`, `--rotations 1` (the official
   benchmark flag), `--model-name`, `--host 127.0.0.1`, `--port 8904`.
   All accepted wire deltas are handled snapdec-side:
   - `_healthy`: third fallback `GET /v1/models`, requiring 200 **and**
     `loaded is True` (the other kinds stay 200-on-/health);
   - `advertised_model` + `probe._probe_one`: flat-body fallback
     (`data["model"]` when there is no `data`/`models` list) — keeps
     `snapdec doctor` and probe output honest;
   - 422/500 error shape needs nothing (§ Context).
   `launch()` passes `cwd=_imajev_dir()` because their bundle json is
   resolved relative to the CWD at load time.

3. **Dual download, per model.** `_ensure_imajev_model(py, model)` runs
   after `install_backend` in `provision()`: (a) base via their
   `download_model.py --model <size>` with `HF_HOME=<SNAPDEC_HOME>/runtime/
   imajev-hf` (absolute — their relative setdefault loses) and
   `cwd=repo root`; (b) adapter via `huggingface_hub.snapshot_download`
   (stdlib-plus-hub one-liner) into `runtime/imajev-adapter/<size>` — a
   stable path so `ensure_running` relaunches never re-download. Both
   subprocesses run with `-I`: nothing is importable from the extracted
   tree or the CWD (untrusted-data rule).

   **Placeholder-bundle trap (found at first provision).** Their tarball
   SHIPS `artifacts/model.json` as a placeholder — relative
   `.cache/huggingface/...` path plus a `"note"` key, no snapshot dir.
   Their real script overwrites it with the **absolute**
   `snapshot_download` return path (+ `repository_bytes`). A plain
   `bundle.exists()` gate passed on the placeholder, skipped the ~4.6 GB
   base download, and the server died with `ValueError: Local model
   snapshot is missing` (server.py bundle `is_dir()` check). Fix:
   `_bundle_ready(bundle)` parses the json, rejects empty/`Path("")`
   paths (empty joins to the repo root, which `is_dir()`s true),
   resolves repo-root-relative paths against `_imajev_dir()`, and
   requires the snapshot dir to exist; the base download is verified
   fail-closed with `_bundle_ready` again after the script run.

   **Live download progress.** Both downloads and `_pip_install` run via
   `_run_live()`: stderr inherited (uv wheel progress and tqdm
   `snapshot_download` bars — bytes + speed — render live), stdout
   captured for error tails. Owner request 2026-10-07: on slow links a
   2–5 GB download takes tens of minutes, and a fully captured console
   looks hung. Version-probe subprocesses stay captured (nothing
   useful on stderr).

4. **Untrusted-archive discipline.** The repo tarball extracts into a
   fresh empty directory per pin (`runtime/imajev/<sha8>`),
   `tarfile.extractall(filter="data")` with the GitHub leading component
   stripped, and a `.snapdec-ok` marker (full SHA) is written **only
   after** a successful extract — the marker gates the extract only
   (deps always pip-install; see §1). Their files are never patched
   (ADR-0010 §8 documents the d2 fingerprint workaround; if a Windows
   path bug blocks imajev the same rules apply: proof, minimal wrapper,
   report upstream).

5. **Offline launch env.** `_env("imajev", …)` sets only
   `HF_HUB_OFFLINE=1` (plus the shared telemetry/tokenizer vars) — no
   PYTHONPATH (§ Context), no HF_HOME at launch (the bundle json records
   absolute snapshot paths). ~~Open risk~~ **Resolved empirically at the
   first real provision (2026-10-08)**: launch with `HF_HUB_OFFLINE=1`
   loads the model to `loaded:true` with no hub traffic — no tokenizer
   fetch escapes the bundle. The var stays.

6. **Catalog honesty: third stat scale, never mixed.** imajev entries
   cite the JevBench board (2026-09) tagged `(board 2026-09)`; kev keeps
   held-out breadth-v1 (ADR-0008) and d2 keeps the vendor card. No
   cross-family number exists; tests assert the three scales never blend.
   RAM floors 12/24/48 GB (x86, FP32) and 8/16/32 GB (Apple, MLX fp16);
   `min_vram_gb=0` (CPU path needs no discrete GPU); `slow_on_cpu=True`;
   `mlx_on_apple=True` so the wizard suppresses the slow tag on Apple
   (real MLX path, unlike d2's 0.5.1 amendment). **No star anywhere**
   (`recommended_for=()`): unbenched in snapdec — kev-0.8b keeps the
   Apple star, d2-eos keeps cpu/windows-gpu. Latency strings said "bench
   pending" until the first `snapdec bench` landed
   (`docs/benchmarks/2026-10-08-imajev-2b.md`: CPU p50 14.8 s / p95 35.1 s
   on this PC — serialized FP32; still no star, n=12 mini-v1 is not a
   quality claim).

7. **CLI wiring.** `WIZARD_MAPPING` covers the three variants;
   `init --backend local --model imajev-…` (or a bare name containing
   "imajev") infers kind `imajev` before the kev/laya checks, with a
   `mohit67890/` org fixup; advertised-model adoption accepts the flat
   body (same tuple lists as kev/decision2).

## Consequences

- This PC (i5-13420H, 15.7 GB RAM, Intel UHD, profile `windows-gpu`):
  imajev-2b only (~5 GB download, ~11 GB FP32 resident — tight with a
  host agent running; the floors hide 4b/9b).
- Shared-venv coupling grows: peft/accelerate are new beside
  transformers/torch/safetensors. Escape hatch unchanged (per-kind venvs).
- Serialized inference (their request lock) + CPU latency may exceed the
  60 s local default on the 8-way fan-out; `request_timeout_s` override
  exists if `snapdec bench` demands it.
- **Resurrect window fix (found at first real resurrect, 2026-10-08).**
  `ensure_running` waited a flat 120 s — the imajev FP32 cold load
  (~11 GB resident, minutes on this PC) blows through that, so a daemon
  restart declared the backend dead while it was still loading. Now
  kind-aware: 600 s for kev/d2/imajev (same window `provision()` uses),
  120 s kept for laya, with a 10 s heartbeat on stderr and a
  log-path note when it fails (`lifecycle.start_daemon` swallows the
  bool — stderr is the only visible failure surface). Unit-tested in
  `tests/unit/test_provision.py` (`ensure_running` block).
- **Pid-reuse guard (ADR-0011, same find).** Windows recycles PIDs
  aggressively: a stale state file can point at an unrelated process.
  `lifecycle._pid_alive` now name-checks (`python*` or contains
  `snapdec`) and `stop_daemon` terminates only a pid that passes that
  check — `stop_daemon` never kills an innocent process that inherited
  the daemon's PID. Unit-tested in `tests/unit/test_lifecycle.py`
  (fake psutil via `sys.modules` injection).
- **Environment note (this PC).** Foreground test-harness Bash calls cap
  at 180 s and kill the whole process tree on timeout — detached
  included — which masqueraded as "backend dies silently." Mitigation is
  operational, not code: long provision/resurrect runs go through
  background tasks. Documented here so the failure signature
  (imajev + daemon both vanish, no traceback in `imajev.log`) is not
  re-chased as a snapdec bug.
- Deferred: 4b/9b and Apple benches (replace "pending" strings in the
  release that first measures them), image-path evaluation, upstream
  report of the d2 Windows fingerprint bug (ADR-0010 §8) — separate.
