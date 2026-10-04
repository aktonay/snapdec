# Bench run — mock backend (harness self-test)

Provenance: `snapdec bench --backend mock --json` · snapdec 0.3.0 · Windows 11 (i5-13420H, 16 GB) · 2026-10-04.

**This is NOT a model-quality claim.** The mock backend is a deterministic
pseudo-random distribution; these numbers only prove the harness runs and
reports. Real-backend runs get their own dated file here (AGENTS.md rule).

```json
{
  "suite": "mini-v1",
  "snapdec_version": "0.3.0",
  "backend": {
    "name": "mock",
    "model": "mock-1"
  },
  "items": 12,
  "classify_accuracy": 0.0,
  "check_accuracy": 0.25,
  "check_brier": 0.75,
  "score_exact": 0.0,
  "decision_mix": {
    "auto": 0,
    "review": 12
  },
  "latency_p50_ms": 0.02,
  "latency_p95_ms": 0.04,
  "latency_note": "direct-to-backend (no daemon hop)",
  "results": [
    {
      "id": "c1",
      "task": "classify",
      "predicted": "deps",
      "truth": "infra",
      "correct": false,
      "probabilities": {
        "infra": 0.08617092176951054,
        "bug": 0.2406496599922105,
        "deps": 0.4926381630028614,
        "timeout": 0.18054125523541753
      },
      "probability": 0.4926381630028614,
      "margin": 0.2519885030106509,
      "decision": "review"
    },
    {
      "id": "c2",
      "task": "classify",
      "predicted": "timeout",
      "truth": "bug",
      "correct": false,
      "probabilities": {
        "infra": 0.17885437507757587,
        "bug": 0.24507497937595435,
        "deps": 0.08863216293637932,
        "timeout": 0.48743848261009054
      },
      "probability": 0.48743848261009054,
      "margin": 0.2423635032341362,
      "decision": "review"
    },
    {
      "id": "c3",
      "task": "classify",
      "predicted": "timeout",
      "truth": "deps",
      "correct": false,
      "probabilities": {
        "infra": 0.1582484273875357,
        "bug": 0.19343469936975358,
        "deps": 0.20574712789161417,
        "timeout": 0.4425697453510966
      },
      "probability": 0.4425697453510966,
      "margin": 0.23682261745948244,
      "decision": "review"
    },
    {
      "id": "c4",
      "task": "classify",
      "predicted": "deps",
      "truth": "infra",
      "correct": false,
      "probabilities": {
        "infra": 0.16948786241529218,
        "bug": 0.15004981903064063,
        "deps": 0.5716549704593549,
        "timeout": 0.10880734809471236
      },
      "probability": 0.5716549704593549,
      "margin": 0.4021671080440627,
      "decision": "review"
    },
    {
      "id": "c5",
      "task": "classify",
      "predicted": "infra",
      "truth": "bug",
      "correct": false,
      "probabilities": {
        "infra": 0.5575087991407613,
        "bug": 0.15321513947449186,
        "deps": 0.17340835437840627,
        "timeout": 0.11586770700634061
      },
      "probability": 0.5575087991407613,
      "margin": 0.38410044476235505,
      "decision": "review"
    },
    {
      "id": "c6",
      "task": "classify",
      "predicted": "infra",
      "truth": "deps",
      "correct": false,
      "probabilities": {
        "infra": 0.5150926963739203,
        "bug": 0.15546264375380184,
        "deps": 0.19856460580630533,
        "timeout": 0.13088005406597253
      },
      "probability": 0.5150926963739203,
      "margin": 0.316528090567615,
      "decision": "review"
    },
    {
      "id": "k1",
      "task": "check",
      "p_yes": 0.0,
      "truth": true,
      "correct": false,
      "probabilities": {
        "yes": 0.3037292422772635,
        "no": 0.6962707577227365
      },
      "probability": 0.6962707577227365,
      "margin": 0.392541515445473,
      "decision": "review"
    },
    {
      "id": "k2",
      "task": "check",
      "p_yes": 0.0,
      "truth": false,
      "correct": true,
      "probabilities": {
        "yes": 0.20727401397288794,
        "no": 0.792725986027112
      },
      "probability": 0.792725986027112,
      "margin": 0.5854519720542241,
      "decision": "review"
    },
    {
      "id": "k3",
      "task": "check",
      "p_yes": 0.0,
      "truth": true,
      "correct": false,
      "probabilities": {
        "yes": 0.2323601902161758,
        "no": 0.7676398097838242
      },
      "probability": 0.7676398097838242,
      "margin": 0.5352796195676484,
      "decision": "review"
    },
    {
      "id": "k4",
      "task": "check",
      "p_yes": 1.0,
      "truth": false,
      "correct": false,
      "probabilities": {
        "yes": 0.7058770608700936,
        "no": 0.29412293912990634
      },
      "probability": 0.7058770608700936,
      "margin": 0.4117541217401873,
      "decision": "review"
    },
    {
      "id": "s1",
      "task": "score",
      "predicted": "major",
      "truth": "trivial",
      "correct": false,
      "probabilities": {
        "trivial": 0.15194853317161205,
        "minor": 0.20410130189678768,
        "major": 0.4768734091168727,
        "critical": 0.16707675581472747
      },
      "probability": 0.4768734091168727,
      "margin": 0.27277210722008505,
      "decision": "review"
    },
    {
      "id": "s2",
      "task": "score",
      "predicted": "minor",
      "truth": "critical",
      "correct": false,
      "probabilities": {
        "trivial": 0.2211784077513242,
        "minor": 0.46190966933252375,
        "major": 0.1809550053055727,
        "critical": 0.13595691761057938
      },
      "probability": 0.46190966933252375,
      "margin": 0.24073126158119956,
      "decision": "review"
    }
  ]
}
```
