"""Fills status/template.svg with live numbers and writes the banner.

Data: the FetchJobs public jobs API and the public status page JSON
(status.fetchjobs.in). Standard library only. If a fetch fails the script
exits with an error, so the workflow keeps the previous banner.

Usage: python status/render.py <output.svg>
"""
import datetime, json, pathlib, sys, urllib.request

HERE = pathlib.Path(__file__).parent
JOBS_API = "https://api.fetchjobs.in/api/v1/jobs?limit=1"
STATUS_API = "https://status.fetchjobs.in/index.json"
COLORS = {"operational": "#3fb950", "degraded": "#d29922", "downtime": "#f85149", "maintenance": "#4493f8"}
WORST = ["operational", "maintenance", "degraded", "downtime"]
AGG_TEXT = {"operational": "All systems operational", "degraded": "Degraded performance",
            "downtime": "Partial outage", "maintenance": "Under maintenance"}
STATE_TEXT = {"operational": "Operational", "degraded": "Degraded", "downtime": "Down", "maintenance": "Maintenance"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "github-profile-status"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def pulse(cx, cy, color):
    return (f'<circle cx="{cx:.0f}" cy="{cy}" r="7" fill="{color}"/>'
            f'<circle cx="{cx:.0f}" cy="{cy}" r="7" fill="none" stroke="{color}" stroke-width="2">'
            '<animate attributeName="r" values="7;18" dur="1.8s" repeatCount="indefinite"/>'
            '<animate attributeName="opacity" values=".8;0" dur="1.8s" repeatCount="indefinite"/></circle>')


def right_status(text, color, y, size):
    cx = 1520 - 0.6 * size * len(text) - 20
    return pulse(cx, y, color) + (f'<text x="1520" y="{y + 7}" text-anchor="end" class="m" '
                                  f'font-size="{size}" fill="{color}">{text}</text>')


def main(out):
    jobs = get(JOBS_API)["pagination"]["total"]
    page = get(STATUS_API)
    resources = [r["attributes"] for r in page["included"] if r["type"] == "status_page_resource"]
    agg = page["data"]["attributes"]["aggregate_state"]

    days = {}
    for r in resources:
        for h in r["status_history"]:
            cur = days.get(h["day"], "operational")
            st = h["status"] if h["status"] in WORST else "operational"
            days[h["day"]] = max(cur, st, key=WORST.index)
    history = [days[d] for d in sorted(days)][-90:]
    history = [None] * (90 - len(history)) + history
    uptime = min(r["availability"] for r in resources) * 100
    uptime_txt = "100%" if uptime >= 99.995 else f"{uptime:.2f}%"
    site = next((r for r in resources if r["public_name"] == "fetchjobs.in"), resources[0])["status"]

    svg = (HERE / "template.svg").read_text()
    y = int(svg.split("%%BARS:")[1].split("%%")[0])
    bars = "".join(
        f'<rect x="{700 + k * 6.4:.1f}" y="{y + 26}" width="5" height="40" rx="1.5" '
        f'fill="{COLORS.get(s, "#2a2a2d")}" opacity="0"><animate attributeName="opacity" from="0" to="1" '
        f'begin="{k * 0.025:.3f}s" dur="0.2s" fill="freeze"/></rect>'
        for k, s in enumerate(history))
    fy = int(svg.split("%%FJ_STATE:")[1].split("%%")[0])
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))

    svg = (svg.replace(f"%%BARS:{y}%%", bars)
              .replace(f"%%FJ_STATE:{fy}%%", right_status(STATE_TEXT.get(site, "Unknown"), COLORS.get(site, "#8d8a84"), fy + 47, 21))
              .replace("%%AGG%%", right_status(AGG_TEXT.get(agg, "Status unknown"), COLORS.get(agg, "#8d8a84"), 78, 19))
              .replace("%%FJ_SUB%%", f"{jobs:,} live jobs · two ingestion pipelines")
              .replace("%%UPTIME%%", f"today · {uptime_txt} uptime")
              .replace("%%FOOTER%%", f"updated {now:%d %b %Y, %H:%M} IST by a GitHub Action · data from fetchjobs.in and status.fetchjobs.in"))
    assert "%%" not in svg, "unfilled placeholder"
    pathlib.Path(out).write_text(svg)
    print(f"jobs={jobs} agg={agg} uptime={uptime_txt} -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
