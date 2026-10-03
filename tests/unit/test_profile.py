from __future__ import annotations

from snapdec.hardware.detect import GPU, HardwareReport
from snapdec.hardware.profile import select_profile


def rep(**kw) -> HardwareReport:
    base = dict(os="Windows 11", arch="AMD64", cpu_model="x", cores=8,
                ram_gb=16, gpus=[])
    base.update(kw)
    return HardwareReport(**base)


def test_tier0_low_ram():
    assert select_profile(rep(ram_gb=2)).id == "tier0"


def test_cpu_when_no_gpu():
    assert select_profile(rep(os="Linux")).id == "cpu"


def test_windows_gpu_gets_dml_profile():
    r = rep(gpus=[GPU(name="Intel(R) UHD Graphics", vendor="intel")])
    assert select_profile(r).id == "windows-gpu"


def test_cuda_tiers():
    small = rep(gpus=[GPU(name="RTX 3050", vendor="nvidia", vram_gb=4)])
    mid = rep(gpus=[GPU(name="RTX 4070", vendor="nvidia", vram_gb=12)])
    big = rep(gpus=[GPU(name="RTX 4090", vendor="nvidia", vram_gb=24)])
    assert select_profile(small).id == "cuda-small"
    assert select_profile(mid).id == "cuda-mid"
    assert select_profile(big).id == "server"


def test_apple_silicon():
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True,
            gpus=[GPU(name="Apple M4", vendor="apple")])
    assert select_profile(r).id == "apple"
    assert select_profile(rep(os="macOS 15", apple_silicon=True, ram_gb=4)).id == "tier0"
