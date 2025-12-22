import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


# ---------------- CONFIG ----------------
LEAGUE_ID = "465.l.33140"
OUTPUT_PATH = "docs/analysis.json"
# ---------------------------------------


# -------------------------------------------------
# 1️⃣ OAuth (GitHub Actions safe)
# -------------------------------------------------
if "YAHOO_OAUTH_JSON" not in os.environ:
    raise RuntimeError("YAHOO_OAUTH_JSON secret not set")

with open("oauth2.json", "w") as f:
    f.write(os.environ["YAHOO_OAUTH_JSON"])

print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")


# -------------------------------------------------
# 2️⃣ Load League
# -------------------------------------------------
game = yfa.Game(oauth, "nhl")
league = game.to_league(LEAGUE_ID)

league_name = league.settings()["name"]
current_week = int(league.current_week())

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks 1 → {current_week}")


# -------------------------------------------------
# 3️⃣ Build STAT ID → NAME map (SAFE)
# -------------------------------------------------
print("🗂️ Loading stat categories...")
stat_id_to_name = {}

for stat in league.stat_categories():
    stat_id = str(stat.get("stat_id"))

    name = (
        stat.get("display_name")
        or stat.get("name")
        or f"Stat {stat_id}"
    )

    stat_id_to_name[stat_id] = name


# -------------------------------------------------
# 4️⃣ Identify your team
# -------------------------------------------------
my_team = league.teams()[0]
team_key = my_team.team_key

print(f"👥 Team key: {team_key}")


# -------------------------------------------------
# 5️⃣ Aggregate stats across ALL weeks
# -------------------------------------------------
stat_totals = {}
stat_weeks = {}

for week in range(1, current_week + 1):
    print(f"📈 Week {week}")
    weekly = my_team.stats(week)

    for stat in weekly.get("stats", []):
        stat_id = str(stat.get("stat_id"))
        value = stat.get("value")

        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        stat_totals[stat_id] = stat_totals.get(stat_id, 0) + value
        stat_weeks[stat_id] = stat_weeks.get(stat_id, 0) + 1


# -------------------------------------------------
# 6️⃣ Compute averages
# -------------------------------------------------
averages = {}
for stat_id, total in stat_totals.items():
    weeks = stat_weeks.get(stat_id, 1)
    averages[stat_id] = total / weeks


# -------------------------------------------------
# 7️⃣ Split strengths / weaknesses
# -------------------------------------------------
strengths = []
weaknesses = []

for stat_id, avg in averages.items():
    name = stat_id_to_name.get(stat_id, f"Stat {stat_id}")

    entry = {
        "stat_id": stat_id,
        "name": name,
        "average": round(avg, 3)
    }

    if avg > 0:
        strengths.append(entry)
    else:
        weaknesses.append(entry)

strengths.sort(key=lambda x: x["average"], reverse=True)
weaknesses.sort(key=lambda x: x["average"])


# -------------------------------------------------
# 8️⃣ Write output
# -------------------------------------------------
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

print("✅ docs/analysis.json updated successfully")
