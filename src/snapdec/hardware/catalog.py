"""Local-model catalog with honest stats + hardware gating (§1.3, §5.2).

The user gets complete freedom to choose — but only among options their
PC can actually run. Stats are Kev 1.0 held-out numbers (breadth-v1 test,
2026-10-03, from github.com/jaredpalmer/kev): Decision Index is
chance-corrected over the benchmark suite (Jev 54.0 reference); OOD =
out-of-domain accuracy on new sources.
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
    runs_on_apple: bool = False    # MLX path in kev[serve]/laya (Apple Silicon)
    min_apple_ram_gb: float = 0.0  # unified-memory floor when runs_on_apple
    recommended_for: tuple[str, ...] = ()  # profile ids that get the star


CATALOG: tuple[LocalModel, ...] = (
    LocalModel(
        "laya-en", "Laya EN", "421M",
        "DI ~0 zero-shot (specialize-first base)",
        "5–15 ms GPU/Apple · 50–450 ms CPU",
        "~2 GB (torch + transformers)",
        min_ram_gb=4, min_vram_gb=0, runs_on_apple=True, min_apple_ram_gb=8,
        recommended_for=("cpu", "windows-gpu"),
    ),
    LocalModel(
        "laya-multilingual", "Laya multilingual", "322M",
        "DI ~0 zero-shot · 100+ languages",
        "5–15 ms GPU/Apple · 50–450 ms CPU",
        "~2 GB (torch + transformers)",
        min_ram_gb=4, min_vram_gb=0, runs_on_apple=True, min_apple_ram_gb=8,
        recommended_for=(),
    ),
    LocalModel(
        "kev-0.8b", "Kev 0.8B", "0.8B",
        "DI 23.3 · OOD acc 0.65",
        "40–80 ms CUDA · fast on Apple (MLX) · CPU: seconds/question",
        "~5 GB (torch + transformers + weights)",
        min_ram_gb=8, min_vram_gb=0, slow_on_cpu=True,
        runs_on_apple=True, min_apple_ram_gb=8,
        recommended_for=("cuda-small", "apple"),
    ),
    LocalModel(
        "kev-4b", "Kev 4B", "4B",
        "DI 38.0 · OOD acc 0.84",
        "~70–80 ms L40S/H100 · 32 GB Mac via MLX (13 GB peak)",
        "~12 GB (weights + torch)",
        min_ram_gb=16, min_vram_gb=16, needs_gpu=True,
        runs_on_apple=True, min_apple_ram_gb=32,
        recommended_for=("cuda-mid",),
    ),
    LocalModel(
        "kev-9b", "Kev 9B", "9B",
        "DI 41.0 · OOD acc 0.85",
        "~17 GB GPU · 32 GB+ Mac (unmeasured)",
        "~22 GB (weights + torch)",
        min_ram_gb=32, min_vram_gb=24, needs_gpu=True,
        runs_on_apple=True, min_apple_ram_gb=32,
        recommended_for=("server",),
    ),
    LocalModel(
        "kev-27b", "Kev 27B", "27B",
        "DI 52.3 · OOD acc 0.89 · near-Jev (Jev 54.0)",
        "80 GB GPU (B200/H200) · 96–128 GB Mac",
        "~60 GB+ (weights dominate)",
        min_ram_gb=96, min_vram_gb=80, needs_gpu=True,
        runs_on_apple=True, min_apple_ram_gb=96,
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
