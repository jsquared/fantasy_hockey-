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
# Helpers
# =========================
def extract_stats(stats_block):
    stats = {}
    for item in stats_block:
        stat_id = str(item["stat"]["stat_id"])
        val = item["stat"]["value"]
        try:
            stats[stat_id] = float(val)
        except (TypeError, ValueError):
            stats[stat_id] = val
    return stats

# =========================
# ROSTER + PLAYER STATS
# =========================
roster_output = []

roster = team.roster()  # ✅ THIS PART WAS ALWAYS WORKING

for p in roster:
    player_id = p["player_id"]
    name = p["name"]
    position = p.get("position")

    player_key = f"{GAME_CODE}.p.{player_id}"

    # ✅ STRING PARAMS (THIS IS THE FIX)
    raw = league.yhandler.get_players_raw(
        league.league_id,
        player_key,
        "stats"
    )

    stats = {}

    try:
        stats_block = (
            raw["fantasy_content"]["league"][1]
            ["players"]["0"]["player"][1]
            ["player_stats"]["stats"]
        )
        stats = extract_stats(stats_block)
    except Exception:
        stats = {}

    roster_output.append({
        "player_id": player_id,
        "player_key": player_key,
        "name": name,
        "position": position,
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
