"""Generate assets/stats.svg and assets/langs.svg from the GitHub GraphQL API.

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
      contributionCalendar { totalContributions }
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
    print(f"wrote {out / 'stats.svg'} and {out / 'langs.svg'}")


if __name__ == "__main__":
    main()
