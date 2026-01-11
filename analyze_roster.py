import json
import os
from datetime import datetime, timezone, date
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
import math

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# ---- OAuth bootstrap (UNCHANGED, VERIFIED) ----
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)
team_key = league.team_key()

# ------------------------------------------------
# HELPERS
# ------------------------------------------------
def extract_value(block, key):
    for item in block:
        if isinstance(item, dict) and key in item:
            return item[key]
    return None

def extract_stats(stat_block):
    stats = {}
    for s in stat_block:
        stat = s.get("stat")
        if not stat:
            continue
        sid = stat.get("stat_id")
        val = stat.get("value")
        if sid is None:
            continue
        try:
            stats[str(sid)] = float(val)
        except (TypeError, ValueError):
            stats[str(sid)] = val
    return stats

def fetch_stats(stat_type):
    raw = league.yhandler.get(
        f"team/{team_key}/roster/players/stats;type={stat_type}"
    )

    team_block = raw["fantasy_content"]["team"][1]
    players = team_block["roster"]["0"]["players"]

    output = {}

    for _, pdata in players.items():
        if not isinstance(pdata, dict) or "player" not in pdata:
            continue

        player = pdata["player"]
        meta = player[0]
        pid = int(extract_value(meta, "player_id"))

        for block in player:
            if isinstance(block, dict) and "player_stats" in block:
                output[pid] = extract_stats(block["player_stats"]["stats"])

    return output

def games_played_from_hits(stats):
    return max(1, int(stats.get("16", 1)))  # TOI proxy fallback

def calc_avg(stats, games):
    avg = {}
    for k, v in stats.items():
        if isinstance(v, (int, float)):
            avg[k] = round(v / games, 3)
    return avg

def calc_delta(avg, season_avg):
    delta = {}
    for k, v in avg.items():
        base = season_avg.get(k)
        if base is not None:
            delta[k] = round(v - base, 3)
    return delta

# ------------------------------------------------
# FETCH WINDOWS
# ------------------------------------------------
today_str = date.today().isoformat()

stat_windows = {
    "season": "season",
    "last_week": "lastweek",
    "last_month": "lastmonth",
    "today": f"date;date={today_str}"
}

window_stats = {k: fetch_stats(v) for k, v in stat_windows.items()}

# ---- DERIVE LAST TWO WEEKS (Yahoo limitation) ----
window_stats["last_two_weeks"] = {}
for pid, lw in window_stats["last_week"].items():
    window_stats["last_two_weeks"][pid] = {
        k: v * 2 if isinstance(v, (int, float)) else v
        for k, v in lw.items()
    }

# ------------------------------------------------
# BASE ROSTER + METADATA
# ------------------------------------------------
raw = league.yhandler.get(
    f"team/{team_key}/roster/players/stats;type=season"
)

team_block = raw["fantasy_content"]["team"][1]
players = team_block["roster"]["0"]["players"]

roster_output = []

# ------------------------------------------------
# BUILD PLAYER OBJECTS
# ------------------------------------------------
for _, pdata in players.items():
    if not isinstance(pdata, dict) or "player" not in pdata:
        continue

    player = pdata["player"]
    meta = player[0]
    selected_pos = player[1]["selected_position"][1]["position"]

    pid = int(extract_value(meta, "player_id"))
    name = extract_value(meta, "name").get("full")
    team_abbr = extract_value(meta, "editorial_team_abbr")

    season = window_stats["season"].get(pid, {})
    season_games = games_played_from_hits(season)
    season_avg = calc_avg(season, season_games)

    stats_bundle = {"season": season, "season_avg": season_avg}

    for window in ["last_week", "last_two_weeks", "last_month"]:
        wstats = window_stats.get(window, {}).get(pid, {})
        games = max(1, len(wstats))
        avg = calc_avg(wstats, games)
        delta = calc_delta(avg, season_avg)

        stats_bundle[window] = wstats
        stats_bundle[f"{window}_avg"] = avg
        stats_bundle[f"{window}_delta"] = delta

    stats_bundle["today"] = window_stats["today"].get(pid, {})

    roster_output.append({
        "player_id": pid,
        "name": name,
        "selected_position": selected_pos,
        "editorial_team": team_abbr,
        "stats": stats_bundle
    })

# ------------------------------------------------
# STEP 3 — TREND NORMALIZATION
# ------------------------------------------------
def trend_score(p):
    d = p["stats"].get("last_two_weeks_delta", {})
    return sum(v for v in d.values() if isinstance(v, (int, float)))

scores = [trend_score(p) for p in roster_output]
mean = sum(scores) / len(scores)
std = math.sqrt(sum((s - mean) ** 2 for s in scores) / len(scores)) or 1

for p in roster_output:
    z = (trend_score(p) - mean) / std
    p["trend_z"] = round(z, 3)

# ------------------------------------------------
# STEP 4 — TRADE VALUE ENGINE
# ------------------------------------------------
POSITION_SCARCITY = {
    "C": 0.9,
    "LW": 1.1,
    "RW": 1.1,
    "D": 1.25,
    "G": 1.4
}

ROLE_MULTIPLIER = {
    "C": 1.0,
    "LW": 1.0,
    "RW": 1.0,
    "D": 1.0,
    "Util": 0.95,
    "BN": 0.85,
    "IR": 0.5,
    "IR+": 0.6
}

for p in roster_output:
    pos = p["selected_position"]
    p["trade_value"] = round(
        p["trend_z"]
        * POSITION_SCARCITY.get(pos, 1.0)
        * ROLE_MULTIPLIER.get(pos, 1.0),
        3
    )

# ---- 1-for-1 TRADE MATRIX ----
trades = []

for a in roster_output:
    for b in roster_output:
        if a["player_id"] == b["player_id"]:
            continue

        delta = round(a["trade_value"] - b["trade_value"], 3)

        verdict = (
            "WIN" if delta > 0.35 else
            "LOSS" if delta < -0.35 else
            "FAIR"
        )

        trades.append({
            "give": a["name"],
            "get": b["name"],
            "delta": delta,
            "verdict": verdict
        })

# ------------------------------------------------
# WRITE OUTPUT
# ------------------------------------------------
payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output,
    "trade_analysis": trades
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written with full analysis")
