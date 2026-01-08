import json
import os
from datetime import datetime, timezone, date
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# ---- OAuth bootstrap (UNCHANGED) ----
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)
team_key = league.team_key()

# ---- HELPERS ----
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

# ---- DELTA ENGINE ----
def compute_delta(recent_avg, season_avg):
    delta = {}
    for stat_id, season_val in season_avg.items():
        recent_val = recent_avg.get(stat_id)
        if not isinstance(season_val, (int, float)):
            continue
        if not isinstance(recent_val, (int, float)):
            continue
        delta[stat_id] = round(recent_val - season_val, 3)
    return delta

# ---- FETCH WINDOW STATS (already working logic) ----
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
        stats = {}

        for block in player:
            if isinstance(block, dict) and "player_stats" in block:
                stats = extract_stats(block["player_stats"]["stats"])

        output[pid] = stats

    return output

# ---- STAT WINDOWS ----
today_str = date.today().isoformat()

stat_windows = {
    "season": "season",
    "season_avg": "seasonavg",
    "last_week": "lastweek",
    "last_week_avg": "lastweekavg",
    "last_month": "lastmonth",
    "last_month_avg": "lastmonthavg",
    "today": f"date;date={today_str}"
}

window_stats = {
    key: fetch_stats(val)
    for key, val in stat_windows.items()
}

# ---- DERIVE LAST TWO WEEKS (Yahoo-style) ----
last_two_weeks = {}
last_two_weeks_avg = {}

for pid, lw in window_stats["last_week"].items():
    combined = {}
    for stat_id, val in lw.items():
        if isinstance(val, (int, float)):
            combined[stat_id] = val * 2
    last_two_weeks[pid] = combined

for pid, lw_avg in window_stats["last_week_avg"].items():
    last_two_weeks_avg[pid] = lw_avg.copy()

window_stats["last_two_weeks"] = last_two_weeks
window_stats["last_two_weeks_avg"] = last_two_weeks_avg

# ---- BASE ROSTER ----
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

    stats_bundle = {
        window: window_stats.get(window, {}).get(pid, {})
        for window in window_stats
    }

    # ---- STEP 1: DELTAS ----
    deltas = {
        "last_week_vs_season": compute_delta(
            stats_bundle.get("last_week_avg", {}),
            stats_bundle.get("season_avg", {})
        ),
        "last_two_weeks_vs_season": compute_delta(
            stats_bundle.get("last_two_weeks_avg", {}),
            stats_bundle.get("season_avg", {})
        ),
        "last_month_vs_season": compute_delta(
            stats_bundle.get("last_month_avg", {}),
            stats_bundle.get("season_avg", {})
        )
    }

    roster_output.append({
        "player_id": pid,
        "name": name,
        "selected_position": selected_pos,
        "editorial_team": team_abbr,
        "stats": stats_bundle,
        "deltas": deltas
    })

# ---- WRITE OUTPUT ----
payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written with delta stats (Step 1)")
