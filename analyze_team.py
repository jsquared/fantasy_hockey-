import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------------- CONFIG ----------------
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
OUTPUT_FILE = "docs/analysis.json"

# ---------------- AUTH ------------------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)
    print("🔐 oauth2.json created from environment variable")

print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------------- OBJECTS ----------------
gm = yfa.Game(oauth, GAME_CODE)
league = gm.to_league(LEAGUE_ID)

settings = league.settings()
league_name = settings.get("name", "Unknown League")
current_week = league.current_week()

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------------- TEAM ----------------
teams = league.teams()
team_meta = next(iter(teams.values()))
TEAM_KEY = team_meta["team_key"]

print(f"👥 Team key: {TEAM_KEY}")

# ---------------- ANALYSIS ----------------
team_totals = {}
weekly_stats = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")

    matchups = league.matchups(week)
    week_data = {}

    for matchup in matchups:
        teams_block = matchup["teams"]

        for team in teams_block:
            if team["team_key"] != TEAM_KEY:
                continue

            stats = team["team_stats"]["stats"]

            for s in stats:
                stat = s["stat"]
                stat_id = str(stat["stat_id"])
                value = stat.get("value", 0)

                week_data[stat_id] = value

                try:
                    team_totals[stat_id] = team_totals.get(stat_id, 0) + float(value)
                except (TypeError, ValueError):
                    pass

    weekly_stats[str(week)] = week_data

# ---------------- OUTPUT ----------------
payload = {
    "league": league_name,
    "team_key": TEAM_KEY,
    "weeks_analyzed": current_week,
    "total_stats": team_totals,
    "weekly_stats": weekly_stats,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
