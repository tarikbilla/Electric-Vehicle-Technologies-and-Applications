# Product Requirements Document (PRD)

**Project:** Modelling and Simulation of an Electric Vehicle
**Course:** Electric Vehicle Technologies & Applications (THM)
**Source brief:** `DOCS/Semester project.pdf`
**Toolchain:** Python
**Status:** v1.1 — implemented, independently audited and revalidated

---

## 1. Purpose

Build a reproducible Python simulation of a commercially available battery-electric vehicle (BEV) that (a) derives its speed and acceleration characteristics from a longitudinal-dynamics and powertrain model, (b) runs the vehicle over a standardised driving profile, and (c) predicts the achievable range on a full battery. Results feed a 12–20 page report and a ~20 minute presentation.

## 2. Scope

**In scope**

- One reference vehicle with a documented parameter set.
- Quasi-static longitudinal vehicle model (traction, resistance forces, rotational inertia).
- Powertrain envelope: motor torque/power limits, single-speed reduction, efficiency chain, regenerative braking with limits.
- Speed and acceleration characteristic curves.
- One primary driving profile (WLTP Class 3b), optional secondary profile for comparison.
- Battery energy model (usable capacity, SOC, auxiliary load) and range calculation.
- Assumption register with every non-datasheet value clearly flagged (rendered in **red** in the report).

**Out of scope**

- Thermal, electrochemical or ageing battery models.
- Lateral dynamics, suspension, NVH, controls tuning.
- Charging behaviour and grid interaction.
- Real-time or hardware-in-the-loop execution.

## 3. Reference Vehicle (proposed)

**Tesla Model 3 RWD (2024 model year, LFP battery, approx. 60 kWh)** — global best-selling BEV, WLTP- and EPA-certified, with extensive public data (homologation documents, EPA test reports, independent teardowns and measurements). Alternative: Volkswagen ID.3 Pro Performance.

Required parameter set (values to be taken from manufacturer/homologation data; anything estimated is an *assumption*):

| Group | Parameters |
|---|---|
| Mass & geometry | Curb mass, payload for test, rotational mass factor λ, wheel dynamic radius, frontal area A |
| Aerodynamics & tyres | Drag coefficient C_d, rolling-resistance coefficient f_r, air density ρ |
| Motor & drivetrain | Peak/continuous torque and power, base speed, max motor speed, gear ratio, η_gear, η_motor, η_inverter |
| Battery | Gross and usable capacity, nominal voltage, discharge/charge power limits, SOC window |
| Regeneration & auxiliaries | Max regen power/torque, regen efficiency, constant auxiliary load (HVAC, 12 V systems) |
| Published references | 0–100 km/h time, top speed, WLTP combined range and consumption |

## 4. Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Load all vehicle and environment parameters from a single versioned file (YAML/JSON); each entry carries `source` and `assumed: true/false`. | Done — `parameters.py` |
| FR-2 | Compute tractive demand from the road-load equation: F = m·a·λ + m·g·f_r·cos α + ½·ρ·C_d·A·v² + m·g·sin α. | Done — `roadload.py`. Implements both the textbook decomposition and the regulatory coastdown form `F0 + F1·v + F2·v²`, which is the default for energy work. The two differ by 15–19 % above 80 km/h. |
| FR-3 | Model the motor as a torque-limited region below base speed and a power-limited region above it, mapped through the gear ratio and wheel radius to tractive force at the wheel. | Done — `powertrain.py` |
| FR-4 | Derive and plot: tractive force and resistance forces vs speed, maximum acceleration vs speed, and the 0–100 km/h time-speed trace; report top speed (traction-limited or limiter-bound). | Done — `performance.py` |
| FR-5 | Implement the WLTP Class 3b cycle (1800 s, 1 Hz) from tabulated data; support loading any other 1 Hz speed profile. | Done — `cycles.py`. The official 1800-point table is not redistributed; the profile is synthesised to within 0.5 % of every published phase statistic and flagged as an assumption. An official CSV dropped into `data/cycles/` overrides it. |
| FR-6 | Run a time-stepped (1 s) simulation over the profile computing wheel power, motor power, battery power (traction and regen) and auxiliary load. | Done — `simulation.py` |
| FR-7 | Integrate battery energy and SOC; enforce motor, battery and regen power limits; flag any time step where the vehicle cannot follow the profile. | Done — `simulation.py`, `battery.py` |
| FR-8 | Report cycle energy consumption (kWh/100 km, Wh/km) and range on a full battery, defined as usable energy ÷ net consumption per km, cross-checked by repeating the cycle until SOC reaches the lower limit. | Done — `rangecalc.py` |
| FR-9 | Produce publication-quality figures (PNG/SVG, SI units, labelled axes) and a results table for the report. | Done — `plotting.py` |
| FR-10 | Export an assumption register (parameter, value, rationale) for direct inclusion in the report in red. | Done — `report.py` |

