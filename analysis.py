"""
Fleet Operations Analytics — end-to-end analysis.
Loads the raw CSVs, cleans/joins them, runs SQL queries in SQLite,
and produces summary charts + an aggregated export for Tableau Public.
"""
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"figure.dpi": 120, "axes.grid": True, "grid.alpha": 0.3})

# -----------------------------------------------------------------
# 1. LOAD
# -----------------------------------------------------------------
aircraft = pd.read_csv("data/aircraft.csv")
flights = pd.read_csv("data/flight_logs.csv", parse_dates=["flight_date"])
maintenance = pd.read_csv("data/maintenance_events.csv", parse_dates=["event_date"])
exams = pd.read_csv("data/personnel_exams.csv", parse_dates=["exam_date"])

print("Raw shapes:", aircraft.shape, flights.shape, maintenance.shape, exams.shape)

# -----------------------------------------------------------------
# 2. CLEAN
# -----------------------------------------------------------------
# normalize booleans / types
flights["completed"] = flights["completed"].astype(bool)
flights["month"] = flights["flight_date"].values.astype("datetime64[M]")
flights["year"] = flights["flight_date"].dt.year

# sanity checks — drop impossible values (defensive cleaning even though
# the generator shouldn't produce them; this mirrors what real ingestion
# pipelines need to do)
before = len(flights)
flights = flights[(flights["flight_hours"] >= 0) & (flights["flight_hours"] <= 12)]
print(f"Dropped {before - len(flights)} rows with implausible flight_hours")

maintenance = maintenance[maintenance["downtime_days"] > 0]

# -----------------------------------------------------------------
# 3. LOAD INTO SQLITE FOR SQL-BASED ANALYSIS
# -----------------------------------------------------------------
conn = sqlite3.connect("fleet_ops.db")
aircraft.to_sql("aircraft", conn, if_exists="replace", index=False)
flights.drop(columns=["month"]).to_sql("flight_logs", conn, if_exists="replace", index=False)
maintenance.to_sql("maintenance_events", conn, if_exists="replace", index=False)
exams.to_sql("personnel_exams", conn, if_exists="replace", index=False)

# -----------------------------------------------------------------
# 4. SQL QUERIES — the kind of standardization/reporting queries
#    a Flight Control & Standardization function runs routinely
# -----------------------------------------------------------------

q_yearly_hours = """
SELECT strftime('%Y', flight_date) AS year,
       ROUND(SUM(flight_hours), 1) AS total_flight_hours,
       COUNT(*) AS sorties
FROM flight_logs
GROUP BY year
ORDER BY year;
"""
yearly_hours = pd.read_sql(q_yearly_hours, conn)
print("\nYearly flight hours:\n", yearly_hours)

q_unit_readiness = """
SELECT f.unit,
       ROUND(100.0 * SUM(CASE WHEN f.completed THEN 1 ELSE 0 END) / COUNT(*), 1) AS completion_rate_pct,
       ROUND(SUM(f.flight_hours), 1) AS total_flight_hours,
       COUNT(DISTINCT f.aircraft_id) AS aircraft_in_unit
FROM flight_logs f
GROUP BY f.unit
ORDER BY completion_rate_pct DESC;
"""
unit_readiness = pd.read_sql(q_unit_readiness, conn)
print("\nUnit-level completion rate:\n", unit_readiness)

q_aircraft_reliability = """
SELECT f.aircraft_id,
       a.aircraft_type,
       a.unit,
       ROUND(SUM(f.flight_hours), 1) AS total_flight_hours,
       ROUND(100.0 * SUM(CASE WHEN f.completed THEN 1 ELSE 0 END) / COUNT(*), 1) AS completion_rate_pct,
       COUNT(DISTINCT m.event_id) AS maintenance_events,
       ROUND(SUM(DISTINCT m.downtime_days), 1) AS total_downtime_days
FROM flight_logs f
JOIN aircraft a ON a.aircraft_id = f.aircraft_id
LEFT JOIN maintenance_events m ON m.aircraft_id = f.aircraft_id
GROUP BY f.aircraft_id
ORDER BY completion_rate_pct ASC
LIMIT 10;
"""
worst_aircraft = pd.read_sql(q_aircraft_reliability, conn)
print("\n10 lowest-completion-rate aircraft (maintenance priority candidates):\n", worst_aircraft)

q_weather_impact = """
SELECT weather_condition,
       COUNT(*) AS sorties,
       ROUND(100.0 * SUM(CASE WHEN completed THEN 1 ELSE 0 END) / COUNT(*), 1) AS completion_rate_pct
FROM flight_logs
GROUP BY weather_condition
ORDER BY completion_rate_pct DESC;
"""
weather_impact = pd.read_sql(q_weather_impact, conn)
print("\nWeather impact on mission completion:\n", weather_impact)

