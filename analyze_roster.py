import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


# ---------- CONFIG ----------
GAME_KEY = "nhl"
OUTPUT_PATH = "docs/roster.json"
# ----------------------------


# OAuth (uses oauth.json)
oauth = OAuth2(None, None, from_file="oauth.json")
gm = yfa.Game(oauth, GAME_KEY)

# Get current league
league_ids = gm.league_ids()
if not league_ids:
    raise RuntimeError("No leagues found for this game.")

league = gm.league(league_ids[0])

# Get your team
teams = league.teams()
my_team_key = list(teams.keys())[0]
team = league.team(my_team_key)

# Get roster (THIS PART WAS WORKING)
roster = team.roster()

# Build player keys (CRITICAL)
player_keys = []
player_map = {}

for p in roster:
    pid = p["player_id"]
    pkey = f"{league.league_key}.p.{pid}"
    player_keys.append(pkey)

    player_map[pkey] = {
        "player_id": pid,
        "name": p["name"],
        "position": p.get("position"),
        "selected_position": p.get("selected_position"),
        "editorial_team": p.get("editorial_team_abbr"),
        "stats": {}
    }

# ---- Yahoo Players API call (THIS IS THE FIX) ----
# This is the ONLY reliable way to get NHL season stats
raw = league.yhandler.get(
    f"/league/{league.league_key}/players;player_keys={','.join(player_keys)}/stats"
)

players = (
    raw["fantasy_content"]["league"][1]["players"]
)

# Normalize Yahoo response
for item in players:
    player = item["player"]
    pkey = player["player_key"]

    if "player_stats" not in player:
        continue

    stats_block = player["player_stats"]["stats"]

    if isinstance(stats_block, list):
        for stat in stats_block:
            stat_id = stat.get("stat_id")
            value = stat.get("value")
            if stat_id is not None:
                player_map[pkey]["stats"][str(stat_id)] = value

# Final output
output = {
    "league": league.settings()["name"],
    "team_key": my_team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": list(player_map.values())
}

os.makedirs("docs", exist_ok=True)
with open(OUTPUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print(f"Wrote roster with season stats → {OUTPUT_PATH}")
