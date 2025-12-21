import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------- League Setup ----------
LEAGUE_ID = "465.l.33140"

# OAuth: use environment variable if available
if "YAHOO_OAUTH_JSON" in os.environ:
    oauth_data = json.loads(os.environ["YAHOO_OAUTH_JSON"])
    with open("oauth2.json", "w") as f:
        json.dump(oauth_data, f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, "nhl")
league = game.to_league(LEAGUE_ID)
team_key = league.team_key()
current_week = league.current_week()

# ---------- Stat name mapping ----------
STAT_NAMES = {
    "1": "Goals",
    "2": "Assists",
    "4": "Plus/Minus",
    "5": "Penalty Minutes",
    "8": "Shots on Goal",
    "11": "Power Play Points",
    "12": "Short-Handed Points",
    "14": "Hits",
    "16": "Blocks",
    "19": "Wins",
    "22": "Goals Against",
    "23": "Goals Against Avg",
    "24": "Saves",
    "25": "Shots Against",
    "26": "Save %",
    "27": "Shutouts",
    "31": "Faceoffs Won",
    "32": "Faceoffs Lost"
}

# ---------- Raw scoreboard ----------
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
league_data = raw["fantasy_content"]["league"][1]
matchups = league_data["scoreboard"]["0"]["matchups"]

my_team = None
opp_team = None

for k, v in matchups.items():
    if k == "count":
        continue
    matchup = v["matchup"]
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

        # Convert raw stats to human-readable
        stat_values = {}
        for s in stats["team_stats"]["stats"]:
            stat_id = s["stat"]["stat_id"]
            value = s["stat"]["value"]
            stat_values[STAT_NAMES.get(stat_id, f"Stat {stat_id}")] = value

        extracted.append({
            "team_key": tkey,
            "name": name,
            "score": score,
            "stats": stat_values
        })

    if any(t["team_key"] == team_key for t in extracted):
        my_team = next(t for t in extracted if t["team_key"] == team_key)
        opp_team = next(t for t in extracted if t["team_key"] != team_key)
        break

if not my_team or not opp_team:
    raise RuntimeError("Could not find matchup for your team")

# ---------- Identify strengths and weaknesses ----------
strengths = sorted(
    [{"stat_id": k, "name": k, "value": v} for k, v in my_team["stats"].items() if v > 0],
    key=lambda x: x["value"],
    reverse=True
)
weaknesses = sorted(
    [{"stat_id": k, "name": k, "value": v} for k, v in my_team["stats"].items() if v <= 0],
    key=lambda x: x["value"]
)

# ---------- Output ----------
payload = {
    "league": league.settings()["name"],
    "team_key": team_key,
    "week": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/analyze_team.json", "w") as f:
    json.dump(payload, f, indent=2)

print("analyze_team.json updated")
