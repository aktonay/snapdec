from __future__ import annotations

from snapdec.hardware.catalog import catalog_for, fits
from snapdec.hardware.detect import GPU, HardwareReport


def rep(**kw) -> HardwareReport:
    base = dict(os="Windows 11", arch="AMD64", cpu_model="x", cores=8,
                ram_gb=16, gpus=[])
    base.update(kw)
    return HardwareReport(**base)


def test_intel_igpu_16gb_gets_laya_and_kev08_but_not_kev4b():
    r = rep(gpus=[GPU(name="Intel(R) UHD Graphics", vendor="intel")])
    keys = {m.key for m in catalog_for(r)}
    assert "laya-en" in keys
    assert "kev-0.8b" in keys            # freedom: runs, just slow on CPU
    assert "kev-4b" not in keys          # needs 16 GB VRAM — outside spec


def test_big_nvidia_gets_everything():
    r = rep(ram_gb=64, gpus=[GPU(name="RTX 4090", vendor="nvidia", vram_gb=24)])
    keys = {m.key for m in catalog_for(r)}
    assert {"laya-en", "kev-0.8b", "kev-4b", "kev-9b"} <= keys
    assert "kev-27b" not in keys  # 80 GB floor


def test_kev9b_needs_24gb_vram():
    keys12 = {m.key for m in catalog_for(rep(ram_gb=32, gpus=[GPU("RTX 4070", "nvidia", 12)]))}
    keys24 = {m.key for m in catalog_for(rep(ram_gb=32, gpus=[GPU("RTX 4090", "nvidia", 24)]))}
    assert "kev-9b" not in keys12
    assert "kev-9b" in keys24


def test_kev27b_needs_80gb_vram():
    keys24 = {m.key for m in catalog_for(rep(ram_gb=96, gpus=[GPU("RTX 4090", "nvidia", 24)]))}
    keys80 = {m.key for m in catalog_for(rep(ram_gb=96, gpus=[GPU("B200", "nvidia", 80)]))}
    assert "kev-27b" not in keys24
    assert "kev-27b" in keys80


def test_apple_16gb_gets_kev08_not_bigger():
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True, ram_gb=16,
            gpus=[GPU(name="Apple M4", vendor="apple")])
    keys = {m.key for m in catalog_for(r)}
    assert "kev-0.8b" in keys and "laya-en" in keys
    assert "kev-4b" not in keys and "kev-9b" not in keys and "kev-27b" not in keys


def test_apple_32gb_gets_kev4b_9b_not_27b():
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True, ram_gb=32,
            gpus=[GPU(name="Apple M4 Pro", vendor="apple")])
    keys = {m.key for m in catalog_for(r)}
    assert "kev-4b" in keys and "kev-9b" in keys
    assert "kev-27b" not in keys


def test_apple_96gb_gets_27b():
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True, ram_gb=96,
            gpus=[GPU(name="Apple M3 Ultra", vendor="apple")])
    assert "kev-27b" in {m.key for m in catalog_for(r)}


def test_low_ram_drops_kev():
    r = rep(ram_gb=4)
    keys = {m.key for m in catalog_for(r)}
    assert "kev-0.8b" not in keys and "kev-4b" not in keys
    assert "laya-en" in keys


def test_fits_kev4b_requires_discrete():
    no_gpu = rep()
    kev4 = next(m for m in catalog_for(rep(gpus=[GPU("RTX 4090", "nvidia", 24)]))
                if m.key == "kev-4b")
    assert fits(kev4, rep(gpus=[GPU("RTX 4090", "nvidia", 24)]))
    assert not fits(kev4, no_gpu)
