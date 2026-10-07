# Bench run — Decision 2.0 Kai-0.6B (local CPU)

Provenance: `snapdec bench --json` · snapdec 0.5.0 · Windows 11 (i5-13420H, 16 GB RAM, Intel UHD, CPU FP32) · 2026-10-07 · model vllm-sr/Decision-2.0-Kai-0.6B @ cd49ea38.

Same harness and caveats as the Eos run the same day. Latency is
direct-to-backend, per bench item; mini-v1 accuracy at n=12 is not a
model-quality claim. On this suite Kai and Eos answered identically
(same correct/incorrect pattern, same rounded Brier); they differ in
latency and model size.

```json
{
  "suite": "mini-v1",
  "snapdec_version": "0.5.0",
  "backend": {
    "name": "remote",
    "model": "vllm-sr/Decision-2.0-Kai-0.6B"
  },
  "items": 12,
  "classify_accuracy": 0.5,
  "check_accuracy": 0.75,
  "check_brier": 0.1849,
  "score_exact": 0.5,
  "decision_mix": {
    "auto": 5,
    "review": 7
  },
  "latency_p50_ms": 6068.93,
  "latency_p95_ms": 6452.53,
  "latency_note": "direct-to-backend (no daemon hop)",
  "results": [
    {
      "id": "c1",
      "task": "classify",
      "predicted": "infra",
      "truth": "infra",
      "correct": true,
      "probabilities": {
        "infra": 0.9969935531706268,
        "bug": 0.00043069294635323497,
        "deps": 0.0025051466500152415,
        "timeout": 7.06072330048107e-05
      },
      "probability": 0.9969935531706268,
      "margin": 0.9944884065206115,
      "decision": "auto"
    },
    {
      "id": "c2",
      "task": "classify",
      "predicted": "bug",
      "truth": "bug",
      "correct": true,
      "probabilities": {
        "infra": 0.055288374686530965,
        "bug": 0.9019280633479861,
        "deps": 0.019944006165346473,
        "timeout": 0.02283955580013648
      },
      "probability": 0.9019280633479861,
      "margin": 0.8466396886614552,
      "decision": "auto"
    },
    {
      "id": "c3",
      "task": "classify",
      "predicted": "deps",
      "truth": "deps",
      "correct": true,
      "probabilities": {
        "infra": 0.006386369016275962,
        "bug": 0.0007483506350256727,
        "deps": 0.9928626073208263,
        "timeout": 2.6730278721441514e-06
      },
      "probability": 0.9928626073208263,
      "margin": 0.9864762383045503,
      "decision": "auto"
    },
    {
      "id": "c4",
      "task": "classify",
      "predicted": "timeout",
      "truth": "infra",
      "correct": false,
      "probabilities": {
        "infra": 0.1537077419563318,
        "bug": 0.027846283220806258,
        "deps": 0.01321896639454318,
        "timeout": 0.8052270084283187
      },
      "probability": 0.8052270084283187,
      "margin": 0.6515192664719869,
      "decision": "review"
    },
    {
      "id": "c5",
      "task": "classify",
      "predicted": "deps",
      "truth": "bug",
      "correct": false,
      "probabilities": {
        "infra": 0.28511888230372595,
        "bug": 0.10100054767006221,
        "deps": 0.5893633630316456,
        "timeout": 0.024517206994566273
      },
      "probability": 0.5893633630316456,
      "margin": 0.30424448072791965,
      "decision": "review"
    },
    {
      "id": "c6",
      "task": "classify",
      "predicted": "timeout",
      "truth": "deps",
      "correct": false,
      "probabilities": {
        "infra": 0.3853358392017673,
        "bug": 0.03920270027669491,
        "deps": 0.11653147610638215,
        "timeout": 0.45892998441515565
      },
      "probability": 0.45892998441515565,
      "margin": 0.07359414521338836,
      "decision": "review"
    },
    {
      "id": "k1",
      "task": "check",
      "p_yes": 0.8381,
      "truth": true,
      "correct": true,
      "probabilities": {
        "yes": 0.838098496712648,
        "no": 0.16190150328735198
      },
      "probability": 0.838098496712648,
      "margin": 0.676196993425296,
      "decision": "review"
    },
    {
      "id": "k2",
      "task": "check",
      "p_yes": 0.0336,
      "truth": false,
      "correct": true,
      "probabilities": {
        "yes": 0.033631751444121706,
        "no": 0.9663682485558783
      },
      "probability": 0.9663682485558783,
      "margin": 0.9327364971117567,
      "decision": "auto"
    },
    {
      "id": "k3",
      "task": "check",
      "p_yes": 0.1561,
      "truth": true,
      "correct": false,
      "probabilities": {
        "yes": 0.15608258311437415,
        "no": 0.8439174168856258
      },
      "probability": 0.8439174168856258,
      "margin": 0.6878348337712517,
      "decision": "review"
    },
    {
      "id": "k4",
      "task": "check",
      "p_yes": 0.0033,
      "truth": false,
      "correct": true,
      "probabilities": {
        "yes": 0.0032750149239981507,
        "no": 0.9967249850760018
      },
      "probability": 0.9967249850760018,
      "margin": 0.9934499701520036,
      "decision": "auto"
    },
    {
      "id": "s1",
      "task": "score",
      "predicted": "trivial",
      "truth": "trivial",
      "correct": true,
      "probabilities": {
        "0": 0.3235178702764927,
        "1": 0.5142081747448953,
        "2": 0.08893799071054598,
        "3": 0.07333596426806592
      },
      "probability": 0.5142081747448953,
      "margin": 0.19069030446840263,
      "decision": "review"
    },
    {
      "id": "s2",
      "task": "score",
      "predicted": "minor",
      "truth": "critical",
      "correct": false,
      "probabilities": {
        "0": 0.03172820466457735,
        "1": 0.08723892256258753,
        "2": 0.2846454876153561,
        "3": 0.5963873851574791
      },
      "probability": 0.5963873851574791,
      "margin": 0.31174189754212306,
      "decision": "review"
    }
  ]
}
```
