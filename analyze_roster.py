import json
import os
from datetime import datetime, timezone, date
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# ---------------- OAuth (UNCHANGED) ----------------
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

# ---------------- STEP 1: PER-GAME AVERAGES ----------------
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

# ---------------- STEP 3: DELTAS ----------------
def compute_delta(recent_avg, season_avg):
    delta = {}
    for sid, val in recent_avg.items():
        if sid in season_avg:
            delta[sid] = round(val - season_avg[sid], 3)
    return delta

# ---------------- STEP 4: TREND CLASSIFICATION ----------------
def classify_trend(delta):
    trend = {}
    for sid, val in delta.items():
        if val > 0.05:
            trend[sid] = "hot"
        elif val < -0.05:
            trend[sid] = "cold"
        else:
            trend[sid] = "neutral"
    return trend

# ---------------- STEP 5: MOMENTUM SCORE ----------------
CATEGORY_WEIGHTS = {
    "1": 1.5,   # Goals
    "2": 1.2,   # Assists
    "5": 0.8,   # PPP
    "14": 0.5,  # Shots
    "16": 0.3,  # Hits
}

def momentum_score(delta):
    score = 0.0
    for sid, val in delta.items():
        weight = CATEGORY_WEIGHTS.get(sid, 0.2)
        score += val * weight
    return round(score, 3)

# ---------------- FETCH WINDOWS ----------------
today_str = date.today().isoformat()

stat_windows = {
    "season": "season",
    "last_week": "lastweek",
    "last_month": "lastmonth",
    "today": f"date;date={today_str}"
}

window_stats = {k: fetch_stats(v) for k, v in stat_windows.items()}

# ---------------- STEP 2: LAST TWO WEEKS (DERIVED) ----------------
last_two_weeks = {}
for pid, lw in window_stats["last_week"].items():
    combined = {}
    for sid, val in lw.items():
        try:
            combined[sid] = val * 2
        except Exception:
            pass
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
    selected_pos = player[1]["selected_position"][1]["position"]

    pid = int(extract_value(meta, "player_id"))
    name_block = extract_value(meta, "name")
    name = name_block.get("full") if name_block else None
    team_abbr = extract_value(meta, "editorial_team_abbr")

    season = window_stats["season"].get(pid, {})
    season_avg = compute_avg(season)

    last_week = window_stats["last_week"].get(pid, {})
    last_week_avg = compute_avg(last_week)
    last_week_delta = compute_delta(last_week_avg, season_avg)

    last_two = window_stats["last_two_weeks"].get(pid, {})
    last_two_avg = compute_avg(last_two)
    last_two_delta = compute_delta(last_two_avg, season_avg)

    last_month = window_stats["last_month"].get(pid, {})
    last_month_avg = compute_avg(last_month)
    last_month_delta = compute_delta(last_month_avg, season_avg)

    stats_bundle = {
        "season": season,
        "season_avg": season_avg,

        "last_week": last_week,
        "last_week_avg": last_week_avg,
        "last_week_delta": last_week_delta,
        "last_week_trend": classify_trend(last_week_delta),

        "last_two_weeks": last_two,
        "last_two_weeks_avg": last_two_avg,
        "last_two_weeks_delta": last_two_delta,
        "last_two_weeks_trend": classify_trend(last_two_delta),

        "last_month": last_month,
        "last_month_avg": last_month_avg,
        "last_month_delta": last_month_delta,
        "last_month_trend": classify_trend(last_month_delta),

        "momentum_score": momentum_score(last_two_delta),
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

print("✅ docs/roster.json written with steps 1–5 (averages, deltas, trends, momentum)")
