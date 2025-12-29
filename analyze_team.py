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
WEEK = 1  # change this to whichever week you want
TOP_N = 8
BOTTOM_N = 5

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

team_key = league.team_key()  # your team key

# =========================
# Fetch scoreboard raw for the week
# =========================
raw = league.yhandler.get_scoreboard_raw(LEAGUE_ID, WEEK)
league_data = raw["fantasy_content"]["league"][1]
scoreboard = league_data["scoreboard"]["0"]
matchups = scoreboard["matchups"]

# =========================
# Find my team stats
# =========================
my_stats = None
my_points = None
my_remaining = None

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

        if meta[0]["team_key"] != team_key:
            continue

        my_stats = team_block[1]["team_stats"]["stats"]
        my_points = team_block[1]["team_points"]["total"]
        my_remaining = team_block[1]["team_remaining_games"]["total"]
        break

    if my_stats:
        break

if not my_stats:
    raise RuntimeError("❌ Could not find your team stats")

# =========================
# Map stat IDs to names
# =========================
STAT_MAP = {
    "1": "Goals", "2": "Assists", "4": "+/-", "5": "PIM", "8": "PPP",
    "11": "SHP", "12": "GWG", "14": "SOG", "16": "FW", "19": "Wins",
    "22": "GA", "23": "GAA", "24": "Shots Against", "25": "Saves",
    "26": "SV%", "27": "Shutouts", "31": "Hit", "32": "Blk"
}

total_stats = []
for item in my_stats:
    stat = item.get("stat")
    if stat is None:
        continue

    stat_id = str(stat.get("stat_id"))
    value_raw = stat.get("value")

    try:
        value = float(value_raw)
    except (TypeError, ValueError):
        value = value_raw  # keep as string if not a number

    total_stats.append({
        "stat_id": stat_id,
        "name": STAT_MAP.get(stat_id, f"Stat {stat_id}"),
        "value": value
    })

# Sort strengths/weaknesses
total_stats_sorted = sorted(total_stats, key=lambda x: float(x["value"]) if isinstance(x["value"], (int, float, str)) and str(x["value"]).replace('.', '', 1).isdigit() else 0, reverse=True)
strengths = total_stats_sorted[:TOP_N]
weaknesses = list(reversed(total_stats_sorted[-BOTTOM_N:]))

# =========================
# Save output
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "team_key": team_key,
    "week": WEEK,
    "team_points": my_points,
    "total_stats": total_stats,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "remaining_games": my_remaining,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/team_analysis.json updated")
