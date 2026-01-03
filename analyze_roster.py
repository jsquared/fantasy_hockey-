import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

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
team = league.to_team(my_team_key)

# =========================
# ROSTER + PLAYER STATS
# =========================
roster_output = []

roster = team.roster()  # ✅ NO arguments supported in your version

for p in roster:
    pid = p["player_id"]

    # pull season stats separately (THIS IS THE KEY)
    raw_stats = team.player_stats(pid, "season")

    stats = {}
    for item in raw_stats:
        stat_id = str(item["stat_id"])
        val = item["value"]
        try:
            stats[stat_id] = float(val)
        except (TypeError, ValueError):
            stats[stat_id] = val

    roster_output.append({
        "player_id": pid,
        "name": p["name"],
        "position": p.get("position"),
        "selected_position": p.get("selected_position"),
        "editorial_team": p.get("editorial_team_abbr"),
        "stats": stats
    })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "team_key": my_team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written successfully")
