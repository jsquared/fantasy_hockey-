import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


# ======================
# CONFIG
# ======================
GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"
TEAM_KEY = "465.l.33140.t.11"
START_WEEK = 1
END_WEEK = 12
OUTPUT_FILE = "docs/analysis.json"


# ======================
# AUTH (NON-INTERACTIVE)
# ======================
print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_env=True)

# ======================
# INIT API OBJECTS
# ======================
gm = yfa.Game(oauth, GAME_CODE)
lg = gm.league(LEAGUE_ID)

print(f"🏒 League: {lg.settings()['name']}")
print(f"📅 Analyzing weeks {START_WEEK} → {END_WEEK}")
print(f"👥 Team key: {TEAM_KEY}")

team = yfa.Team(oauth, TEAM_KEY)


# ======================
# DATA STRUCTURES
# ======================
weekly_stats = {}
total_stats = {}


# ======================
# MAIN LOOP
# ======================
for week in range(START_WEEK, END_WEEK + 1):
    print(f"🗂️ Week {week}")
    weekly_totals = {}

    try:
        players = team.roster(week=week)
    except Exception as e:
        print(f"⚠️ Failed to load roster for week {week}: {e}")
        weekly_stats[str(week)] = {}
        continue

    for player in players:
        player_key = player["player_key"]

        try:
            stats = team.player_stats(player_key, week=week)
        except Exception:
            continue

        for stat_name, value in stats.items():
            try:
                val = float(value)
            except (TypeError, ValueError):
                continue

            weekly_totals[stat_name] = weekly_totals.get(stat_name, 0) + val
            total_stats[stat_name] = total_stats.get(stat_name, 0) + val

    weekly_stats[str(week)] = weekly_totals


# ======================
# OUTPUT
# ======================
output = {
    "league": lg.settings()["name"],
    "team_key": TEAM_KEY,
    "weeks_analyzed": END_WEEK,
    "total_stats": total_stats,
    "weekly_stats": weekly_stats,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

with open(OUTPUT_FILE, "w") as f:
    json.dump(output, f, indent=2)

print("✅ analysis.json updated successfully")