q_abort_reasons = """
SELECT abort_reason, COUNT(*) AS n
FROM flight_logs
WHERE completed = 0
GROUP BY abort_reason
ORDER BY n DESC;
"""
abort_reasons = pd.read_sql(q_abort_reasons, conn)
print("\nAbort reasons:\n", abort_reasons)

q_exam_pass_rate = """
SELECT unit,
       COUNT(*) AS exams_taken,
       ROUND(100.0 * SUM(CASE WHEN result = 'Pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pass_rate_pct,
       ROUND(AVG(score), 1) AS avg_score
FROM personnel_exams
GROUP BY unit
ORDER BY pass_rate_pct DESC;
"""
exam_pass_rate = pd.read_sql(q_exam_pass_rate, conn)
print("\nPersonnel qualification pass rate by unit:\n", exam_pass_rate)

q_monthly_trend = """
SELECT strftime('%Y-%m', flight_date) AS ym,
       ROUND(SUM(flight_hours), 1) AS total_hours,
       ROUND(100.0 * SUM(CASE WHEN completed THEN 1 ELSE 0 END) / COUNT(*), 1) AS completion_rate_pct
FROM flight_logs
GROUP BY ym
ORDER BY ym;
"""
monthly_trend = pd.read_sql(q_monthly_trend, conn)

# -----------------------------------------------------------------
# 5. CHARTS
# -----------------------------------------------------------------

# Chart 1: monthly flight hours + completion rate trend
fig, ax1 = plt.subplots(figsize=(11, 4.5))
ax1.plot(pd.to_datetime(monthly_trend["ym"]), monthly_trend["total_hours"], color="#1F3864", linewidth=1.6)
ax1.set_ylabel("Total flight hours / month", color="#1F3864")
ax1.set_title("Fleet Flight Hours & Mission Completion Rate (2021–2025)")
ax2 = ax1.twinx()
ax2.plot(pd.to_datetime(monthly_trend["ym"]), monthly_trend["completion_rate_pct"], color="#C0392B", linewidth=1.2, alpha=0.8)
ax2.set_ylabel("Completion rate (%)", color="#C0392B")
fig.tight_layout()
fig.savefig("charts/01_monthly_hours_completion.png")
plt.close(fig)

# Chart 2: completion rate by unit
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.bar(unit_readiness["unit"], unit_readiness["completion_rate_pct"], color="#1F3864")
ax.set_ylabel("Completion rate (%)")
ax.set_title("Mission Completion Rate by Unit")
ax.set_ylim(0, 100)
fig.tight_layout()
fig.savefig("charts/02_completion_by_unit.png")
plt.close(fig)

# Chart 3: weather impact
fig, ax = plt.subplots(figsize=(6, 4.5))
order = ["Clear", "Marginal", "Poor"]
wi = weather_impact.set_index("weather_condition").reindex(order).reset_index()
ax.bar(wi["weather_condition"], wi["completion_rate_pct"], color=["#1F3864", "#7A9BC4", "#C0392B"])
ax.set_ylabel("Completion rate (%)")
ax.set_title("Mission Completion Rate by Weather Condition")
ax.set_ylim(0, 100)
fig.tight_layout()
fig.savefig("charts/03_weather_impact.png")
plt.close(fig)

# Chart 4: abort reasons
fig, ax = plt.subplots(figsize=(6, 4.5))
ax.pie(abort_reasons["n"], labels=abort_reasons["abort_reason"], autopct="%1.0f%%",
       colors=["#1F3864", "#C0392B", "#7A9BC4"])
ax.set_title("Aborted-Sortie Reasons")
fig.tight_layout()
fig.savefig("charts/04_abort_reasons.png")
plt.close(fig)

# Chart 5: yearly flight hours by aircraft type
q_type_year = """
SELECT strftime('%Y', f.flight_date) AS year, a.aircraft_type,
       ROUND(SUM(f.flight_hours), 1) AS total_hours
FROM flight_logs f JOIN aircraft a ON a.aircraft_id = f.aircraft_id
GROUP BY year, a.aircraft_type
ORDER BY year;
"""
type_year = pd.read_sql(q_type_year, conn)
pivot = type_year.pivot(index="year", columns="aircraft_type", values="total_hours").fillna(0)
fig, ax = plt.subplots(figsize=(9, 4.5))
pivot.plot(kind="bar", stacked=True, ax=ax, color=["#1F3864", "#7A9BC4", "#C0392B"])
ax.set_ylabel("Total flight hours")
ax.set_title("Yearly Flight Hours by Aircraft Type")
fig.tight_layout()
fig.savefig("charts/05_hours_by_type.png")
plt.close(fig)

# -----------------------------------------------------------------
# 6. EXPORT FOR TABLEAU PUBLIC (one flat, analysis-ready table)
# -----------------------------------------------------------------
export = flights.merge(aircraft, on=["aircraft_id", "unit"], how="left")
export = export.drop(columns=["month"])
export.to_csv("dashboard_export.csv", index=False)

conn.close()
print("\nDone. Charts in charts/, SQLite DB at fleet_ops.db, Tableau export at dashboard_export.csv")
