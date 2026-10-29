"""Generate assets/stats.svg, assets/langs.svg and assets/vitals.svg from the GitHub GraphQL API.

Usage: GITHUB_TOKEN=... python scripts/gen_stats.py Maddy824
"""
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount } }
      }
      totalPullRequestContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

BG = "#070b1a"
BG2 = "#0b2233"
MUTED = "#5c6f91"
TEXT = "#e6edf3"
ACCENTS = ["#2de2e6", "#ff8a3d", "#fee440", "#9b5de5", "#f15bb5", "#00f5d4"]
MONO = "ui-monospace,Menlo,Consolas,monospace"
CARD_HEIGHT = 254  # both cards share it so they line up side by side


def fetch(login: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def frame(width: int, height: int, title: str, inner: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG2}"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="14" fill="url(#bg)"/>
  <text x="24" y="34" font-family="{MONO}" font-size="13" fill="{MUTED}">$ {escape(title)}</text>
{inner}
</svg>
"""


def stats_svg(user: dict) -> str:
    repos = user["repositories"]
    stars = sum(r["stargazerCount"] for r in repos["nodes"])
    cc = user["contributionsCollection"]
    rows = [
        ("contributions (last year)", cc["contributionCalendar"]["totalContributions"]),
        ("public repos", repos["totalCount"]),
        ("stars earned", stars),
        ("pull requests (last year)", cc["totalPullRequestContributions"]),
        ("followers", user["followers"]["totalCount"]),
    ]
    lines = []
    for i, (label, value) in enumerate(rows):
        y = 76 + i * 36
        delay = f"{0.15 * i:.2f}s"
        colour = ACCENTS[i % len(ACCENTS)]
        lines.append(
            f'  <g opacity="0" font-family="{MONO}" font-size="15">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{delay}" dur="0.5s" fill="freeze"/>'
            f'<text x="24" y="{y}" fill="{TEXT}">{escape(label)}</text>'
            f'<text x="376" y="{y}" fill="{colour}" text-anchor="end" font-weight="700">{value:,}</text></g>'
        )
    return frame(400, CARD_HEIGHT, "git stats --me", "\n".join(lines))


def langs_svg(user: dict, top: int = 6) -> str:
    totals: dict[str, int] = {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top]
    grand = sum(size for _, size in ranked) or 1
    lines = []
    for i, (name, size) in enumerate(ranked):
        pct = size / grand * 100
        y = 64 + i * 30
        bar = max(4, 170 * size / ranked[0][1])
        delay = f"{0.15 * i:.2f}s"
        colour = ACCENTS[i % len(ACCENTS)]
        lines.append(
            f'  <g font-family="{MONO}" font-size="14">'
            f'<text x="24" y="{y + 12}" fill="{TEXT}">{escape(name)}</text>'
            f'<rect x="130" y="{y}" width="0" height="14" rx="7" fill="{colour}">'
            f'<animate attributeName="width" from="0" to="{bar:.0f}" begin="{delay}" dur="0.8s" fill="freeze"/></rect>'
            f'<text x="376" y="{y + 12}" fill="{MUTED}" text-anchor="end">{pct:.1f}%</text></g>'
        )
    return frame(400, CARD_HEIGHT, "ls languages/", "\n".join(lines))


def vitals_svg(user: dict, days: int = 30) -> str:
    """Heart-monitor trace: one heartbeat spike per day with contributions, flatline otherwise."""
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts = [d["contributionCount"] for w in weeks for d in w["contributionDays"]][-days:]
    peak = max(counts) or 1
    last7 = sum(counts[-7:])
    streak = 0
    for c in reversed(counts):
        if not c:
            break
        streak += 1

    width, height = 900, 300
    left, right, base = 40, 860, 200
    step = (right - left) / max(1, len(counts) - 1)
    pts = [(left, base)]
    for i, c in enumerate(counts):
        x = left + i * step
        if c:
            h = 20 + 78 * (c / peak) ** 0.5  # tallest spike stays below the readouts
            pts += [(x - step * 0.3, base), (x - step * 0.15, base + 8),
                    (x, base - h), (x + step * 0.15, base + 14), (x + step * 0.3, base)]
        else:
            pts.append((x, base))
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)

    status, colour = ("ALIVE (caffeinated)", "#00f5d4") if last7 else ("FLATLINED (on a break)", "#f15bb5")
    readouts = [("BPM", f"{last7}", "#2de2e6"), ("PEAK", f"{peak}", "#ff8a3d"), ("STREAK", f"{streak}d", "#fee440")]
    tiles = "\n".join(
        f'  <text x="{560 + i * 110}" y="44" font-family="{MONO}" font-size="11" fill="{MUTED}">{label}</text>'
        f'<text x="{560 + i * 110}" y="74" font-family="{MONO}" font-size="28" font-weight="700" fill="{col}">{escape(val)}</text>'
        for i, (label, val, col) in enumerate(readouts)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Heart monitor drawn from the last {days} days of contributions: {last7} this week, peak {peak} in a day, {streak} day streak">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG2}"/>
    </linearGradient>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M20 0H0V20" fill="none" stroke="#2de2e6" stroke-opacity="0.06"/>
    </pattern>
    <filter id="glow" x="-10%" y="-30%" width="120%" height="160%">
      <feGaussianBlur stdDeviation="3" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{BG}" stop-opacity="0"/><stop offset="1" stop-color="{BG}" stop-opacity="1"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="16" fill="url(#bg)"/>
  <rect x="20" y="96" width="860" height="184" fill="url(#grid)"/>
  <text x="40" y="44" font-family="{MONO}" font-size="13" fill="{MUTED}">$ dev-vitals --last {days}d</text>
  <text x="40" y="74" font-family="{MONO}" font-size="20" font-weight="700" fill="{colour}">● {escape(status)}<animate attributeName="opacity" values="1;0.35;1" dur="1.2s" repeatCount="indefinite"/></text>
{tiles}
  <path d="{path}" fill="none" stroke="#2de2e6" stroke-opacity="0.12" stroke-width="2"/>
  <path d="{path}" fill="none" stroke="#2de2e6" stroke-width="2.4" stroke-linejoin="round" filter="url(#glow)" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1">
    <animate attributeName="stroke-dashoffset" values="1;0;0" keyTimes="0;0.85;1" dur="7s" repeatCount="indefinite"/>
  </path>
  <circle r="5" fill="#f4f7ff" filter="url(#glow)">
    <animateMotion dur="7s" keyPoints="0;1;1" keyTimes="0;0.85;1" calcMode="linear" repeatCount="indefinite" path="{path}"/>
  </circle>
  <text x="860" y="290" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">one spike per day I shipped something. flat = touching grass.</text>
</svg>
"""


def main() -> None:
    login = sys.argv[1] if len(sys.argv) > 1 else "Maddy824"
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    user = fetch(login, token)
    out = Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(exist_ok=True)
    (out / "stats.svg").write_text(stats_svg(user), encoding="utf-8")
    (out / "langs.svg").write_text(langs_svg(user), encoding="utf-8")
    (out / "vitals.svg").write_text(vitals_svg(user), encoding="utf-8")
    print(f"wrote stats.svg, langs.svg and vitals.svg to {out}")


if __name__ == "__main__":
    main()
