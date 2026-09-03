"""
Synthetic fleet-operations data generator.

NOTE ON DATA PROVENANCE: This dataset is SIMULATED. It is not real military
or proprietary data (which is confidential) and not a scraped/downloaded
public dataset (this environment's network egress does not allow fetching
external files). It is generated with realistic statistical patterns
(seasonality, weather effects, maintenance-driven downtime, aircraft-level
reliability differences) so the analysis techniques applied to it -
cleaning, SQL joins, aggregation, trend detection - are genuinely
transferable to real operational data. This is disclosed in the README.
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(42)

# ---------------------------------------------------------------
# 1. AIRCRAFT (fleet of 40, across 5 units)
# ---------------------------------------------------------------
N_AIRCRAFT = 50
UNITS = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
AIRCRAFT_TYPES = ["Class-I Recon", "Class-II Multirole", "Class-III Strike"]

aircraft = pd.DataFrame({
    "aircraft_id": [f"AC-{i:03d}" for i in range(1, N_AIRCRAFT + 1)],
    "aircraft_type": rng.choice(AIRCRAFT_TYPES, N_AIRCRAFT, p=[0.45, 0.35, 0.20]),
    "unit": [UNITS[i % 5] for i in range(N_AIRCRAFT)],
    "acquisition_year": rng.integers(2016, 2023, N_AIRCRAFT),
})
# hidden per-aircraft reliability factor (0.6-1.0) used only to drive simulation
reliability = rng.uniform(0.65, 1.0, N_AIRCRAFT)
aircraft_reliability = dict(zip(aircraft["aircraft_id"], reliability))

# ---------------------------------------------------------------
# 2. FLIGHT LOGS (2021-01-01 to 2025-12-31, ~5 years)
# ---------------------------------------------------------------
START = date(2021, 1, 1)
END = date(2025, 12, 31)
N_DAYS = (END - START).days + 1

WEATHER = ["Clear", "Marginal", "Poor"]
MISSION_TYPES = ["Training", "Operational", "Reconnaissance", "Transit"]

flight_rows = []
flight_id = 1
for _, row in aircraft.iterrows():
    ac_id = row["aircraft_id"]
    rel = aircraft_reliability[ac_id]
    # each aircraft flies roughly 2-4 sorties/week on average, seasonally varying
    d = START
    while d <= END:
        month = d.month
        # more flying in spring/summer (training season), less in winter
        seasonal_factor = 1.3 if month in (4, 5, 6, 7, 8, 9) else 0.7
        daily_prob = 0.40 * seasonal_factor  # base chance a sortie happens this day
        if rng.random() < daily_prob:
            weather = rng.choice(WEATHER, p=[0.65, 0.25, 0.10])
            mission = rng.choice(MISSION_TYPES, p=[0.45, 0.30, 0.15, 0.10])
            duration = float(np.clip(rng.normal(3.2, 1.1), 0.5, 9.0))
            # completion probability lower in poor weather / low-reliability aircraft
            complete_prob = rel * (1.0 if weather == "Clear" else 0.85 if weather == "Marginal" else 0.55)
            completed = rng.random() < complete_prob
            abort_reason = None
            if not completed:
                abort_reason = rng.choice(
                    ["Weather", "Technical", "Other"],
                    p=[0.5, 0.4, 0.1] if weather != "Clear" else [0.1, 0.75, 0.15],
                )
                duration = round(duration * rng.uniform(0.1, 0.5), 1)
            flight_rows.append((
                flight_id, ac_id, row["unit"], d.isoformat(), round(duration, 1),
                mission, weather, completed, abort_reason,
            ))
            flight_id += 1
        d += timedelta(days=1)

flights = pd.DataFrame(flight_rows, columns=[
    "flight_id", "aircraft_id", "unit", "flight_date", "flight_hours",
    "mission_type", "weather_condition", "completed", "abort_reason",
])

# ---------------------------------------------------------------
# 3. MAINTENANCE EVENTS (scheduled + unscheduled, tied loosely to usage)
# ---------------------------------------------------------------
maint_rows = []
event_id = 1
hours_by_ac = flights.groupby("aircraft_id")["flight_hours"].sum()
for ac_id in aircraft["aircraft_id"]:
    rel = aircraft_reliability[ac_id]
    total_hours = hours_by_ac.get(ac_id, 0)
    # scheduled maintenance roughly every 150 flight hours
    n_scheduled = max(1, int(total_hours // 150))
    # unscheduled maintenance more frequent for lower-reliability aircraft
    n_unscheduled = max(1, int((1 - rel) * 40 + rng.integers(0, 5)))
    for _ in range(n_scheduled):
        d = START + timedelta(days=int(rng.integers(0, N_DAYS)))
        maint_rows.append((event_id, ac_id, d.isoformat(), "Scheduled",
                            round(rng.uniform(1, 4), 1), "Routine Inspection"))
        event_id += 1
    for _ in range(n_unscheduled):
        d = START + timedelta(days=int(rng.integers(0, N_DAYS)))
        issue = rng.choice(["Engine", "Avionics", "Airframe", "Sensor/Payload", "Other"],
                            p=[0.25, 0.25, 0.2, 0.2, 0.1])
        downtime = round(float(np.clip(rng.exponential(3), 0.5, 21)), 1)
        maint_rows.append((event_id, ac_id, d.isoformat(), "Unscheduled", downtime, issue))
        event_id += 1

maintenance = pd.DataFrame(maint_rows, columns=[
    "event_id", "aircraft_id", "event_date", "maintenance_type",
    "downtime_days", "issue_category",
])

# ---------------------------------------------------------------
# 4. PERSONNEL QUALIFICATION EXAMS
# ---------------------------------------------------------------
N_CREW = 420
crew_ids = [f"CR-{i:03d}" for i in range(1, N_CREW + 1)]
crew_units = {cid: UNITS[i % 5] for i, cid in enumerate(crew_ids)}

exam_rows = []
exam_id = 1
for cid in crew_ids:
    n_exams = rng.integers(2, 7)
    for _ in range(n_exams):
        d = START + timedelta(days=int(rng.integers(0, N_DAYS)))
        exam_type = rng.choice(["Initial", "Recurrent"], p=[0.25, 0.75])
        score = float(np.clip(rng.normal(82, 9), 40, 100))
        result = "Pass" if score >= 70 else "Fail"
        exam_rows.append((exam_id, cid, crew_units[cid], d.isoformat(), exam_type, round(score, 1), result))
        exam_id += 1

exams = pd.DataFrame(exam_rows, columns=[
    "exam_id", "crew_id", "unit", "exam_date", "exam_type", "score", "result",
])

# ---------------------------------------------------------------
# Save
# ---------------------------------------------------------------
aircraft.to_csv("data/aircraft.csv", index=False)
flights.to_csv("data/flight_logs.csv", index=False)
maintenance.to_csv("data/maintenance_events.csv", index=False)
exams.to_csv("data/personnel_exams.csv", index=False)

print(f"aircraft: {len(aircraft)} rows")
print(f"flight_logs: {len(flights)} rows")
print(f"maintenance_events: {len(maintenance)} rows")
print(f"personnel_exams: {len(exams)} rows")
