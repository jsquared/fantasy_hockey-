import json
import os
import math
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
        except Exception:
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

# ---- AVERAGES & DELTAS ----
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
    return {
        sid: round(recent_avg[sid] - season_avg[sid], 3)
        for sid in recent_avg
        if sid in season_avg
    }

# ---- STEP 2: TREND SCORE ----
WEIGHTS = {
    "last_week": 0.5,
    "last_two_weeks": 0.3,
    "last_month": 0.2
}

EXCLUDE_STATS = {"31", "32"}

def compute_trend_score(stats):
    score = 0.0
    breakdown = {}

    for window, weight in WEIGHTS.items():
        deltas = stats.get(f"{window}_delta", {})
        for sid, delta in deltas.items():
            if sid in EXCLUDE_STATS:
                continue
            breakdown.setdefault(sid, 0.0)
            breakdown[sid] += delta * weight
            score += delta * weight

    return round(score, 3), {k: round(v, 3) for k, v in breakdown.items()}

# ---- FETCH WINDOWS ----
today_str = date.today().isoformat()

stat_windows = {
    "season": "season",
    "last_week": "lastweek",
    "last_month": "lastmonth",
    "today": f"date;date={today_str}"
}

window_stats = {k: fetch_stats(v) for k, v in stat_windows.items()}

# ---- DERIVE LAST TWO WEEKS ----
last_two_weeks = {}
for pid, lw in window_stats["last_week"].items():
    last_two_weeks[pid] = {
        sid: val * 2 for sid, val in lw.items() if isinstance(val, (int, float))
    }

window_stats["last_two_weeks"] = last_two_weeks

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

    pid = int(extract_value(meta, "player_id"))
    name = extract_value(meta, "name").get("full")
    pos = player[1]["selected_position"][1]["position"]
    team_abbr = extract_value(meta, "editorial_team_abbr")

    season = window_stats["season"].get(pid, {})
    season_avg = compute_avg(season)

    lw = window_stats["last_week"].get(pid, {})
    lw_avg = compute_avg(lw)

    l2w = window_stats["last_two_weeks"].get(pid, {})
    l2w_avg = compute_avg(l2w)

    lm = window_stats["last_month"].get(pid, {})
    lm_avg = compute_avg(lm)

    stats_bundle = {
        "season": season,
        "season_avg": season_avg,

        "last_week": lw,
        "last_week_avg": lw_avg,
        "last_week_delta": compute_delta(lw_avg, season_avg),

        "last_two_weeks": l2w,
        "last_two_weeks_avg": l2w_avg,
        "last_two_weeks_delta": compute_delta(l2w_avg, season_avg),

        "last_month": lm,
        "last_month_avg": lm_avg,
        "last_month_delta": compute_delta(lm_avg, season_avg),

        "today": window_stats["today"].get(pid, {})
    }

    trend_score, trend_breakdown = compute_trend_score(stats_bundle)

    roster_output.append({
        "player_id": pid,
        "name": name,
        "selected_position": pos,
        "editorial_team": team_abbr,
        "trend_score": trend_score,
        "trend_breakdown": trend_breakdown,
        "stats": stats_bundle
    })

# ---- STEP 3: POSITION NORMALIZATION ----
positions = {}
for p in roster_output:
    positions.setdefault(p["selected_position"], []).append(p)

for pos, players in positions.items():
    scores = [p["trend_score"] for p in players]
    mean = sum(scores) / len(scores)
    std = math.sqrt(sum((s - mean) ** 2 for s in scores) / len(scores)) or 1.0

    players.sort(key=lambda x: x["trend_score"], reverse=True)

    for rank, p in enumerate(players, start=1):
        z = (p["trend_score"] - mean) / std
        percentile = round(
            100 * (len(players) - rank) / (len(players) - 1), 1
        ) if len(players) > 1 else 100.0

        p["trend_rank_pos"] = rank
        p["trend_z_pos"] = round(z, 3)
        p["trend_percentile_pos"] = percentile

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

print("✅ docs/roster.json written with position-normalized trends")
