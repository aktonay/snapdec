from __future__ import annotations

from snapdec.hardware.catalog import CATALOG, catalog_for, fits
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


# ------------------------------------------------- decision2 entries (ADR-0010)

def test_intel_igpu_16gb_gets_kai_eos_sol_not_nox():
    r = rep(gpus=[GPU(name="Intel(R) UHD Graphics", vendor="intel")])
    keys = {m.key for m in catalog_for(r)}
    assert {"d2-kai", "d2-eos", "d2-sol"} <= keys
    assert "d2-nox" not in keys            # 20 GB RAM floor


def test_big_nvidia_gets_all_d2():
    r = rep(ram_gb=64, gpus=[GPU(name="RTX 4090", vendor="nvidia", vram_gb=24)])
    keys = {m.key for m in catalog_for(r)}
    assert {"d2-kai", "d2-eos", "d2-sol", "d2-nox"} <= keys


def test_apple_16gb_gets_d2_kai_eos_not_sol_nox():
    # 0.5.1: d2 selectable on Apple via the plain torch CPU path (ADR-0010 §4);
    # unified-memory floors: kai/eos 8 GB, sol/nox 32 GB
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True, ram_gb=16,
            gpus=[GPU(name="Apple M4", vendor="apple")])
    keys = {m.key for m in catalog_for(r)}
    assert {"d2-kai", "d2-eos"} <= keys
    assert "d2-sol" not in keys and "d2-nox" not in keys


def test_apple_32gb_gets_sol_nox_too():
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True, ram_gb=32,
            gpus=[GPU(name="Apple M4 Pro", vendor="apple")])
    keys = {m.key for m in catalog_for(r)}
    assert {"d2-kai", "d2-eos", "d2-sol", "d2-nox"} <= keys


def test_d2_apple_is_cpu_not_mlx_and_unstarred():
    # kev/laya keep the MLX fast path (wizard slow-tag suppression on Apple);
    # d2 does not — and never wins the apple star from kev-0.8b
    by = {m.key: m for m in CATALOG}
    assert by["kev-0.8b"].mlx_on_apple and by["laya-en"].mlx_on_apple
    assert not any(by[k].mlx_on_apple for k in
                   ("d2-kai", "d2-eos", "d2-sol", "d2-nox"))
    assert "apple" not in by["d2-eos"].recommended_for


def test_d2_slow_flags_and_star():
    by = {m.key: m for m in CATALOG}
    # p95 6.6 s / 9.3 s on the bench PC — every d2 variant is slow on CPU
    # (docs/benchmarks/2026-10-07-decision2-{eos,kai}.md)
    assert all(by[k].slow_on_cpu for k in ("d2-kai", "d2-eos", "d2-sol", "d2-nox"))
    assert by["d2-eos"].recommended_for == ("cpu", "windows-gpu")  # eos-only star
    assert by["d2-kai"].recommended_for == ()


def test_d2_stats_always_cite_card_source():
    # two stat scales must never blend into one unattributed number (ADR-0008)
    for m in CATALOG:
        if m.key.startswith("d2-"):
            assert "vllm-sr card" in m.di
            assert "breadth" not in m.di  # kev's held-out scale stays out


# ------------------------------------------------------------- imajev (ADR-0011)

def test_intel_igpu_16gb_gets_imajev_2b_only():
    # torch fp32 CPU path: RAM floors 12/24/48 GB (ADR-0011)
    r = rep(gpus=[GPU(name="Intel(R) UHD Graphics", vendor="intel")])
    keys = {m.key for m in catalog_for(r)}
    assert "imajev-2b" in keys
    assert "imajev-4b" not in keys and "imajev-9b" not in keys


def test_big_nvidia_gets_all_imajev():
    r = rep(ram_gb=64, gpus=[GPU(name="RTX 4090", vendor="nvidia", vram_gb=24)])
    keys = {m.key for m in catalog_for(r)}
    assert {"imajev-2b", "imajev-4b", "imajev-9b"} <= keys


def test_apple_16gb_gets_imajev_2b_4b_not_9b():
    # real MLX fast path on Apple: unified-memory floors 8/16/32 GB
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True, ram_gb=16,
            gpus=[GPU(name="Apple M4", vendor="apple")])
    keys = {m.key for m in catalog_for(r)}
    assert {"imajev-2b", "imajev-4b"} <= keys
    assert "imajev-9b" not in keys


def test_apple_32gb_gets_imajev_9b_too():
    r = rep(os="macOS 15", arch="arm64", apple_silicon=True, ram_gb=32,
            gpus=[GPU(name="Apple M4 Pro", vendor="apple")])
    keys = {m.key for m in catalog_for(r)}
    assert {"imajev-2b", "imajev-4b", "imajev-9b"} <= keys


def test_imajev_apple_mlx_unstarred_slow_on_cpu():
    by = {m.key: m for m in CATALOG}
    for k in ("imajev-2b", "imajev-4b", "imajev-9b"):
        m = by[k]
        assert m.mlx_on_apple and m.runs_on_apple and m.slow_on_cpu
        assert m.recommended_for == ()  # unbenched → no star (ADR-0011)
        assert m.min_vram_gb == 0  # fp32 CPU path needs no discrete GPU


def test_imajev_stats_always_cite_board_source():
    # third stat scale: JevBench board numbers never blend with kev breadth-v1
    # or the vllm-sr card (ADR-0008 rule, ADR-0011)
    for m in CATALOG:
        if m.key.startswith("imajev-"):
            assert "board 2026-09" in m.di
            assert "vllm-sr card" not in m.di and "breadth" not in m.di
