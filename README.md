# Fleet Operations Analytics

**A data analytics project applying flight-hour, readiness, and maintenance analysis to a simulated 50-aircraft fleet — the same category of analysis I performed operationally over 5.5 years as an Operations Officer and Head of Flight Control & Standardization Department in UAV operations.**

## Why this project

In my military career I tracked flight hours, aircraft availability, maintenance events, and personnel readiness across a 50-aircraft fleet to support standardization and command-level decisions. This project rebuilds that same type of analysis — cleaning, SQL, and visualization — end to end, using Python, SQL, and pandas, to demonstrate the technical side of that experience.

## A note on the data

**This dataset is simulated, not real.** Real operational/military data is confidential, and this project environment doesn't have general internet access to pull a substitute public dataset, so I generated one instead: a realistic 50-aircraft, 5-unit fleet (400+ personnel) with ~36,700 flight-log records (2021–2025), ~1,080 maintenance events, and ~1,620 personnel qualification exams — built with genuine statistical structure (weather-driven completion rates, seasonal flying patterns, aircraft-level reliability differences, maintenance tied to usage) so the analysis techniques are directly transferable to real data. The exact generation logic is in [`generate_data.py`](generate_data.py) — nothing here is dressed up to look like a real published dataset.

## What's in this repo

```
data/                    4 CSVs: aircraft, flight_logs, maintenance_events, personnel_exams
generate_data.py         Synthetic data generator (documented, seeded/reproducible)
analysis.py              Full pipeline: clean -> SQLite -> SQL queries -> charts -> export
notebook/
  fleet_ops_analysis.ipynb   The main deliverable: narrated, executed analysis notebook
charts/                  5 PNG charts (also embedded in the notebook)
fleet_ops.db             SQLite database (all 4 tables, ready to query)
dashboard_export.csv     Flat, joined table for building an interactive Tableau Public dashboard
```

## Method

1. **Clean** — type coercion, dropping implausible values, defensive checks (mirrors real ingestion pipelines).
2. **SQL** — loaded into SQLite; all core analysis (yearly hours, unit-level readiness, aircraft-level reliability via joins, weather impact, personnel pass rates) run as SQL, not just pandas `.groupby()`.
3. **Visualize** — matplotlib charts for trend, comparison, and composition views.
4. **Export** — a flat joined CSV for an interactive Tableau Public dashboard (see below).

## Key findings

- **Weather is the single biggest driver of mission completion**: 81.7% completion in clear weather vs. 43.3% in poor weather.
- **Completion rate varies meaningfully by unit** (72.5%–76.7%) — a standardization-relevant gap worth investigating (allocation, crew experience, or local procedure).
- **A small subset of aircraft account for a disproportionate share of maintenance events and downtime** — the SQL query in the notebook surfaces exactly which tail numbers should be maintenance-review priorities.
- **Technical issues, not weather, are the leading cause of aborted sorties overall.**

## Tools

Python (pandas, sqlite3, matplotlib), SQL, and Tableau Public (for the interactive dashboard built from `dashboard_export.csv`).

## Next steps

- Interactive Tableau Public dashboard (in progress).
- A simple predictive model for sortie-completion probability given weather and aircraft reliability.