## 5. Non-Functional Requirements

- **Language/stack:** Python ≥ 3.11; `numpy`, `scipy`, `pandas`, `matplotlib`, `pyyaml`, `pytest`.
- **Reproducibility:** one command (`python scripts/run_all.py`) regenerates every figure and table; pinned dependencies in `requirements.txt`.
- **Units:** SI internally; conversions only at I/O boundaries.
- **Quality:** unit tests for road-load, motor envelope and energy integration; type hints; docstrings.
- **Structure:** installable package (`src/evsim/`), separated data, scripts, tests and report assets.

## 6. Acceptance Criteria — measured

| Check | Target | Measured | Result |
|---|---|---|---|
| Simulated 0–100 km/h | within ±10 % | 6.14 s against 6.1 s, +0.7 % | Pass |
| Simulated top speed | within ±5 %, or the limiter | 201 km/h, set by the electronic limiter | Pass |
| WLTP range on a full battery | within ±10 % | 508 km against 513 km, −0.9 % | Pass |
| Cycle consumption | within ±10 % | 11.45 against 11.70 kWh/100 km, −2.1 % | Pass |
| Profile tracking | zero unmet speed points | 0 unmet, 0 limited, tracking error 0.000 km/h | Pass |
| Assumption register | every assumed value listed and shown in red | 32 of 49 parameters, each with its basis | Pass |
| Reproducibility | one command from a clean environment | `python scripts/run_all.py`, 80 s | Pass |
| Tests | model verified against hand calculations | 125 tests, all passing | Pass |

Independent checks that were **not** used in any calibration:

| Check | Simulated | Reference |
|---|---|---|
| Steady 100 km/h consumption | 148 Wh/km | 140–150 Wh/km measured |
| Steady 130 km/h consumption | 214 Wh/km | 190–210 Wh/km measured |
| Wheel-level energy conservation | residual 9e-10 J | exact |
| Battery energy balance closes | gap 1e-7 J | exact |
| Two range methods agree | 0.64 % | same physics, different route |

Beyond the brief, two things were added because a result resting on 32 assumed
parameters needs them: a sensitivity study over every assumption, and a second
range method that cross-checks the first.

## 7. Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Python repository (model, data, tests, run script, README) | Done — 15 modules, 125 tests |
| 2 | Figures: characteristic curves, driving profile, power and energy against time, SOC against distance | Done — 13 figures, PNG and SVG |
| 3 | Report, 12–20 pages: introduction, vehicle and parameters, model derivation, driving profile, results, validation, assumptions and sensitivity, conclusion | Done — `results/report/report.md`, ten sections, ~3 200 words, 12 figures, renders to 12–16 pages |
| 4 | Presentation slides, about 20 minutes | Done — `results/report/presentation.md`, 17 slides with timed speaker notes |

Both documents are generated from the simulation results, so their numbers,
tables and figures cannot drift out of step with the code.

## 8. Milestones

