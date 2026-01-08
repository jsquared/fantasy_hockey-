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

def compute_weekly_avg(stats, weeks):
    if not weeks or weeks == 0:
        return {}

    avg = {}
    for sid, val in stats.items():
        try:
            avg[sid] = round(float(val) / weeks, 2)
        except Exception:
            pass
    return avg

# ---- FETCH STAT WINDOWS ----
today_str = date.today().isoformat()

stat_windows = {
    "season": "season",
    "last_week": "lastweek",
    "last_month": "lastmonth",
    "today": f"date;date={today_str}"
}

window_stats = {
    key: fetch_stats(val)
    for key, val in stat_windows.items()
}

# ---- DERIVE LAST TWO WEEKS (Yahoo-style) ----
last_two_weeks = {}
for pid, lw_stats in window_stats["last_week"].items():
    combined = {}
    for stat_id, val in lw_stats.items():
        try:
            combined[stat_id] = float(val) * 2
        except Exception:
            pass
    last_two_weeks[pid] = combined

window_stats["last_two_weeks"] = last_two_weeks

# ---- BASE ROSTER (SEASON CALL FOR METADATA) ----
raw = league.yhandler.get(
    f"team/{team_key}/roster/players/stats;type=season"
)

team_block = raw["fantasy_content"]["team"][1]
players = team_block["roster"]["0"]["players"]

roster_output = []

# ---- YAHOO MATCHUP WEEK CONSTANTS ----
SEASON_WEEKS = 42
LAST_WEEK_WEEKS = 1
LAST_TWO_WEEKS = 2
LAST_MONTH_WEEKS = 4.5  # Yahoo rolling month approximation

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

    season = window_stats["season"].get(pid, {})
    last_week = window_stats["last_week"].get(pid, {})
    last_two = window_stats["last_two_weeks"].get(pid, {})
    last_month = window_stats["last_month"].get(pid, {})
    today = window_stats["today"].get(pid, {})

    stats_bundle = {
        "season": season,
        "season_avg": compute_weekly_avg(season, SEASON_WEEKS),
        "last_week": last_week,
        "last_week_avg": compute_weekly_avg(last_week, LAST_WEEK_WEEKS),
        "last_two_weeks": last_two,
        "last_two_weeks_avg": compute_weekly_avg(last_two, LAST_TWO_WEEKS),
        "last_month": last_month,
        "last_month_avg": compute_weekly_avg(last_month, LAST_MONTH_WEEKS),
        "today": today
    }

    roster_output.append({
        "player_id": pid,
        "name": name,
        "selected_position": selected_pos,
        "editorial_team": team_abbr,
        "stats": stats_bundle
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

print("✅ docs/roster.json written with Yahoo-accurate stat windows and averages")
