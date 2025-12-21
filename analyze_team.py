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
my_team_data = None
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

        # Extract stats safely
        stats_dict = {}
        if len(team_block) > 1 and "team_stats" in team_block[1]:
            stats_list = team_block[1]["team_stats"]["stats"]
            for s in stats_list:
                stat = s.get("stat")
                if stat and "value" in stat:
                    try:
                        stats_dict[stat["stat_id"]] = {
                            "name": stat.get("name", stat["stat_id"]),
                            "value": float(stat["value"])
                        }
                    except ValueError:
                        stats_dict[stat["stat_id"]] = {"name": stat.get("name", stat["stat_id"]), "value": 0.0}

        tkey = meta[0]["team_key"]
        if tkey == team_key:
            my_team_data = {
                "team_key": tkey,
                "name": meta[2]["name"],
                "stats": stats_dict
            }
            break
    if my_team_data:
        break

if not my_team_data:
    raise RuntimeError("Could not find your team in this week's matchup")

# ---------- Identify strengths and weaknesses ----------
strengths = sorted(
    [v for k, v in my_team_data["stats"].items() if v["value"] > 0],
    key=lambda x: x["value"],
    reverse=True
)

weaknesses = sorted(
    [v for k, v in my_team_data["stats"].items() if v["value"] <= 0],
    key=lambda x: x["value"]
)

# ---------- Output ----------
payload = {
    "league": league.settings()["name"],
    "team_key": my_team_data["team_key"],
    "week": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("team_analysis.json updated")
