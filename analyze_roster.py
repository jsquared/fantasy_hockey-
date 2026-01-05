import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# OAuth bootstrap (CI-safe)
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()
team = league.to_team(team_key)

roster_output = []

for p in team.roster():
    pid = p["player_id"]

    try:
        raw_stats = league.player_stats(pid, "season")
    except Exception:
        raw_stats = None

    stats = {}

    # ---- NORMALIZE STAT SHAPES ----
    if isinstance(raw_stats, dict):
        for sid, val in raw_stats.items():
            try:
                stats[str(sid)] = float(val)
            except (TypeError, ValueError):
                stats[str(sid)] = val

    elif isinstance(raw_stats, list):
        for entry in raw_stats:
            if not isinstance(entry, dict):
                continue
            sid = entry.get("stat_id")
            val = entry.get("value")
            if sid is None:
                continue
            try:
                stats[str(sid)] = float(val)
            except (TypeError, ValueError):
                stats[str(sid)] = val

    roster_output.append({
        "player_id": pid,
        "name": p.get("name"),
        "position": p.get("position"),
        "selected_position": p.get("selected_position"),
        "editorial_team": p.get("editorial_team_abbr"),
        "stats": stats
    })

payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written successfully")
