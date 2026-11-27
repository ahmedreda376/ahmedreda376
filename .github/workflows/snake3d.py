#!/usr/bin/env python3
"""GitHub contribution board + Google-Snake-style animated snake (rainbow body, blue head).

Usage: GITHUB_TOKEN=... python3 snake3d.py <github_user> <out_dir>
Set SNAKE_DEMO=1 to use random data (no network).
"""
import json
import os
import random
import sys
import urllib.request

P, S = 14.0, 11.0        # cell pitch / square size
M = 14.0                 # margin
STEP = 0.12              # seconds per cell
SEGMENTS = 44            # more segments = smoother, longer body
SEG_GAP = 0.2            # spacing between segments, in cells (small = continuous tube)
BODY_R = 4.6             # body thickness (radius)
HEAD_R = 6.2
PAUSE = 2.0

# Google Snake colours from head to tail
HEAD_COLOR = "#4285f4"
STOPS = [(66, 133, 244), (66, 133, 244), (52, 168, 83), (251, 188, 5), (255, 140, 0), (234, 67, 53)]

THEMES = {
    "light": {"levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]},
    "dark": {"levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]},
}

QUERY = """
query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
weeks{contributionDays{weekday contributionLevel}}}}}}
"""
LEVEL_MAP = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
             "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "snake3d",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(d["weekday"], LEVEL_MAP[d["contributionLevel"]]) for d in w["contributionDays"]]
            for w in weeks]


def demo():
    random.seed(7)
    return [[(j, random.choice([0, 0, 0, 1, 1, 2, 3, 4])) for j in range(7)] for _ in range(53)]


def f(x):
    return f"{x:.1f}"


def body_color(t):
    """t in [0,1]: 0 = neck, 1 = tail tip."""
    pos = t * (len(STOPS) - 1)
    a = min(int(pos), len(STOPS) - 2)
    u = pos - a
    c = [round(STOPS[a][i] + (STOPS[a + 1][i] - STOPS[a][i]) * u) for i in range(3)]
    return "#%02x%02x%02x" % tuple(c)


def build(weeks, theme):
    lv = THEMES[theme]["levels"]
    empty = lv[0]
    n_weeks = len(weeks)
    width = 2 * M + n_weeks * P
    height = 2 * M + 7 * P

    cells = {}
    for i, w in enumerate(weeks):
        for j, lvl in w:
            cells[(i, j)] = lvl

    def center(i, j):
        return M + i * P + S / 2, M + j * P + S / 2

    order = []
    for i in range(n_weeks):
        js = sorted(j for (ii, j) in cells if ii == i)
        order += [(i, j) for j in (js if i % 2 == 0 else reversed(js))]
    n = len(order)
    T = n * STEP
    D = (SEGMENTS - 1) * SEG_GAP * STEP
    total = T + D + PAUSE

    out = []
    w = out.append
    w(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
      f'viewBox="0 0 {f(width)} {f(height)}" width="{f(width)}" height="{f(height)}">')
    w('<title>snake</title>')
    w('<defs>')
    path = " L".join(f"{f(x)},{f(y)}" for x, y in (center(i, j) for i, j in order))
    w(f'<path id="p" d="M{path}" fill="none"/>')
    w('</defs>')

    # Board
    eaten = {c: k for k, c in enumerate(order)}
    for (i, j), lvl in sorted(cells.items()):
        x, y = M + i * P, M + j * P
        col = lv[lvl]
        if lvl == 0:
            w(f'<rect x="{f(x)}" y="{f(y)}" width="{S}" height="{S}" rx="2" fill="{col}"/>')
        else:
            tk = (eaten[(i, j)] * STEP) / total
            w(f'<rect x="{f(x)}" y="{f(y)}" width="{S}" height="{S}" rx="2" fill="{col}">'
              f'<animate attributeName="fill" values="{col};{empty};{empty}" keyTimes="0;{tk:.5f};1" '
              f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/></rect>')

    def motion(k, rotate=False):
        d = k * SEG_GAP * STEP
        kt = [0.0, d / total, (d + T) / total, 1.0]
        kp = [0.0, 0.0, 1.0, 1.0]
        if d == 0:
            kt, kp = kt[1:], kp[1:]
        kts = ";".join(f"{v:.5f}" for v in kt)
        kps = ";".join(f"{v:.1f}" for v in kp)
        rot = ' rotate="auto"' if rotate else ""
        return (f'<animateMotion dur="{total:.2f}s" repeatCount="indefinite" calcMode="linear" '
                f'keyPoints="{kps}" keyTimes="{kts}"{rot}><mpath xlink:href="#p"/></animateMotion>')

    # Body: many overlapping circles = one smooth, thick, rounded tube (tail -> neck)
    for k in range(SEGMENTS - 1, 0, -1):
        col = body_color(k / (SEGMENTS - 1))
        w(f'<circle r="{f(BODY_R)}" fill="{col}">{motion(k)}</circle>')

    # Head (blue, white eyes, rotates along the path)
    w('<g>'
      f'<ellipse cx="0" cy="0" rx="{f(HEAD_R)}" ry="{f(HEAD_R - 0.4)}" fill="{HEAD_COLOR}"/>'
      '<circle cx="2.2" cy="-2.9" r="2.1" fill="#fff"/><circle cx="2.2" cy="2.9" r="2.1" fill="#fff"/>'
      '<circle cx="2.9" cy="-2.9" r="1.0" fill="#1f2937"/><circle cx="2.9" cy="2.9" r="1.0" fill="#1f2937"/>'
      f'{motion(0, rotate=True)}</g>')

    w('</svg>')
    return "\n".join(out)


def main():
    user = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    weeks = demo() if os.environ.get("SNAKE_DEMO") else fetch(user, os.environ["GITHUB_TOKEN"])
    for theme, name in (("light", "github-snake.svg"), ("dark", "github-snake-dark.svg")):
        with open(os.path.join(out_dir, name), "w") as fh:
            fh.write(build(weeks, theme))
        print("wrote", name)


if __name__ == "__main__":
    main()
