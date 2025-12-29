import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
from yfantasy_api import YahooFantasySportsQuery

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

yfs = YahooFantasySportsQuery(oauth, "nhl")

# =========================
# LOAD LEAGUE METADATA
# =========================
league_meta = yfs.get_league_metadata(LEAGUE_KEY)
league_name = league_meta.get("name", "Unknown League")

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks {START_WEEK} → {END_WEEK}")
print(f"👥 Team key: {TEAM_KEY}")

# =========================
# ANALYZE WEEKS
# =========================
weekly_stats = {}
total_stats = {}

for week in range(START_WEEK, END_WEEK + 1):
    print(f"🗂️ Week {week}")

    try:
        raw = yfs.get_team_stats(TEAM_KEY, week)
    except Exception as e:
        print(f"⚠️ Failed week {week}: {e}")
        weekly_stats[str(week)] = {}
        continue

    stats_block = raw.get("team", {}).get("team_stats", {}).get("stats", [])

    week_totals = {}

    for stat in stats_block:
        stat_id = stat.get("stat", {}).get("stat_id")
        value = stat.get("stat", {}).get("value")

        if stat_id is None or value is None:
            continue

        week_totals[str(stat_id)] = float(value)

        total_stats[str(stat_id)] = total_stats.get(str(stat_id), 0) + float(value)

    weekly_stats[str(week)] = week_totals

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
