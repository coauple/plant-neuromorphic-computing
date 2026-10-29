# Salep Cybernetics — English summary

*The main documentation of this repository is written in Turkish ([README.md](README.md)). This page is a one-page English overview for international readers.*

## What this is

An independent research prototype exploring whether slow, sparse **electrical events of plants** can be turned into a learnable representation of the plant's condition (e.g. drought, salinity), using a **multi-compartment, spiking, fixed-point neural computation** designed to be portable to FPGA hardware.

**Status (October 2026): research prototype, not a product or a validated diagnostic.** All quantitative results come from **synthetic** data (a simulated plant and a simulated electrical layer). No claim is made about real plants beyond the one negative real-data check described below.

## What was built

- **C++17 neuromorphic core** (`salep_core/src/`): Q16.16 fixed-point arithmetic, preallocated data structures, deterministic ticks, look-up tables; no neural-network library. Currently runs on CPU; **FPGA synthesis has not been done.**
- **Mechanisms:** multi-compartment dendritic neurons; phase-locked interval resonator (PLIR) for separating rhythms on one wire; a quadratic synaptic learning rule with a persistent trace; a pattern lobe with four relational views (what / when / history / relational); a checkpoint format for the learned state.
- **Python simulation environment** (`salep_core/sim/`): soil–plant–atmosphere physics (water balance, salinity, evapotranspiration, VPD), real Aydın weather data (Open-Meteo), a stochastic event engine, a synthetic electrophysiology layer, and a live web dashboard.

## Results, including negative ones

| Finding | Outcome |
|---|---|
| Deterministic, bit-identical core | Demonstrated (synthetic) |
| Two superposed rhythms separated and phase-locked | Demonstrated (synthetic), phase error ≤ 0.03 tick |
| Six conditions give six distinct exact signatures | Demonstrated on one 250-day trajectory |
| Association accuracy 163/165 (98.8 %) | Partial: labels are derived from the same representation (circular) |
| Inference baseline 97/175 = 0.554 | Partial: drought is never recognised, always absorbed into "normal" (28/28) |
| Quadratic learning improves inference | **Not observed** (0.400, below the 0.554 baseline) |
| Conditioned response without sensor input | **Failed** (no firing in the test phase) |
| Independent evaluation vs. simple baselines | Not better: the system ties or trails them; silent on sparse causal events |
| Real plant recordings (36 *Ocimum* recordings, n = 483 windows) | **Chance level** (pooled AUC 0.493); labels are weak |

An independent evaluation with pre-frozen criteria is in `salep_core/bench/`; an internal audit (14 Oct 2026) found no hidden label leakage but identified circular labels, a single trajectory/seed, and the absence of an independent end-to-end test.

## Main limitations

Single seed and trajectory; train/test not independent; synthetic electrophysiology; weakly labelled real data; hardware claims on paper only; no closed loop.

## Planned work

Multi-seed and held-out-scenario evaluation with pre-registered criteria; real labelled data; FPGA synthesis; and a **system-level inference engine with causal modelling and forecasting**.

## Reproduce

```bash
git clone https://github.com/coauple/plant-neuromorphic-computing
cd plant-neuromorphic-computing
bash run_review.sh      # needs g++ (C++17) and python3 + numpy; ~ seconds
```

Details: [QUICKSTART.md](QUICKSTART.md), full research log: [salep_core/CLAUDE.md](salep_core/CLAUDE.md) (Turkish).

## Licence and AI disclosure

Code: PolyForm Noncommercial 1.0.0. Documentation and data outputs: CC BY-NC 4.0. Commercial use requires a separate licence from the author. Third-party data (Open-Meteo, Madariaga et al. 2024) keep their own licences. See [LICENSE-DOCS.md](LICENSE-DOCS.md). The project was developed with substantial help from an AI coding assistant; the author set the research questions and architectural decisions and approved every gate (README §13).

Author: Metehan Cafer Kılıç, independent researcher.
