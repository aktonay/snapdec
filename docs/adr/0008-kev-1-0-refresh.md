# ADR-0008: Kev 1.0 catalog refresh + Apple Silicon eligibility

Date: 2026-10-04 · Status: accepted

## Context

Kev 1.0 (jaredpalmer/kev, pinned SHA `fe64b1274ea7f80d4095866df90666abb03e9cf6`,
2026-10-03) replaced the generation snapdec 0.2.0 pinned (`84847f0…`):
0.8B/4B/9B LoRA on Qwen3.5 + a 27B full fine-tune on Qwen3.8, new held-out
stats (breadth-v1 test DI: 23.3 / 38.0 / 41.0 / 52.3; Jev 54.0), and an
MLX backend in `kev[serve]` that is **validated on all Apple Silicon**
for 0.8B (4B measured at 13 GB peak on a 32 GB Mac; 9B expected on 32 GB+
but unmeasured; 27B needs 96–128 GB, unmeasured).

Separately OpenRouter delisted all `jaredpalmer/kev-*` ids; the only
System One model it serves is `typesafe/jev-router`.

## Decisions

1. **Stats source switch**: catalog + hosted rows now cite Kev 1.0
   breadth-v1 held-out numbers (one consistent eval across all models,
   incl. Jev 54.0) instead of the 0.2.0 mix (coding-v0-era 13.26/31.31,
   Jev 51.67). Mixing evals would be dishonest; one scale is honest.
2. **Apple eligibility fields**: `LocalModel.runs_on_apple` +
   `min_apple_ram_gb`; `fits()` checks Apple first (unified memory replaces
   the VRAM/discrete-GPU rules). kev-0.8B becomes the starred local rec on
   Apple (DI 23.3 vs Laya ~0 zero-shot). `slow_on_cpu` never displays on
   Apple — MLX is the fast path there.
3. **kev-4b VRAM floor = 16 GB** (judgment call): measured need is 13 GB
   peak on CUDA; 16 GB admits 4080/4090/5080-class boards with torch
   overhead, excludes 12 GB where peak+overhead is too tight. The cuda-mid
   profile threshold moves 12→16 GB to match; 12 GB boards get cuda-small.
4. **9B/27B honesty**: listed with hardware floors (9B: 24 GB VRAM /
   32 GB Mac "unmeasured"; 27B: 80 GB VRAM / 96–128 GB Mac), no stars —
   huge-machine options, not recommendations.
5. **Pin + install**: `KEV_PIN_SHA` → `fe64b127…`; install is
   `kev[serve] @ <tarball>` (extra carries fastapi/uvicorn/typesafe-sdk,
   mlx-lm resolves only on mac-arm64 via its marker). A Python 3.12/3.13
   floor is enforced before install (kev 1.0 requires-python >=3.12,<3.14).
6. **Wire model adoption**: after provisioning, the wizard adopts the
   server's advertised model id (`/v1/models`, `/models` fallback) instead
   of assuming the HF repo id round-trips the wire `model` field.
7. **OpenRouter**: default chain is the single verified id
   `typesafe/jev-router`; kev ids on OpenRouter are treated as dead and a
   regression test guards their return.

## Consequences

- Windows managed-kev install for 1.0 is NOT re-verified on real hardware
  (torch 2.6–2.9 + transformers 5.x download); laya path is unchanged and
  verified. The wizard shows honest setup sizes (5/12/22/60 GB per repo).
- 27B first run downloads ~54 GB of weights, likely exceeding the 600 s
  health wait — documented as best-effort; failure falls back cleanly.
- Deferred: daemon version-skew compare, Windsurf/Cline skill dirs,
  calibration refit, macOS real-hardware verification of the MLX path.
