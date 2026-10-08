"""Local-model catalog with honest stats + hardware gating (§1.3, §5.2).

The user gets complete freedom to choose — but only among options their
PC can actually run. Stats are Kev 1.0 held-out numbers (breadth-v1 test,
2026-10-03, from github.com/jaredpalmer/kev): Decision Index is
chance-corrected over the benchmark suite (Jev 54.0 reference); OOD =
out-of-domain accuracy on new sources.

Decision 2.0 (vllm-sr) stats are vendor-card numbers (2026-10) on their
own index — a DIFFERENT scale from kev's held-out DI; the two are never
cross-compared in one number (ADR-0008 rule, ADR-0010).

imajev (mohit67890) stats are JevBench board numbers (2026-09) on yet
another scale — source-cited, never blended with the other two
(ADR-0008 rule, ADR-0011).
"""

from __future__ import annotations

from dataclasses import dataclass

from .detect import HardwareReport


@dataclass(frozen=True)
class LocalModel:
    key: str                 # catalog id
    label: str
    params: str
    di: str                  # Decision Index (zero-shot unless noted)
    latency: str
    setup: str               # download/setup footprint
    min_ram_gb: float
    min_vram_gb: float       # 0 = runs on CPU (maybe slowly)
    needs_gpu: bool = False  # excluded entirely without a discrete GPU
    slow_on_cpu: bool = False
    runs_on_apple: bool = False    # any validated Apple path (MLX or CPU)
    min_apple_ram_gb: float = 0.0  # unified-memory floor when runs_on_apple
    mlx_on_apple: bool = False     # kev[serve]/laya MLX fast path (slow-tag
    #                                 suppression on Apple); d2 runs CPU there
    recommended_for: tuple[str, ...] = ()  # profile ids that get the star


