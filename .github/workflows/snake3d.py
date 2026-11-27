#!/usr/bin/env python3
"""Generate an isometric (pseudo-3D) animated snake over the GitHub contribution graph.

Usage: GITHUB_TOKEN=... python3 snake3d.py <github_user> <out_dir>
Set SNAKE_DEMO=1 to use random data (no network).
"""
import json
import os
import random
import sys
import urllib.request

A, B = 9.0, 4.5          # half tile width / height (isometric)
GAP = 0.92               # tile shrink factor (space between cubes)
LEVEL_H = [0, 3, 6, 9, 12]
STEP = 0.13              # seconds per cell
SEGMENTS = 18
SEG_GAP = 0.8            # spacing between segments, in cells
PAUSE = 2.0

THEMES = {
    "light": {
        "empty": "#ebedf0",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    },
    "dark": {
        "empty": "#161b22",
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
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


def shade(hex_color, f):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (int(r * f), int(g * f), int(b * f))


def f(x):
    return f"{x:.1f}"


def build(weeks, theme):
    t = THEMES[theme]
    n_weeks = len(weeks)
    ox, oy = 7 * A, 34
    width = (n_weeks + 7) * A
    height = oy + (n_weeks + 7) * B + 22

    def center(i, j):
        return ox + (i - j) * A, oy + (i + j) * B

    cells = {}
    for i, w in enumerate(weeks):
        for j, lvl in w:
            cells[(i, j)] = lvl

    # Snake path: zig-zag column by column
    order = []
    for i in range(n_weeks):
        js = sorted(j for (ii, j) in cells if ii == i)
        order += [(i, j) for j in (js if i % 2 == 0 else reversed(js))]
    n = len(order)
    T = n * STEP
    D = (SEGMENTS - 1) * SEG_GAP * STEP
    total = T + D + PAUSE
    eaten_at = {c: (k * STEP) / total for k, c in enumerate(order)}

    out = []
    w = out.append
    w(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
      f'viewBox="0 0 {f(width)} {f(height)}" width="{f(width)}" height="{f(height)}">')
    w('<title>3D snake</title>')
    w('<defs>')
    pts = []
    for (i, j) in order:
        x, y = center(i, j)
        pts.append(f"{f(x)},{f(y - 5)}")
    w(f'<path id="p" d="M{" L".join(pts)}" fill="none"/>')
    for name, c1, c2, c3 in (("gA", "#fde68a", "#f59e0b", "#92400e"),
                             ("gB", "#fcd34d", "#d97706", "#78350f")):
        w(f'<radialGradient id="{name}" cx="35%" cy="30%" r="75%">'
          f'<stop offset="0" stop-color="{c1}"/><stop offset="0.5" stop-color="{c2}"/>'
          f'<stop offset="1" stop-color="{c3}"/></radialGradient>')
    w('<radialGradient id="gH" cx="35%" cy="30%" r="80%"><stop offset="0" stop-color="#fef3c7"/>'
      '<stop offset="0.45" stop-color="#f59e0b"/><stop offset="1" stop-color="#7c2d12"/></radialGradient>')
    w('</defs>')

    # Tiles + cubes, back to front
    for s in range(0, n_weeks + 7):
        for i in range(n_weeks):
            j = s - i
            if (i, j) not in cells:
                continue
            lvl = cells[(i, j)]
            x, y = center(i, j)
            a, b = A * GAP, B * GAP
            w(f'<polygon points="{f(x)},{f(y-b)} {f(x+a)},{f(y)} {f(x)},{f(y+b)} {f(x-a)},{f(y)}" '
              f'fill="{t["empty"]}"/>')
            if lvl == 0:
                continue
            h = LEVEL_H[lvl]
            col = t["levels"][lvl]
            tk = eaten_at[(i, j)]
            w('<g>')
            w(f'<polygon points="{f(x-a)},{f(y-h)} {f(x)},{f(y+b-h)} {f(x)},{f(y+b)} {f(x-a)},{f(y)}" fill="{shade(col, .72)}"/>')
            w(f'<polygon points="{f(x+a)},{f(y-h)} {f(x)},{f(y+b-h)} {f(x)},{f(y+b)} {f(x+a)},{f(y)}" fill="{shade(col, .55)}"/>')
            w(f'<polygon points="{f(x)},{f(y-b-h)} {f(x+a)},{f(y-h)} {f(x)},{f(y+b-h)} {f(x-a)},{f(y-h)}" fill="{col}"/>')
            w(f'<animate attributeName="opacity" values="1;0;0" keyTimes="0;{tk:.5f};1" '
              f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>')
            w('</g>')

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

    def radius(k):
        return 5.4 * (1 - 0.62 * (k / (SEGMENTS - 1)) ** 1.1)

    # Shadows
    for k in range(SEGMENTS - 1, -1, -1):
        r = 6.8 if k == 0 else radius(k)
        w(f'<g><ellipse cx="2" cy="6" rx="{f(r)}" ry="{f(r*0.5)}" fill="#000" opacity="0.28"/>{motion(k)}</g>')

    # Body (tail -> neck)
    for k in range(SEGMENTS - 1, 0, -1):
        r = radius(k)
        g = "gA" if k % 2 else "gB"
        spot = (f'<ellipse cx="0" cy="{f(-r*0.35)}" rx="{f(r*0.5)}" ry="{f(r*0.28)}" fill="#451a03" opacity="0.5"/>'
                if k % 2 == 0 else "")
        w(f'<g><circle r="{f(r)}" fill="url(#{g})"/>{spot}'
          f'<ellipse cx="{f(-r*0.3)}" cy="{f(-r*0.42)}" rx="{f(r*0.35)}" ry="{f(r*0.2)}" fill="#fff" opacity="0.35"/>'
          f'{motion(k)}</g>')

    # Head (rotates along the path)
    w('<g>'
      '<ellipse cx="0" cy="0" rx="8.4" ry="6.2" fill="url(#gH)"/>'
      '<ellipse cx="-2" cy="-3.6" rx="3" ry="1.3" fill="#fff" opacity="0.35"/>'
      '<circle cx="2.6" cy="-3.1" r="1.9" fill="#fff"/><circle cx="2.6" cy="3.1" r="1.9" fill="#fff"/>'
      '<ellipse cx="3" cy="-3.1" rx="0.6" ry="1.4" fill="#111"/><ellipse cx="3" cy="3.1" rx="0.6" ry="1.4" fill="#111"/>'
      '<g stroke="#ef4444" stroke-width="0.9" stroke-linecap="round" fill="none">'
      '<path d="M8,0 L12.5,0 M12.5,0 L15,-2 M12.5,0 L15,2"/>'
      '<animate attributeName="opacity" values="1;1;0;1" keyTimes="0;0.5;0.6;1" dur="0.9s" repeatCount="indefinite"/></g>'
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