| Week | Milestone |
|---|---|
| 1 | Vehicle selected, parameter file and assumption register complete |
| 2 | Road-load and powertrain model; characteristic curves validated (0–100 km/h, top speed) |
| 3 | WLTP cycle simulation, energy and range results; sensitivity study (mass, C_d, aux load, regen) |
| 4 | Report and presentation finalised; final code freeze |

**Deadline (per brief):** at the latest one week before 15 September, i.e. 8 September. Confirm the applicable year with the course lead.

## 9. Risks & Mitigations

- **Missing manufacturer data** — Tesla does not publish motor torque, gear ratio, usable battery capacity or efficiency maps officially → use EPA application documents, independent measurements and literature-typical values, flag every such value as an assumption, and run a sensitivity study.
- **Range mismatch vs WLTP figure** → check auxiliary load, regen assumptions and mass; WLTP certification uses defined test mass and no HVAC.
- **Scope creep** (thermal, detailed efficiency maps) → keep constant-efficiency baseline; add refinements only if time permits.

## 10. Resolved Questions

1. **Vehicle and variant.** Tesla Model 3 RWD, Highland (2024 model year),
   European market, LFP battery, 18-inch wheels. Chosen because it is
   WLTP-certified and has the deepest body of independent measurement.
2. **Second driving profile.** NEDC is implemented alongside WLTP and
   reconstructed exactly from UNECE R83 Annex 4a. It shows the vehicle covering
   2.9 % more range than on WLTP, which is the expected direction given how much
   gentler the older cycle is.
3. **Report language and template.** Left to the author. The generated
   `results/report/results.md` supplies the figures, tables and headline numbers
   for the 12–20 page submission; it is not itself the report.

## 11. Revalidation (v1.1)

The v1.0 model was independently audited against the brief and the code was
reviewed for correctness. The audit found defects that the test suite had not
caught, all since fixed:

| Finding | Effect | Resolution |
|---|---|---|
| Windage dominated drive-unit loss at cruise | 79 % efficiency where a real unit gives ~88 % | Loss coefficients refitted to seven realistic operating points |
| Textbook road load has no linear term and uses a wind-tunnel drag coefficient | Under-predicted running resistance by 15–19 % above 80 km/h | Regulatory coastdown form added and made the default |
| Coastdown rolling term did not scale with load | Payload appeared almost free | Constant term scaled by the ratio to the coastdown test mass |
| Battery power clipping did not re-solve the speed | A power-limited car "followed" the cycle on energy the pack never supplied, reporting 893 km | Every limit now resolved before the step is committed |
| Loop accumulators and the power trace used different quantities | 23.6 % divergence once any limit bound | Both now accumulate the applied power |
| Analytic range mixed terminal and open-circuit energy | 2.4 % of the "method disagreement" was a unit error | Both methods now divide at the open-circuit level |
| Usable capacity ignored a narrowed SOC window | A narrowed window silently under-delivered range | Capacity scaled by the window width |
| Sensitivity varied parameters the active model ignores | Tornado chart would show silent zeros | Case list built from the active road-load model, with a test asserting no case is inert |
| Stop time assumed a uniform time grid | 29× error on a ragged CSV | Per-sample interval weighting |
| Drive-unit loss inferred by subtraction in the energy chart | Loss bar 3× too large | Measured directly in the simulator |

Validation improved on every measure as a result: range from −3.2 % to −0.9 %,
cycle consumption from +0.8 % to −2.1 %, and the two range methods from 2.4 %
apart to 0.6 %.

## 12. What Was Delivered

- Installable Python package under `src/evsim/` (15 modules).
- Vehicle parameter file with provenance and an assumed flag on every value.
- WLTC Class 3b synthesised to within 0.5 % of every published statistic, and
  NEDC reconstructed exactly. Either can be replaced by an official CSV.
- 13 figures as PNG and SVG, 8 CSV tables.
- The written report and the presentation deck, both generated from the results.
- 125 tests.

See [`../README.md`](../README.md) for the results and how to run it.
