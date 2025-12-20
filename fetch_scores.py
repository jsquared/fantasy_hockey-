import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

LEAGUE_ID = "465.l.33140"

# ---------- OAuth ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    oauth_data = json.loads(os.environ["YAHOO_OAUTH_JSON"])
    with open("oauth2.json", "w") as f:
        json.dump(oauth_data, f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------- Yahoo objects ----------
game = yfa.Game(oauth, "nhl")
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()
current_week = league.current_week()

# ---------- Raw scoreboard ----------
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)

league_data = raw["fantasy_content"]["league"][1]
matchups = league_data["scoreboard"]["0"]["matchups"]

# ---------- Find my matchup ----------
my_team = None
opp_team = None
status = "UNKNOWN"

for k, v in matchups.items():
    if k == "count":
        continue

    matchup = v["matchup"]
    status = matchup.get("status", "UNKNOWN").upper()

    teams = matchup["0"]["teams"]

    extracted = []
    for tk, tv in teams.items():
        if tk == "count":
            continue

        team_block = tv["team"]
        meta = team_block[0]
        stats = team_block[1]

        tkey = meta[0]["team_key"]
        name = meta[2]["name"]
        score = float(stats["team_points"]["total"])

        extracted.append({
            "team_key": tkey,
            "name": name,
            "score": score
        })

    if any(t["team_key"] == team_key for t in extracted):
        my_team = next(t for t in extracted if t["team_key"] == team_key)
        opp_team = next(t for t in extracted if t["team_key"] != team_key)
        break

if not my_team or not opp_team:
    raise RuntimeError("Could not find matchup for your team")

# ---------- Output ----------
payload = {
    "league": league.settings()["name"],
    "week": current_week,
    "status": status,
    "myTeam": my_team,
    "opponent": opp_team,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/scores.json", "w") as f:
    json.dump(payload, f, indent=2)

print("scores.json updated")
