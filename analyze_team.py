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

# ---------- Fetch matchup scoreboard ----------
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

my_team_stats = None

for k, v in matchups.items():
    if k == "count":
        continue
    teams = v["matchup"]["0"]["teams"]
    for tk, tv in teams.items():
        if tk == "count":
            continue
        team_block = tv["team"]
        meta = team_block[0]
        stats = team_block[1]
        tkey = meta[0]["team_key"]
        if tkey == team_key:
            # Use the stats array safely
            my_team_stats = {}
            for s in stats.get("team_stats", {}).get("stats", []):
                stat_id = s["stat"].get("stat_id")
                value = float(s["stat"].get("value", 0))
                if stat_id:
                    my_team_stats[stat_id] = value
            break
    if my_team_stats:
        break

if not my_team_stats:
    raise RuntimeError("Could not find your team stats")

# ---------- Stat ID -> Human Name Map ----------
STAT_MAP = {
    "1": "Goals",
    "2": "Assists",
    "4": "Penalty Minutes",
    "5": "Power Play Points",
    "8": "Shots on Goal",
    "11": "Hits",
    "12": "Blocks",
    "14": "Faceoff Wins",
    "16": "Plus/Minus",
    "19": "Short-Handed Points",
    "22": "Giveaways",
    "23": "Takeaways",
    "24": "Wins",
    "25": "Saves",
    "26": "Save %",
    "27": "Goals Against",
    "31": "Goals For",
    "32": "Shots For"
}

# ---------- Separate strengths and weaknesses ----------
strengths = [
    {"stat_id": k, "name": STAT_MAP.get(k, k), "value": v}
    for k, v in my_team_stats.items() if v > 0
]

weaknesses = [
    {"stat_id": k, "name": STAT_MAP.get(k, k), "value": v}
    for k, v in my_team_stats.items() if v <= 0
]

# ---------- Output ----------
payload = {
    "league": league.settings()["name"],
    "team_key": team_key,
    "week": current_week,
    "strengths": sorted(strengths, key=lambda x: x["value"], reverse=True),
    "weaknesses": sorted(weaknesses, key=lambda x: x["value"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/analyzed_team.json", "w") as f:
    json.dump(payload, f, indent=2)

print("analyzed_team.json updated")
