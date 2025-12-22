import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


OUTPUT_PATH = "docs/analysis.json"


print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")
gm = yfa.Game(oauth, "nhl")

print("🏒 Loading league...")
league = gm.league()
league_name = league.settings()["name"]
current_week = int(league.current_week())

print(f"📊 League: {league_name}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# -------------------------------------------------------------------
# 1️⃣ Build STAT ID → NAME map
# -------------------------------------------------------------------
print("🗂️ Loading stat categories...")
stat_id_to_name = {}
for stat in league.stat_categories():
    stat_id_to_name[str(stat["stat_id"])] = stat["name"]

# -------------------------------------------------------------------
# 2️⃣ Get your team
# -------------------------------------------------------------------
teams = league.teams()
my_team = teams[0]
team_key = my_team.team_key

print(f"👥 Team key: {team_key}")

# -------------------------------------------------------------------
# 3️⃣ Aggregate stats across all weeks
# -------------------------------------------------------------------
stat_totals = {}
stat_weeks_counted = {}

for week in range(1, current_week + 1):
    print(f"📈 Fetching stats for week {week}...")
    week_stats = my_team.stats(week)

    for stat in week_stats["stats"]:
        stat_id = str(stat["stat_id"])
        value = stat["value"]

        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        stat_totals[stat_id] = stat_totals.get(stat_id, 0) + value
        stat_weeks_counted[stat_id] = stat_weeks_counted.get(stat_id, 0) + 1

# -------------------------------------------------------------------
# 4️⃣ Compute averages
# -------------------------------------------------------------------
averaged_stats = {}

for stat_id, total in stat_totals.items():
    weeks = stat_weeks_counted.get(stat_id, 1)
    averaged_stats[stat_id] = total / weeks

# -------------------------------------------------------------------
# 5️⃣ Split strengths & weaknesses
# -------------------------------------------------------------------
strengths = []
weaknesses = []

for stat_id, avg_value in averaged_stats.items():
    name = stat_id_to_name.get(stat_id, f"Stat {stat_id}")

    entry = {
        "stat_id": stat_id,
        "name": name,
        "average": round(avg_value, 3)
    }

    if avg_value > 0:
        strengths.append(entry)
    else:
        weaknesses.append(entry)

strengths.sort(key=lambda x: x["average"], reverse=True)
weaknesses.sort(key=lambda x: x["average"])

# -------------------------------------------------------------------
# 6️⃣ Output JSON
# -------------------------------------------------------------------
output = {
    "league": league_name,
    "team_key": team_key,
    "weeks_analyzed": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)

with open(OUTPUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print("✅ Historical analysis complete")
print(f"📄 Written to {OUTPUT_PATH}")
print(f"📦 Strength stats: {len(strengths)}")
print(f"📉 Weakness stats: {len(weaknesses)}")
