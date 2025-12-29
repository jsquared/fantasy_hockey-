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
OAUTH_FILE = "oauth2.json"


# ======================
# AUTH (FILE-BASED, NON-INTERACTIVE)
# ======================
print("🔑 Authenticating with Yahoo (file-based OAuth)...")

if not os.path.exists(OAUTH_FILE):
    raise RuntimeError("❌ oauth2.json not found — workflow must create it")

oauth = OAuth2(None, None, from_file=OAUTH_FILE)


# ======================
# INIT API OBJECTS
# ======================
gm = yfa.Game(oauth, GAME_CODE)
lg = gm.league(LEAGUE_ID)
team = yfa.Team(oauth, TEAM_KEY)

print(f"🏒 League: {lg.settings()['name']}")
print(f"📅 Analyzing weeks {START_WEEK} → {END_WEEK}")
print(f"👥 Team key: {TEAM_KEY}")


# ======================
# DATA STRUCTURES
# ======================
weekly_stats = {}
total_stats = {}


# ======================
# MAIN LOOP (PLAYER STATS → TEAM TOTALS)
# ======================
for week in range(START_WEEK, END_WEEK + 1):
    print(f"🗂️ Week {week}")
    weekly_totals = {}

    try:
        players = team.roster(week=week)
    except Exception as e:
        print(f"⚠️ Roster load failed: {e}")
        weekly_stats[str(week)] = {}
        continue

    for player in players:
        player_key = player["player_key"]

        try:
            stats = team.player_stats(player_key, week=week)
        except Exception:
            continue

        for stat, value in stats.items():
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue

            weekly_totals[stat] = weekly_totals.get(stat, 0) + v
            total_stats[stat] = total_stats.get(stat, 0) + v

    weekly_stats[str(week)] = weekly_totals


# ======================
# WRITE OUTPUT
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

print("✅ analysis.json written successfully")
