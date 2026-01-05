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
# OAuth bootstrap (CI-safe)
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

team_key = league.team_key()
team = league.to_team(team_key)

# =========================
# Helpers
# =========================
def extract_player_stats(player_block):
    stats = {}

    player_stats = (
        player_block
        .get("player", {})
        .get("player_stats", {})
        .get("stats", [])
    )

    for entry in player_stats:
        stat = entry.get("stat", {})
        sid = stat.get("stat_id")
        val = stat.get("value")

        if sid is None:
            continue

        try:
            stats[str(sid)] = float(val)
        except (TypeError, ValueError):
            stats[str(sid)] = val

    return stats

# =========================
# ROSTER + STATS
# =========================
roster_output = []

for p in team.roster():
    pid = p["player_id"]
    player_key = f"{GAME_CODE}.p.{pid}"

    try:
        raw = league.yhandler.get(
            f"league/{LEAGUE_ID}/players;player_keys={player_key}/stats"
        )

        player_block = (
            raw["fantasy_content"]["league"][1]
               ["players"]["0"]
        )

        stats = extract_player_stats(player_block)

    except Exception as e:
        stats = {}

    roster_output.append({
        "player_id": pid,
        "name": p.get("name"),
        "position": p.get("position"),
        "selected_position": p.get("selected_position"),
        "editorial_team": p.get("editorial_team_abbr"),
        "stats": stats
    })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written successfully with season-to-date stats")
