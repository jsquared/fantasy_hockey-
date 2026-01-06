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

# ---- FETCH ROSTER WITH SEASON STATS ----
raw = league.yhandler.get(
    f"team/{team_key}/roster/players/stats;type=season"
)

team_block = raw["fantasy_content"]["team"][1]
players = team_block["roster"]["0"]["players"]

roster_output = []

# ---- HELPERS ----
def extract_value(block, key):
    for item in block:
        if isinstance(item, dict) and key in item:
            return item[key]
    return None

def extract_stats(stat_block):
    stats = {}
    for s in stat_block:
        stat = s.get("stat")
        if not stat:
            continue
        sid = stat.get("stat_id")
        val = stat.get("value")
        if sid is None:
            continue
        try:
            stats[str(sid)] = float(val)
        except (TypeError, ValueError):
            stats[str(sid)] = val
    return stats

# ---- PARSE PLAYERS ----
for _, pdata in players.items():
    if not isinstance(pdata, dict):
        continue
    if "player" not in pdata:
        continue

    player = pdata["player"]
    meta = player[0]
    selected_pos = player[1]["selected_position"][1]["position"]

    player_id = int(extract_value(meta, "player_id"))
    name_block = extract_value(meta, "name")
    name = name_block.get("full") if name_block else None
    team_abbr = extract_value(meta, "editorial_team_abbr")

    stats = {}

    for block in player:
        if isinstance(block, dict) and "player_stats" in block:
            stats = extract_stats(block["player_stats"]["stats"])

    roster_output.append({
        "player_id": player_id,
        "name": name,
        "selected_position": selected_pos,
        "editorial_team": team_abbr,
        "stats": stats
    })

# ---- WRITE OUTPUT ----
payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written with season stats")
