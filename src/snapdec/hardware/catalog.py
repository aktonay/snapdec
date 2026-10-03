"""Local-model catalog with honest stats + hardware gating (§1.3, §5.2).

The user gets complete freedom to choose — but only among options their
PC can actually run. Stats are from SYSONE_ARCHITECTURE.md §1.3 research
(2026-10-03): Decision Index = chance-corrected score over 40 benchmarks
(Jev 51.67 reference); OOD = out-of-domain accuracy.
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
    recommended_for: tuple[str, ...] = ()  # profile ids that get the star


CATALOG: tuple[LocalModel, ...] = (
    LocalModel(
        "laya-en", "Laya EN", "421M",
        "DI ~0 zero-shot (specialize-first base)",
        "5–15 ms GPU/Apple · 50–450 ms CPU",
        "~2 GB (torch + transformers)",
        min_ram_gb=4, min_vram_gb=0,
        recommended_for=("cpu", "windows-gpu", "apple"),
    ),
    LocalModel(
        "laya-multilingual", "Laya multilingual", "322M",
        "DI ~0 zero-shot · 100+ languages",
        "5–15 ms GPU/Apple · 50–450 ms CPU",
        "~2 GB (torch + transformers)",
        min_ram_gb=4, min_vram_gb=0,
        recommended_for=("cpu",),
    ),
    LocalModel(
        "kev-0.8b", "Kev 0.8B", "0.8B",
        "DI 13.26 · OOD acc 0.652",
        "~40–80 ms CUDA · CPU: seconds/question",
        "~3 GB (torch + fla + weights)",
        min_ram_gb=8, min_vram_gb=0, slow_on_cpu=True,
        recommended_for=("cuda-small",),
    ),
    LocalModel(
        "kev-4b", "Kev 4B", "4B",
        "DI 31.31 · OOD acc 0.797",
        "~70–80 ms RTX 4500 Ada (after ~10 s compile)",
        "~16 GB (weights + torch)",
        min_ram_gb=16, min_vram_gb=12, needs_gpu=True,
        recommended_for=("cuda-mid", "server"),
    ),
)

HOSTED_STATS = (
    ("OpenRouter",
     "free keys (openrouter.ai/keys) · hosts Jev + Kev · Jev DI 51.67 (best known)"),
    ("TypeSafe Jev",
     "native /v1/systemone · Jev DI 51.67 (best known) · paid per call"),
)


def max_vram(report: HardwareReport) -> float:
    return max((g.vram_gb or 0 for g in report.gpus), default=0)


def has_discrete_gpu(report: HardwareReport) -> bool:
    return any(g.vendor in ("nvidia", "amd") for g in report.gpus)


def fits(model: LocalModel, report: HardwareReport) -> bool:
    if model.needs_gpu and not has_discrete_gpu(report):
        return False
    if model.min_vram_gb > 0 and max_vram(report) < model.min_vram_gb:
        return False
    return (report.ram_gb or 0) >= model.min_ram_gb


def catalog_for(report: HardwareReport) -> list[LocalModel]:
    return [m for m in CATALOG if fits(m, report)]
