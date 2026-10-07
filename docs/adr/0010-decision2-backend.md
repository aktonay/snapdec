# ADR-0010: Decision 2.0 family as third managed local backend (`decision2`)

Date: 2026-10-06 · Status: accepted

## Context

The owner requested adding the "Decision 2.0" family (HF org `vllm-sr`,
Apache-2.0, announced 2026-10-03) after vendor cards claimed it beats
Jev/Kev/Laya per size class. Research (2026-10-06) verified:

- The repos ship a `trust_remote_code` modeling file exposing
  `model.system_one(state, questions)` but **no HTTP server**.
- The answer wire format matches our §4.5 System One contract exactly
  (choice/noul/score/probabilities/confidence/legend, error answers) —
  confirmed from `decision2/_vendor/dev2model/infer.py`. Zero daemon or
  `RemoteSystemOne` protocol changes needed.
- The shared runtime venv (laya[serve]) already satisfies the pinned
  transformers/torch/safetensors versions, so a second venv would be pure
  duplication today.

This is a deliberate deviation from SYSONE_ARCHITECTURE.md §5.4/§10
(no `trust_remote_code`, OSI-only, human gate for network calls). The
human gate is satisfied: the owner requested the family explicitly, and
Apache-2.0 is OSI-approved.

## Decisions

1. **Third kind `decision2`, port 8903, shared runtime venv.**
   `provision.py` gains `DECISION2_PORT = 8903`, `D2_REPOS` (per-repo
   pinned commit SHAs, resolved via the HF API 2026-10-06 — repo ids are
   case-sensitive), and `D2_INSTALL_SPECS = ("transformers==5.18.0",
   "torch==2.14.1", "safetensors==0.8.0")` — idempotent against the
   existing venv (§0.3: everything pinned, never "latest").
   `_port()` becomes public `port_for(kind)`; `_default_model(kind)`
   replaces the hardcoded `"english"` fallback so daemon resurrection
   after a crash relaunches the configured decision2 model.

2. **We author the serve shim: `runtime/d2serve.py`.** stdlib
   `ThreadingHTTPServer` on **127.0.0.1 only**. It is materialized into
   `SNAPDEC_HOME/runtime/d2serve.py` (idempotent copy) because
   `ensure_running` relaunches via `_launch_cmd` without reinstalling.
   Design points: bind **after** model load (health ⇒ weights resident),
   `Semaphore(2)` lanes around `system_one` (torch CPU ops release the
   GIL), `/v1/models` + `/models` + `/health` + `/healthz` endpoints,
   inference errors answered as HTTP 200 `{"answers": {}, "error": ...}`
   — fail-closed, mirroring the daemon (NFR-4). Answers pass through
   verbatim.

3. **trust_remote_code load order (the §5.4/§10 deviation).**
   Two-phase load: (a) `snapshot_download(repo, revision=pin)` — the only
   network phase, and their loader verifies `MODEL_MANIFEST` SHA-256
   internally; (b) set `HF_HUB_OFFLINE=1` **before** importing
   transformers; (c) `AutoModel.from_pretrained(..., revision=pin,
   trust_remote_code=True)` runs with the hub disabled — pinned cache
   only, no post-snapshot fetch. Residual risk (pinned commit is
   malicious) accepted by the owner's explicit request; per-repo SHA pins
   make it auditable. Inference-only: the model never generates, only
   `system_one`.

4. **Catalog honesty: two stat scales, never mixed.** kev entries cite
   held-out breadth-v1 numbers (ADR-0008); Decision 2.0 entries cite
   vendor-card numbers tagged `(vllm-sr card 2026-10)` on their own
   index. No cross-family composite number exists in the catalog.
   Latency strings say "CPU: bench pending" until `snapdec bench`
   commits measurements under `docs/benchmarks/` (AGENTS.md: claims come
   from bench output, not adjectives). RAM floors are FP32 residency +
   headroom: 6/8/10/20 GB for Kai/Eos/Sol/Nox. `runs_on_apple=False`
   (MPS path unvalidated). Lux-9B and Vega-27B cards were never fetched —
   omitted rather than guessed.

5. **Eos-only star, two-star consequence accepted.**
   `recommended_for=("cpu", "windows-gpu")` on `d2-eos` only (it
   dominates Kai on the card). laya-en keeps its star, so low-end
   profiles show two stars; the wizard default stays laya-en because
   "first starred wins" (`_select_backend`). Documented here so the
   double star is a decision, not an accident.

6. **Timeout bug fixed in the same change.** `RemoteSystemOne` defaulted
   to `timeout=5.0` and `ipc._client` hardcoded `10.0`; the 8-way CLI
   fan-out (§4.6) against a CPU-served model exceeded 5 s and produced
   silent failure envelopes. New `Config.request_timeout_s` (0 = default)
   + `effective_request_timeout()`: explicit >0 override wins; else 60 s
   for `local-managed`/`local-server` backends, 5 s for hosted. Threaded
   through `daemon.build_backend`, `ipc._client`, and `_canary`.

7. **`--backend local` inference + wizard mapping.** `WIZARD_MAPPING`
   (module constant, wizard + non-interactive path share it) covers the
   four d2 variants; `init --backend local --model vllm-sr/…` (or a bare
   name containing kai/eos/sol/nox) infers `decision2`, org-prefixed.

8. **Upstream Windows fingerprint bug worked around in the shim (not
   patched around the verification).** The vendored
   `checkpoint_fingerprint` (`_vendor/dev2model/infer.py:296`) builds its
   `files_sha256` keys with `str(file.relative_to(path))`, which emits `\`
   separators on Windows, while the published `MODEL_MANIFEST.json` was
   hashed on POSIX with `/` separators — so the composite `model_sha256`
   never matches and `QwenDecision.load` raises
   `ValueError("Model identity differs from the scored checkpoint")` on
   every Windows load. Proof (Eos @ `3594047d`, 2026-10-06): all 6
   per-file SHA-256 digests match the manifest; the backslash-keyed
   composite is
   `7aa5272a9814966a893e6ed0944c7a60ecc210510d33989d839af81387968023`
   (mismatch), the POSIX-keyed composite is
   `d97127991870ae202017a99eb496bdc56a62afd038594a67febfab0aea9d76fe`
   (manifest exact match). Mitigation in `d2serve.py`: while
   `AutoModel.from_pretrained` runs, an import hook patches the vendored
   `checkpoint_fingerprint`/`label_fingerprint`/`dec_fingerprint` with a
   wrapper that still calls the original (every per-file digest is still
   read and hashed — tamper detection untouched), then normalizes the
   dict-key separators to `/` and recomputes the composite before the
   vendored loader compares it. The hook is removed in `finally`; only
   key spelling and the composite over it change. To report upstream to
   `vllm-sr` (their Windows users hit this on every full-checkpoint
   load); remove the workaround when a fixed revision is pinned.

## Consequences

- This PC (i5-13420H, 15.7 GB RAM, Intel UHD, profile `windows-gpu`):
  Kai + Eos + Sol selectable, Nox hidden (min_ram 20 GB).
- Shared-venv coupling: a future kev tarball requiring a different torch
   would collide; per-kind venvs are the escape hatch.
- Deferred: Apple/MPS validation for the family; Lux/Vega catalog entries
  pending card verification; batching in the shim (Phase 2 concern).
- Bench numbers replace "pending" strings in the catalog in the same
  release that first measures them.
