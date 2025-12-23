import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------- Configuration ----------
LEAGUE_KEY = "465.l.33140"
OUTPUT_FILE = "docs/analysis.json"

# ---------- OAuth ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)
    print("🔐 oauth2.json created from environment variable")

print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------- Yahoo Objects ----------
gm = yfa.Game(oauth, "nhl")
league = gm.to_league(LEAGUE_KEY)

settings = league.settings()
league_name = settings["name"]
current_week = int(settings["current_week"])

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Resolve Your Team ----------
teams = league.teams()   # dict keyed by team_key
team_key = next(iter(teams))

print(f"👥 Team key: {team_key}")

# ---------- Aggregate Weekly Stats ----------
totals = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")

    raw = league.yhandler.get_scoreboard_raw(LEAGUE_KEY, week)

    scoreboard = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for matchup in scoreboard.values():
        teams_block = matchup["matchup"]["teams"]

        for team in teams_block.values():
            team_data = team["team"][0]

            if team_data["team_key"] != team_key:
                continue

            stats = team["team"][1]["team_stats"]["stats"]

            for stat in stats:
                sid = str(stat["stat_id"])
                val = stat["value"]

                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue

                totals[sid] = totals.get(sid, 0) + val

# ---------- Build Output ----------
stats_out = [
    {"stat_id": sid, "value": round(val, 3)}
    for sid, val in totals.items()
]

payload = {
    "league": league_name,
    "team_key": team_key,
    "weeks_analyzed": current_week,
    "stats": sorted(stats_out, key=lambda x: x["value"], reverse=True),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

# ---------- Write File ----------
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
