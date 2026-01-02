import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict
import itertools

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
WEEKS = 12

# =========================
# STAT MAP
# =========================
STAT_MAP = {
    "1": "Goals",
    "2": "Assists",
    "4": "+/-",
    "5": "PIM",
    "8": "PPP",
    "11": "SHP",
    "12": "GWG",
    "14": "SOG",
    "16": "FW",
    "31": "Hits",
    "32": "Blocks",
    "19": "Wins",
    "22": "GA",
    "23": "GAA",
    "24": "Shots Against",
    "25": "Saves",
    "26": "SV%",
    "27": "Shutouts"
}

LOWER_IS_BETTER = {"GA", "GAA", "Shots Against"}
GOALIE_STATS = {"Wins", "GA", "GAA", "Saves", "Shots Against", "SV%", "Shutouts"}

# =========================
# OAuth
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
teams_meta = league.teams()

# =========================
# Helpers
# =========================
def normalize(val, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (val - min_v) / (max_v - min_v)

def invert(val):
    return -val

# =========================
# DATA COLLECTION
# =========================
weekly_stats = defaultdict(dict)

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for _, matchup in matchups.items():
        if _ == "count":
            continue

        teams_block = matchup["matchup"]["0"]["teams"]
        for _, team_entry in teams_block.items():
            if _ == "count":
                continue

            team_block = team_entry["team"]
            team_key = team_block[0][0]["team_key"]

            stats = {}
            for item in team_block[1]["team_stats"]["stats"]:
                stat_id = str(item["stat"]["stat_id"])
                if stat_id not in STAT_MAP:
                    continue
                try:
                    stats[STAT_MAP[stat_id]] = float(item["stat"]["value"])
                except:
                    pass

            weekly_stats[week][team_key] = stats

# =========================
# AVERAGES
# =========================
avg_stats = defaultdict(dict)

for team in teams_meta.keys():
    for stat in STAT_MAP.values():
        vals = [
            weekly_stats[w][team][stat]
            for w in weekly_stats
            if stat in weekly_stats[w].get(team, {})
        ]
        avg_stats[team][stat] = sum(vals) / len(vals) if vals else None

# =========================
# NORMALIZED CATEGORY SCORES
# =========================
team_scores = defaultdict(dict)

for stat in STAT_MAP.values():
    vals = {
        t: avg_stats[t][stat]
        for t in avg_stats
        if avg_stats[t][stat] is not None
    }

    if not vals:
        continue

    min_v, max_v = min(vals.values()), max(vals.values())

    for team, v in vals.items():
        score = normalize(v, min_v, max_v)
        if stat in LOWER_IS_BETTER:
            score = 1 - score

        # goalie stats weighted slightly higher
        weight = 1.15 if stat in GOALIE_STATS else 1.0
        team_scores[team][stat] = score * weight

# =========================
# SURPLUS / WEAKNESS
# =========================
my_scores = team_scores[my_team_key]

sorted_stats = sorted(my_scores.items(), key=lambda x: x[1], reverse=True)
strengths = {s for s, _ in sorted_stats[:4]}
weaknesses = {s for s, _ in sorted_stats[-4:]}

# =========================
# TRADE ENGINE
# =========================
trade_suggestions = []

for other_team in teams_meta.keys():
    if other_team == my_team_key:
        continue

    other_scores = team_scores[other_team]

    # 1-for-1 logic
    for give, get in itertools.product(strengths, weaknesses):
        delta_me = other_scores.get(get, 0) - my_scores.get(give, 0)
        delta_them = my_scores.get(get, 0) - other_scores.get(give, 0)

        if delta_me > 0 and delta_them > 0:
            trade_suggestions.append({
                "partner": teams_meta[other_team]["name"],
                "type": "1-for-1",
                "i_give": give,
                "i_get": get,
                "net_gain": round(delta_me, 3)
            })

    # 2-for-1 logic
    for give_pair in itertools.combinations(strengths, 2):
        for get in weaknesses:
            give_val = sum(my_scores.get(s, 0) for s in give_pair)
            get_val = other_scores.get(get, 0)

            if get_val > give_val * 0.9:
                trade_suggestions.append({
                    "partner": teams_meta[other_team]["name"],
                    "type": "2-for-1",
                    "i_give": list(give_pair),
                    "i_get": get,
                    "net_gain": round(get_val - give_val, 3)
                })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "strengths": sorted(strengths),
    "weaknesses": sorted(weaknesses),
    "trade_recommendations": sorted(
        trade_suggestions,
        key=lambda x: x["net_gain"],
        reverse=True
    ),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with trade recommendations")
