import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
OUTPUT_FILE = "docs/roster.json"

# =========================
# OAuth (GitHub-safe)
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo Objects
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

my_team_key = league.team_key()
current_week = league.current_week()

team = league.to_team(my_team_key)

# =========================
# ROSTER
# =========================
roster = team.roster()  # current roster
player_ids = []
player_meta = {}

for p in roster:
    pid = int(p["player_id"])
    player_ids.append(pid)
    player_meta[pid] = {
        "player_id": pid,
        "name": p.get("name"),
        "team_key": my_team_key,
        "positions": p.get("eligible_positions", []),
        "status": p.get("status", ""),
        "editorial_team": p.get("editorial_team_abbr", "")
    }

# =========================
# PLAYER STATS (SEASON)
# =========================
stats_raw = league.player_stats(player_ids, req_type="season")

players = []

for stat in stats_raw:
    pid = int(stat["player_id"])

    # Normalize numeric values only
    clean_stats = {}
    for k, v in stat.items():
        if k in ("player_id", "name", "position_type"):
            clean_stats[k] = v
        else:
            try:
                clean_stats[k] = float(v)
            except (TypeError, ValueError):
                continue

    players.append({
        **player_meta.get(pid, {}),
        "season_stats": clean_stats
    })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name"),
    "current_week": current_week,
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
    "players": players
}

os.makedirs("docs", exist_ok=True)

with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"{OUTPUT_FILE} written successfully ({len(players)} players)")
