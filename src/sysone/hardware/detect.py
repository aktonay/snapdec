"""Hardware detection — no ML imports (ADR-03).

Probes per §5.1 of SYSONE_ARCHITECTURE.md. Every probe is best-effort:
a failure leaves the field unset rather than raising. Windows VRAM note:
Win32_VideoController.AdapterRAM is a 32-bit field capped at 4 GB, and
on shared-memory iGPUs it is meaningless — treat it as a hint only.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass
class GPU:
    name: str
    vendor: str  # nvidia | amd | intel | apple | unknown
    vram_gb: float | None = None


@dataclass
class HardwareReport:
    os: str = ""
    arch: str = ""
    cpu_model: str = ""
    cores: int = 0
    ram_gb: float | None = None
    gpus: list[GPU] = field(default_factory=list)
    apple_silicon: bool = False
    wsl: bool = False
    notes: list[str] = field(default_factory=list)

    def oneline(self) -> str:
        parts = [self.cpu_model or "unknown CPU"]
        if self.ram_gb:
            parts.append(f"{self.ram_gb:.0f} GB RAM")
        if self.apple_silicon:
            parts.append("Apple Silicon")
        for g in self.gpus:
            vram = f" · {g.vram_gb:.0f} GB VRAM" if g.vram_gb else ""
            parts.append(f"{g.name}{vram}")
        parts.append(self.os)
        return " · ".join(parts)


def _run(cmd: list[str], timeout: float = 5.0) -> str | None:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode == 0:
            return r.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _detect_apple(report: HardwareReport) -> None:
    if sys.platform != "darwin":
        return
    report.apple_silicon = platform.machine() == "arm64"
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if brand:
        report.cpu_model = brand.strip()
    if report.apple_silicon:
        report.gpus.append(GPU(name=report.cpu_model or "Apple Silicon", vendor="apple"))
        translated = _run(["sysctl", "-n", "sysctl.proc_translated"])
        if translated and translated.strip() == "1":
            report.notes.append("running under Rosetta (x86 Python on Apple Silicon)")
    mem = _run(["sysctl", "-n", "hw.memsize"])
    if mem:
        try:
            report.ram_gb = int(mem.strip()) / 1024**3
        except ValueError:
            pass


def _detect_linux(report: HardwareReport) -> None:
    if sys.platform != "linux":
        return
    report.wsl = ("microsoft" in platform.release().lower()
                  or bool(os.environ.get("WSL_DISTRO_NAME")))
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    report.cpu_model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    report.ram_gb = int(line.split()[1]) / 1024**2
                    break
    except OSError:
        pass
    nvidia = _run(
        ["nvidia-smi", "--query-gpu=name,memory.total",
         "--format=csv,noheader,nounits"])
    if nvidia:
        for row in nvidia.strip().splitlines():
            bits = [b.strip() for b in row.split(",")]
            if len(bits) >= 2 and bits[0]:
                try:
                    vram = float(bits[1]) / 1024
                except ValueError:
                    vram = None
                report.gpus.append(GPU(name=bits[0], vendor="nvidia", vram_gb=vram))
    elif shutil.which("rocm-smi"):
        smi = _run(["rocm-smi", "--json"])
        if smi:
            try:
                for card in json.loads(smi).get("card", {}).values():
                    name = card.get("Card series") or card.get("Card model") or "AMD GPU"
                    report.gpus.append(GPU(name=name, vendor="amd"))
            except (json.JSONDecodeError, AttributeError):
                pass


def _detect_windows(report: HardwareReport) -> None:
    if sys.platform != "win32":
        return
    ps = (
        "$cs = Get-CimInstance Win32_ComputerSystem; "
        "$cpu = Get-CimInstance Win32_Processor; "
        "$gpus = Get-CimInstance Win32_VideoController; "
        "[pscustomobject]@{ ram = $cs.TotalPhysicalMemory; cpu = $cpu.Name; "
        "gpus = @($gpus | ForEach-Object { $_.Name }) } | ConvertTo-Json -Compress"
    )
    out = _run(["powershell", "-NoProfile", "-Command", ps], timeout=15)
    if out:
        try:
            data = json.loads(out)
            report.ram_gb = float(data.get("ram", 0)) / 1024**3 or None
            report.cpu_model = (data.get("cpu") or "").strip()
            for name in data.get("gpus", []):
                if not name:
                    continue
                low = name.lower()
                vendor = "nvidia" if ("nvidia" in low or "geforce" in low or "rtx" in low) \
                    else "amd" if ("amd" in low or "radeon" in low) \
                    else "intel" if "intel" in low else "unknown"
                # AdapterRAM is unreliable (32-bit cap, shared memory iGPUs): no VRAM claim.
                report.gpus.append(GPU(name=name.strip(), vendor=vendor))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    # nvidia-smi is authoritative when present (also inside WSL2)
    nvidia = _run(
        ["nvidia-smi", "--query-gpu=name,memory.total",
         "--format=csv,noheader,nounits"])
    if nvidia:
        report.gpus = [g for g in report.gpus if g.vendor != "nvidia"]
        for row in nvidia.strip().splitlines():
            bits = [b.strip() for b in row.split(",")]
            if len(bits) >= 2 and bits[0]:
                try:
                    vram = float(bits[1]) / 1024
                except ValueError:
                    vram = None
                report.gpus.append(GPU(name=bits[0], vendor="nvidia", vram_gb=vram))


def detect() -> HardwareReport:
    report = HardwareReport(
        os=f"{platform.system()} {platform.release()}".strip(),
        arch=platform.machine() or os.environ.get("PROCESSOR_ARCHITECTURE", ""),
        cores=os.cpu_count() or 0,
    )
    _detect_windows(report)
    _detect_linux(report)
    _detect_apple(report)
    return report
