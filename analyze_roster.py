import json
import os
from datetime import datetime, timezone, date
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# -------------------------------------------------
# OAuth bootstrap (UNCHANGED — WORKING)
# -------------------------------------------------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)
team_key = league.team_key()

# -------------------------------------------------
# Helpers
# -------------------------------------------------
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

def fetch_window(stat_type):
    raw = league.yhandler.get(
        f"team/{team_key}/roster/players/stats;type={stat_type}"
    )
    team_block = raw["fantasy_content"]["team"][1]
    players = team_block["roster"]["0"]["players"]

    out = {}
    games = {}

    for _, pdata in players.items():
        if not isinstance(pdata, dict) or "player" not in pdata:
            continue

        player = pdata["player"]
        meta = player[0]
        pid = int(extract_value(meta, "player_id"))

        stats = {}
        gp = None

        for block in player:
            if isinstance(block, dict) and "player_stats" in block:
                stats = extract_stats(block["player_stats"]["stats"])
            if isinstance(block, dict) and "games_played" in block:
                gp = block["games_played"]

        out[pid] = stats
        if gp:
            games[pid] = int(gp)

    return out, games

def per_game(stats, games):
    avg = {}
    if not games or games == 0:
        return avg
    for k, v in stats.items():
        if isinstance(v, (int, float)):
            avg[k] = round(v / games, 3)
    return avg

# -------------------------------------------------
# Fetch stat windows Yahoo actually supports
# -------------------------------------------------
today_str = date.today().isoformat()

windows = {
    "season": "season",
    "last_week": "lastweek",
    "last_month": "lastmonth",
    "today": f"date;date={today_str}"
}

window_stats = {}
window_games = {}

for name, wtype in windows.items():
    s, g = fetch_window(wtype)
    window_stats[name] = s
    window_games[name] = g

# -------------------------------------------------
# Derive last two weeks (Yahoo has no endpoint)
# -------------------------------------------------
last_two_weeks = {}
last_two_games = {}

for pid, lw in window_stats["last_week"].items():
    combined = {}
    for stat, val in lw.items():
        if isinstance(val, (int, float)):
            combined[stat] = val * 2
    last_two_weeks[pid] = combined

    gp = window_games["last_week"].get(pid, 0)
    last_two_games[pid] = gp * 2

window_stats["last_two_weeks"] = last_two_weeks
window_games["last_two_weeks"] = last_two_games

# -------------------------------------------------
# Build roster metadata (season call)
# -------------------------------------------------
raw = league.yhandler.get(
    f"team/{team_key}/roster/players/stats;type=season"
)

team_block = raw["fantasy_content"]["team"][1]
players = team_block["roster"]["0"]["players"]

roster_output = []

for _, pdata in players.items():
    if not isinstance(pdata, dict) or "player" not in pdata:
        continue

    player = pdata["player"]
    meta = player[0]
    selected_pos = player[1]["selected_position"][1]["position"]

    pid = int(extract_value(meta, "player_id"))
    name_block = extract_value(meta, "name")
    name = name_block.get("full") if name_block else None
    team_abbr = extract_value(meta, "editorial_team_abbr")

    stats_bundle = {}

    # ---- raw totals ----
    for w in window_stats:
        stats_bundle[w] = window_stats[w].get(pid, {})

    # ---- averages (TRUE Yahoo math) ----
    for w in ["season", "last_week", "last_two_weeks", "last_month"]:
        stats_bundle[f"{w}_avg"] = per_game(
            stats_bundle[w],
            window_games[w].get(pid, 0)
        )

    # ---- deltas vs season avg ----
    for w in ["last_week", "last_two_weeks", "last_month"]:
        delta = {}
        base = stats_bundle["season_avg"]
        cur = stats_bundle[f"{w}_avg"]
        for stat in base:
            if stat in cur:
                delta[stat] = round(cur[stat] - base[stat], 3)
        stats_bundle[f"{w}_delta"] = delta

    # ---- trend score (weighted momentum) ----
    trend = 0.0
    for w, weight in [
        ("last_week_delta", 0.5),
        ("last_two_weeks_delta", 0.3),
        ("last_month_delta", 0.2),
    ]:
        for v in stats_bundle[w].values():
            if isinstance(v, (int, float)):
                trend += v * weight

    trade_value = round(
        sum(stats_bundle["season_avg"].values()) + trend, 3
    )

    roster_output.append({
        "player_id": pid,
        "name": name,
        "selected_position": selected_pos,
        "editorial_team": team_abbr,
        "trend_z": round(trend, 3),
        "trade_value": trade_value,
        "stats": stats_bundle
    })

# -------------------------------------------------
# STEP 5 — ACTIONABLE INSIGHTS
# -------------------------------------------------
sell_high = []
buy_low = []

for p in roster_output:
    if p["trade_value"] > 0.3 and p["trend_z"] < -0.25:
        sell_high.append(p)
    if p["trade_value"] < 0.2 and p["trend_z"] > 0.4:
        buy_low.append(p)

sell_high = sorted(sell_high, key=lambda x: x["trend_z"])
buy_low = sorted(buy_low, key=lambda x: x["trend_z"], reverse=True)

# -------------------------------------------------
# Write output
# -------------------------------------------------
payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output,
    "sell_high": sell_high,
    "buy_low": buy_low
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written (full analytics)")
