import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# ---------- OAuth bootstrap ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()

# ---------- RAW API CALL (VERSION SAFE) ----------
raw = league.yhandler.get(
    f"team/{team_key}/roster/players/stats;type=season",
    {}
)

team_block = raw["team"][1]
players = (
    team_block["roster"]["0"]["players"]
)

roster_output = []

for p in players.values():
    pdata = p["player"][1]

    stats = {}
    for s in pdata.get("player_stats", {}).get("stats", []):
        stat = s.get("stat", {})
        sid = stat.get("stat_id")
        val = stat.get("value")

        if sid is None:
            continue

        try:
            stats[str(sid)] = float(val)
        except (TypeError, ValueError):
            stats[str(sid)] = val

    roster_output.append({
        "player_id": pdata.get("player_id"),
        "name": pdata.get("name", {}).get("full"),
        "position": pdata.get("primary_position"),
        "selected_position": pdata.get("selected_position", {}).get("position"),
        "editorial_team": pdata.get("editorial_team_abbr"),
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

print("✅ docs/roster.json written with SEASON stats")
