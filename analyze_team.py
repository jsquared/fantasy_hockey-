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
WEEK = 1  # change to the week you want to dump

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

# =========================
# Get scoreboard raw for the week
# =========================
raw = league.yhandler.get_scoreboard_raw(
    league.league_id, WEEK
)

# =========================
# Extract teams and stats
# =========================
league_data = raw["fantasy_content"]["league"][1]
scoreboard = league_data["scoreboard"]["0"]
matchups = scoreboard["matchups"]

all_teams_stats = {}

for k, v in matchups.items():
    if k == "count":
        continue

    matchup = v["matchup"]
    teams = matchup["0"]["teams"]

    for tk, tv in teams.items():
        if tk == "count":
            continue

        team_block = tv["team"]
        meta = team_block[0]
        stats_block = team_block[1].get("team_stats", {})
        team_key = meta[0]["team_key"]

        all_teams_stats[team_key] = stats_block

# =========================
# Dump raw stats
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/league_week_{}.json".format(WEEK), "w") as f:
    json.dump({
        "week": WEEK,
        "league": LEAGUE_ID,
        "teams": all_teams_stats,
        "lastUpdated": datetime.now(timezone.utc).isoformat()
    }, f, indent=2)

print(f"docs/league_week_{WEEK}.json updated")