CATALOG: tuple[LocalModel, ...] = (
    LocalModel(
        "laya-en", "Laya EN", "421M",
        "DI ~0 zero-shot (specialize-first base)",
        "5–15 ms GPU/Apple · 50–450 ms CPU",
        "~2 GB (torch + transformers)",
        min_ram_gb=4, min_vram_gb=0, runs_on_apple=True, min_apple_ram_gb=8, mlx_on_apple=True,
        recommended_for=("cpu", "windows-gpu"),
    ),
    LocalModel(
        "laya-multilingual", "Laya multilingual", "322M",
        "DI ~0 zero-shot · 100+ languages",
        "5–15 ms GPU/Apple · 50–450 ms CPU",
        "~2 GB (torch + transformers)",
        min_ram_gb=4, min_vram_gb=0, runs_on_apple=True, min_apple_ram_gb=8, mlx_on_apple=True,
        recommended_for=(),
    ),
    LocalModel(
        "kev-0.8b", "Kev 0.8B", "0.8B",
        "DI 23.3 · OOD acc 0.65",
        "40–80 ms CUDA · fast on Apple (MLX) · CPU: seconds/question",
        "~5 GB (torch + transformers + weights)",
        min_ram_gb=8, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=8, mlx_on_apple=True,
        recommended_for=("cuda-small", "apple"),
    ),
    LocalModel(
        "kev-4b", "Kev 4B", "4B",
        "DI 38.0 · OOD acc 0.84",
        "~70–80 ms L40S/H100 · 32 GB Mac via MLX (13 GB peak)",
        "~12 GB (weights + torch)",
        min_ram_gb=16, min_vram_gb=16, needs_gpu=True,
        runs_on_apple=True, min_apple_ram_gb=32, mlx_on_apple=True,
        recommended_for=("cuda-mid",),
    ),
    LocalModel(
        "kev-9b", "Kev 9B", "9B",
        "DI 41.0 · OOD acc 0.85",
        "~17 GB GPU · 32 GB+ Mac (unmeasured)",
        "~22 GB (weights + torch)",
        min_ram_gb=32, min_vram_gb=24, needs_gpu=True,
        runs_on_apple=True, min_apple_ram_gb=32, mlx_on_apple=True,
        recommended_for=("server",),
    ),
    LocalModel(
        "kev-27b", "Kev 27B", "27B",
        "DI 52.3 · OOD acc 0.89 · near-Jev (Jev 54.0)",
        "80 GB GPU (B200/H200) · 96–128 GB Mac",
        "~60 GB+ (weights dominate)",
        min_ram_gb=96, min_vram_gb=80, needs_gpu=True,
        runs_on_apple=True, min_apple_ram_gb=96, mlx_on_apple=True,
        recommended_for=(),
    ),
    # Decision 2.0 (HF org vllm-sr, Apache-2.0, port 8903 — ADR-0010).
    # Vendor-card stats, own scale (see module docstring). CPU numbers are
    # snapdec-bench measurements on i5-13420H (docs/benchmarks/
    # 2026-10-07-decision2-{eos,kai}.md); multi-second p50 → slow_on_cpu on
    # every variant. Sol/Nox unbenched (Nox hidden by RAM floor here).
    # min_ram = FP32 residency + headroom.
    # Apple (0.5.1): runs_on_apple=True via the plain torch CPU path (d2serve
    # is device-agnostic; no MLX build exists) → mlx_on_apple stays False so
    # the wizard keeps showing [slow on CPU] there. Apple floors are higher
    # than x86: unified memory is shared with the OS + GPU. MPS deferred.
    LocalModel(
        "d2-kai", "Decision 2.0 Kai 0.6B", "0.6B",
        "JevArena 48.6 · transfer 45.9 · DI 16.3 (vllm-sr card 2026-10)",
        "CPU: p50 5.8 s / p95 6.6 s (bench 2026-10-07) · Apple (CPU): bench "
        "pending · GPU: 4.9 ms (card)",
        "~2 GB (weights + torch)",
        min_ram_gb=6, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=8,
    ),
    LocalModel(
        "d2-eos", "Decision 2.0 Eos 0.8B", "0.8B",
        "JevArena 53.9 · transfer 50.3 · DI 20.1 (vllm-sr card 2026-10 · "
        "same-board beats Kev-0.8B 53.9 vs 43.2)",
        "CPU: p50 7.4 s / p95 9.3 s (bench 2026-10-07) · Apple (CPU): bench "
        "pending · GPU: 6.0 ms (card)",
        "~3 GB (weights + torch)",
        min_ram_gb=8, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=8,
        recommended_for=("cpu", "windows-gpu"),
    ),
    LocalModel(
        "d2-sol", "Decision 2.0 Sol 2B", "2B",
        "JevArena 52.1 · transfer 51.3 · DI 29.5 (vllm-sr card 2026-10)",
        "CPU: not benched (2B FP32 ≫ Eos on same core) · Apple (CPU): bench "
        "pending · GPU: 7.2 ms (card)",
        "~6 GB (weights + torch)",
        min_ram_gb=10, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=32,
    ),
    LocalModel(
        "d2-nox", "Decision 2.0 Nox 4B", "4B",
        "JevArena 63.6 · transfer 52.3 · DI 43.8 (vllm-sr card 2026-10)",
        "CPU: not benched · Apple (CPU): bench pending · GPU: 12.9 ms (card)",
        "~11 GB (weights + torch)",
        min_ram_gb=20, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=32,
    ),
    # imajev (GitHub mohit67890/imajev, Apache-2.0, port 8904 — ADR-0011).
    # JevBench board stats, own scale (see module docstring). Served by their
    # pinned playground server, CPU dtype is always FP32 → min_ram floors
    # 12/24/48 = weights + calibration + headroom. Apple gets the REAL MLX
    # path (--backend mlx, fp16) → mlx_on_apple=True, floors 8/16/32. Unbenched
    # → no star anywhere (kev-0.8b/d2-eos keep theirs). 2b is the only variant
    # this dev PC (15.7 GB) can run.
    LocalModel(
        "imajev-2b", "imajev 2B (Qwen3.5)", "2.2B",
        "JevBench hard split 60.4 · Image JevBench v0.1.3 68.72 #6 (board 2026-09)",
        "CPU: p50 14.8 s / p95 35.1 s (bench 2026-10-08) · Apple (MLX): bench pending",
        "~5 GB (Qwen3.5-2B base + adapter + torch)",
        min_ram_gb=12, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=8, mlx_on_apple=True,
        recommended_for=(),
    ),
    LocalModel(
        "imajev-4b", "imajev 4B (Qwen3.5)", "4.3B",
        "JevBench v1.4.2.2 67.37 #1 · Image JevBench v0.1.3 76.39 #1 · "
        "DecisionBench 79.65 #3 (board 2026-09)",
        "CPU: bench pending · Apple (MLX): bench pending",
        "~10 GB (weights + torch)",
        min_ram_gb=24, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=16, mlx_on_apple=True,
        recommended_for=(),
    ),
    LocalModel(
        "imajev-9b", "imajev 9B (Qwen3.5)", "9.4B",
        "JevBench hard split 69.4 (board 2026-09)",
        "CPU: bench pending · Apple (MLX): bench pending",
        "~19 GB (weights + torch)",
        min_ram_gb=48, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=32, mlx_on_apple=True,
        recommended_for=(),
    ),
)

HOSTED_STATS = (
    ("OpenRouter",
     "free keys (openrouter.ai/keys) · typesafe/jev-router · Jev DI 54.0 (best known)"),
    ("TypeSafe Jev",
     "native /v1/systemone · Jev DI 54.0 (best known) · paid per call"),
)


def max_vram(report: HardwareReport) -> float:
    return max((g.vram_gb or 0 for g in report.gpus), default=0)


def has_discrete_gpu(report: HardwareReport) -> bool:
    return any(g.vendor in ("nvidia", "amd") for g in report.gpus)


def fits(model: LocalModel, report: HardwareReport) -> bool:
    # Apple Silicon: unified memory + MLX replace the VRAM/discrete-GPU rules
    # (kev-0.8B validated on all Apple Silicon; 4B+ gated by RAM — ADR-0008).
    if report.apple_silicon:
        return model.runs_on_apple and (report.ram_gb or 0) >= model.min_apple_ram_gb
    if model.needs_gpu and not has_discrete_gpu(report):
        return False
    if model.min_vram_gb > 0 and max_vram(report) < model.min_vram_gb:
        return False
    return (report.ram_gb or 0) >= model.min_ram_gb


def catalog_for(report: HardwareReport) -> list[LocalModel]:
    return [m for m in CATALOG if fits(m, report)]
