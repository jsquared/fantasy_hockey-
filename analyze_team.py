import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_KEY = "465.l.33140"
TEAM_KEY = "465.l.33140.t.11"
START_WEEK = 1
END_WEEK = 12
OUTPUT_FILE = "docs/analysis.json"

# =========================
# AUTH
# =========================
print("🔑 Authenticating with Yahoo...")

oauth = OAuth2(None, None, from_env=True)
if not oauth.token_is_valid():
    oauth.refresh_access_token()

gm = yfa.Game(oauth, "nhl")
lg = gm.to_league(LEAGUE_KEY)
league_name = lg.settings().get("name", "Unknown League")

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks {START_WEEK} → {END_WEEK}")
print(f"👥 Team key: {TEAM_KEY}")

team = lg.to_team(TEAM_KEY)

# =========================
# ANALYZE WEEKS
# =========================
weekly_stats = {}
total_stats = {}

for week in range(START_WEEK, END_WEEK + 1):
    print(f"🗂️ Week {week}")
    weekly_stats[str(week)] = {}

    try:
        stats = team.stats(week)
    except Exception as e:
        print(f"⚠️ No stats for week {week}: {e}")
        continue

    if not stats:
        continue

    for stat_name, value in stats.items():
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        weekly_stats[str(week)][stat_name] = value
        total_stats[stat_name] = total_stats.get(stat_name, 0) + value

# =========================
# SAVE OUTPUT
# =========================
output = {
    "league": league_name,
    "team_key": TEAM_KEY,
    "weeks_analyzed": END_WEEK,
    "total_stats": total_stats,
    "weekly_stats": weekly_stats,
    "lastUpdated": datetime.utcnow().isoformat() + "Z",
}

os.makedirs("docs", exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(output, f, indent=2)

print("✅ Analysis complete")
