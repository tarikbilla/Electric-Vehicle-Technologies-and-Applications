# Driving cycle data

Drop an official cycle table here to use it instead of the generated one.

## WLTC Class 3b

Save the official trace as `wltc_class3b.csv` in this directory and it is picked
up automatically in place of the synthesised profile, which is then no longer
flagged as an assumption.

Required format — 1 Hz, two columns:

```csv
time_s,speed_kph
0,0.0
1,0.0
2,0.0
...
1800,0.0
```

The official 1800-point table is published in UNECE Global Technical Regulation
No. 15 (WLTP), Annex 1. It is not redistributed in this repository.

## Any other profile

Any CSV in the same format can be run directly:

```bash
python scripts/run_all.py --cycle data/cycles/my_profile.csv
```

The NEDC needs no file. It is reconstructed exactly from its regulatory
definition in `src/evsim/cycles.py`.
