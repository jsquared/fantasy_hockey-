import json
import os
from datetime import datetime, timezone

# =========================
# CONFIG
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
    "31": "Hit",
    "32": "Blk",
    "19": "Wins",
    "22": "GA",
    "23": "GAA",
    "25": "Saves",
    "24": "Shots Against",
    "26": "SV%",
    "27": "Shutouts"
}

TOP_N = 5  # number of strengths to highlight
BOTTOM_N = 5  # number of weaknesses to highlight

# =========================
# Load your raw team dump
# =========================
with open("docs/team_analysis.json") as f:
    data = json.load(f)

raw_stats = data.get("team_stats", {}).get("stats", [])

# =========================
# Process stats
# =========================
processed_stats = []
for item in raw_stats:
    stat = item.get("stat")
    if not stat:
        continue
    stat_id = str(stat.get("stat_id"))
    raw_value = stat.get("value")
    if raw_value == "":
        continue  # skip empty values

    try:
        # Determine type: SV% and GAA are floats, rest can be int
        if stat_id in {"23", "26"}:
            value = float(raw_value)
        else:
            value = int(float(raw_value))
    except (ValueError, TypeError):
        continue

    processed_stats.append({
        "stat_id": stat_id,
        "name": STAT_MAP.get(stat_id, f"Stat {stat_id}"),
        "value": value
    })

# Sort descending (highest first) for strengths
processed_stats.sort(key=lambda x: x["value"], reverse=True)

strengths = processed_stats[:TOP_N]
weaknesses = list(reversed(processed_stats[-BOTTOM_N:]))

# =========================
# Build analysis payload
# =========================
payload = {
    "week": data.get("team_stats", {}).get("week"),
    "team_points": data.get("team_points", {}).get("total"),
    "total_stats": processed_stats,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

# =========================
# Save analysis
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ Team analysis updated for week", payload["week"])
