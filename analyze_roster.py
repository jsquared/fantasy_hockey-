import json
import os
from datetime import datetime, timezone, date
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------------- CONFIG ----------------
GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# ---------------- OAUTH ----------------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)
team_key = league.team_key()

# ---------------- HELPERS ----------------
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
        sid = str(stat.get("stat_id"))
        val = stat.get("value")
        try:
            stats[sid] = float(val)
        except (TypeError, ValueError):
            stats[sid] = val
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

# ---------------- AVG / DELTA ----------------
def compute_avg(stats):
    gp = stats.get("31") or stats.get("32")
    if not gp or gp == 0:
        return {}

    avg = {}
    for sid, val in stats.items():
        if sid in ("31", "32"):
            continue
        try:
            avg[sid] = round(val / gp, 3)
        except Exception:
            pass
    return avg

def compute_delta(recent_avg, season_avg):
    delta = {}
    for sid, val in recent_avg.items():
        if sid in season_avg:
            delta[sid] = round(val - season_avg[sid], 3)
    return delta

# ---------------- FETCH WINDOWS ----------------
today_str = date.today().isoformat()

stat_windows = {
    "season": "season",
    "last_week": "lastweek",
    "last_month": "lastmonth",
    "today": f"date;date={today_str}"
}

window_stats = {k: fetch_stats(v) for k, v in stat_windows.items()}

# ---------------- DERIVE LAST TWO WEEKS (WITH GP) ----------------
last_two_weeks = {}

for pid, lw in window_stats["last_week"].items():
    combined = {}

    for sid, val in lw.items():
        try:
            combined[sid] = val * 2
        except Exception:
            pass

    # CRITICAL: carry games played forward
    if "31" in lw:
        combined["31"] = lw["31"] * 2
    if "32" in lw:
        combined["32"] = lw["32"] * 2

    last_two_weeks[pid] = combined

window_stats["last_two_weeks"] = last_two_weeks

# ---------------- BASE ROSTER ----------------
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

    pid = int(extract_value(meta, "player_id"))
    name_block = extract_value(meta, "name")
    name = name_block.get("full") if name_block else None
    team_abbr = extract_value(meta, "editorial_team_abbr")
    selected_pos = player[1]["selected_position"][1]["position"]

    season = window_stats["season"].get(pid, {})
    season_avg = compute_avg(season)

    last_week = window_stats["last_week"].get(pid, {})
    last_week_avg = compute_avg(last_week)

    last_two = window_stats["last_two_weeks"].get(pid, {})
    last_two_avg = compute_avg(last_two)

    last_month = window_stats["last_month"].get(pid, {})
    last_month_avg = compute_avg(last_month)

    stats_bundle = {
        "season": season,
        "season_avg": season_avg,

        "last_week": last_week,
        "last_week_avg": last_week_avg,
        "last_week_delta": compute_delta(last_week_avg, season_avg),

        "last_two_weeks": last_two,
        "last_two_weeks_avg": last_two_avg,
        "last_two_weeks_delta": compute_delta(last_two_avg, season_avg),

        "last_month": last_month,
        "last_month_avg": last_month_avg,
        "last_month_delta": compute_delta(last_month_avg, season_avg),

        "today": window_stats["today"].get(pid, {})
    }

    roster_output.append({
        "player_id": pid,
        "name": name,
        "selected_position": selected_pos,
        "editorial_team": team_abbr,
        "stats": stats_bundle
    })

# ---------------- WRITE OUTPUT ----------------
payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written with correct averages + deltas")
