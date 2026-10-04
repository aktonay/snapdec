"""Hardware → inference profile (§5.2).

Initial rule table; to be replaced by the Phase-2/4 bake-off ADR.
Rule: pick the smallest profile that meets the accuracy bar — never the
biggest model that merely fits.
"""

from __future__ import annotations

from dataclasses import dataclass

from .detect import HardwareReport


@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    runtime: str
    default_model: str
    note: str


PROFILES: dict[str, Profile] = {
    "tier0": Profile("tier0", "Tier-0 only", "none", "", "rule-based answers, no model"),
    "cpu": Profile("cpu", "CPU", "ONNX Runtime CPU (INT8)", "laya-multilingual",
                   "Laya 322M — smallest useful; expect 100–500 ms"),
    "apple": Profile("apple", "Apple Silicon", "kev[serve] auto (MLX on Apple)", "kev-0.8b",
                     "Kev-0.8B via MLX — validated on all Apple Silicon; "
                     "DI 23.3 vs Laya ~0 zero-shot"),
    "windows-gpu": Profile("windows-gpu", "Windows GPU", "ONNX Runtime DirectML", "laya-en",
                           "DirectML; sequential execution provider required"),
    "cuda-small": Profile("cuda-small", "NVIDIA ≥4 GB", "torch + flash-linear-attention",
                          "kev-0.8b", "Kev-0.8B — modest out-of-domain accuracy"),
    "cuda-mid": Profile("cuda-mid", "NVIDIA 16–24 GB", "torch", "kev-4b",
                        "Kev-4B — better coverage; ~10 s one-time kernel compile"),
    "server": Profile("server", "Server GPU ≥24 GB", "torch / vLLM", "kev-9b",
                      "Kev-9B (DI 41.0); 27B on 80 GB boards; optional shared team daemon"),
}


def select_profile(report: HardwareReport) -> Profile:
    nvidia = [g for g in report.gpus if g.vendor == "nvidia" and (g.vram_gb or 0) >= 4]
    if report.apple_silicon:
        return PROFILES["apple"] if (report.ram_gb or 0) >= 8 else PROFILES["tier0"]
    if nvidia:
        vram = max(g.vram_gb or 0 for g in nvidia)
        if vram >= 24:
            return PROFILES["server"]
        if vram >= 16:  # kev-4b VRAM floor (ADR-0008); 12 GB boards run kev-0.8b
            return PROFILES["cuda-mid"]
        return PROFILES["cuda-small"]
    if (report.ram_gb or 0) < 4:
        return PROFILES["tier0"]
    if sys_platform() == "win32" and report.gpus:
        return PROFILES["windows-gpu"]
    return PROFILES["cpu"]


def sys_platform() -> str:
    import sys

    return sys.platform
