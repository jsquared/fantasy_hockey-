import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# OAuth bootstrap
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()

# ---- RAW TEAM ROSTER WITH SEASON STATS ----
raw = league.yhandler.get(
    f"team/{team_key}/roster/players/stats;type=season"
)


team_block = raw["fantasy_content"]["team"][1]
players = team_block["roster"]["0"]["players"]

roster_output = []

for _, pdata in players.items():
    player = pdata["player"]

    # ---- PLAYER METADATA ----
    meta = player[0]
    pid = int(meta[1]["player_id"])
    name = meta[2]["name"]["full"]
    team_abbr = meta[7]["editorial_team_abbr"]

    # ---- SELECTED POSITION ----
    selected_position = None
    if len(player) > 1 and "selected_position" in player[1]:
        selected_position = player[1]["selected_position"][1]["position"]

    # ---- STATS ----
    stats = {}

    if len(player) > 3 and "player_stats" in player[3]:
        stat_block = player[3]["player_stats"]["stats"]
        for entry in stat_block:
            stat = entry["stat"]
            sid = stat["stat_id"]
            val = stat["value"]
            try:
                stats[sid] = float(val)
            except ValueError:
                stats[sid] = val

    roster_output.append({
        "player_id": pid,
        "name": name,
        "selected_position": selected_position,
        "editorial_team": team_abbr,
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
