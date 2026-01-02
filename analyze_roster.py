import json
import os
from datetime import datetime, timezone
from collections import defaultdict
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
MIN_NET_GAIN = 0.05

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
    "31": "Hits",
    "32": "Blocks",
    "19": "Wins",
    "23": "GAA",
    "26": "SV%",
    "27": "Shutouts"
}

LOWER_IS_BETTER = {"GAA"}

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

# =========================
# TEAM NAMES (FIXED)
# =========================
teams = {}
for team_key in league.teams():
    team = yfa.Team(oauth, team_key)
    teams[team_key] = team.name()   # ✅ METHOD, NOT ATTRIBUTE

# =========================
# PLAYER DATA
# =========================
players_by_team = defaultdict(dict)

for team_key in teams:
    team = yfa.Team(oauth, team_key)
    roster = team.roster()

    for player in roster:
        pid = player["player_id"]
        name = player["name"]["full"]

        p = yfa.Player(oauth, pid)
        stats_raw = p.stats()

        stats = {}
        for s in stats_raw:
            sid = str(s["stat_id"])
            if sid in STAT_MAP:
                try:
                    stats[STAT_MAP[sid]] = float(s["value"])
                except (TypeError, ValueError):
                    stats[STAT_MAP[sid]] = 0.0

        players_by_team[team_key][pid] = {
            "name": name,
            "stats": stats
        }

# =========================
# TEAM STRENGTHS / WEAKNESSES
# =========================
team_totals = defaultdict(lambda: defaultdict(float))

for team_key, players in players_by_team.items():
    for p in players.values():
        for stat, val in p["stats"].items():
            team_totals[team_key][stat] += val

def rank_stat(stat):
    vals = {t: team_totals[t].get(stat, 0) for t in teams}
    reverse = stat not in LOWER_IS_BETTER
    ranked = sorted(vals.items(), key=lambda x: x[1], reverse=reverse)
    return {t: i + 1 for i, (t, _) in enumerate(ranked)}

ranks = {stat: rank_stat(stat) for stat in STAT_MAP.values()}

my_strengths = [s for s in STAT_MAP.values() if ranks[s][my_team_key] <= 4]
my_weaknesses = [s for s in STAT_MAP.values() if ranks[s][my_team_key] >= len(teams) - 3]

# =========================
# TRADE ENGINE
# =========================
def player_value(player):
    score = 0
    for stat, val in player["stats"].items():
        r = ranks[stat][team_key]
        score += val / r
    return score

trade_recs = []

for opp_key in teams:
    if opp_key == my_team_key:
        continue

    for my_pid, my_p in players_by_team[my_team_key].items():
        my_val = sum(
            my_p["stats"].get(w, 0) for w in my_strengths
        )

        for opp_pid, opp_p in players_by_team[opp_key].items():
            opp_val = sum(
                opp_p["stats"].get(w, 0) for w in my_weaknesses
            )

            net = opp_val - my_val
            if net >= MIN_NET_GAIN:
                trade_recs.append({
                    "partner": teams[opp_key],
                    "type": "1-for-1",
                    "i_give": my_p["name"],
                    "i_get": opp_p["name"],
                    "net_gain": round(net, 3)
                })

        # 2-for-1
        for my_pid2, my_p2 in players_by_team[my_team_key].items():
            if my_pid2 <= my_pid:
                continue

            my_val2 = my_val + sum(
                my_p2["stats"].get(w, 0) for w in my_strengths
            )

            for opp_pid, opp_p in players_by_team[opp_key].items():
                opp_val = sum(
                    opp_p["stats"].get(w, 0) for w in my_weaknesses
                )

                net = opp_val - my_val2
                if net >= MIN_NET_GAIN:
                    trade_recs.append({
                        "partner": teams[opp_key],
                        "type": "2-for-1",
                        "i_give": [my_p["name"], my_p2["name"]],
                        "i_get": opp_p["name"],
                        "net_gain": round(net, 3)
                    })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "strengths": my_strengths,
    "weaknesses": my_weaknesses,
    "trade_recommendations": sorted(
        trade_recs, key=lambda x: x["net_gain"], reverse=True
    ),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json written with PLAYER-LEVEL trade recommendations")
