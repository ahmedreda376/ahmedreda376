#!/usr/bin/env python3
"""GitHub contribution board + Google-Snake-style animated snake (rainbow body, blue head).

The snake takes the shortest route to eat every contribution square (nearest-neighbour
tour improved with 2-opt) instead of sweeping the whole board column by column.

Usage: GITHUB_TOKEN=... python3 snake3d.py <github_user> <out_dir>
Set SNAKE_DEMO=1 to use random data (no network).
"""
import json
import os
import random
import sys
import urllib.request
from collections import deque

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


# ---------------------------------------------------------------- path planning
def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def plan_tour(cells):
    """Order in which to visit the contribution squares (short open tour)."""
    start = (0, min(j for (i, j) in cells if i == 0))
    remaining = {c for c, lvl in cells.items() if lvl > 0}
    remaining.discard(start)

    # 1) nearest neighbour (ties: prefer left/top so it drifts left -> right)
    tour, cur = [start], start
    while remaining:
        nxt = min(remaining, key=lambda t: (dist(cur, t), t[0], t[1]))
        tour.append(nxt)
        remaining.discard(nxt)
        cur = nxt

    # 2) 2-opt: reverse segments while it shortens the total route (start stays fixed)
    n = len(tour)
    improved, rounds = True, 0
    while improved and rounds < 50:
        improved = False
        rounds += 1
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b = tour[i - 1], tour[i]
                c = tour[j]
                d = tour[j + 1] if j + 1 < n else None
                old = dist(a, b) + (dist(c, d) if d else 0)
                new = dist(a, c) + (dist(b, d) if d else 0)
                if new < old:
                    tour[i:j + 1] = reversed(tour[i:j + 1])
                    improved = True
    return start, tour


def bfs_route(cells, a, b):
    """Shortest route through existing cells (fallback)."""
    prev = {a: None}
    q = deque([a])
    while q:
        cur = q.popleft()
        if cur == b:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (cur[0] + dx, cur[1] + dy)
            if nb in cells and nb not in prev:
                prev[nb] = cur
                q.append(nb)
    route, cur = [], b
    while cur != a:
        route.append(cur)
        cur = prev[cur]
    return route[::-1]


def l_route(cells, a, b, horizontal_first):
    """L-shaped route a -> b (excluding a). None if it leaves the board."""
    route, (x, y) = [], a
    legs = ("x", "y") if horizontal_first else ("y", "x")
    for leg in legs:
        if leg == "x":
            while x != b[0]:
                x += 1 if b[0] > x else -1
                route.append((x, y))
        else:
            while y != b[1]:
                y += 1 if b[1] > y else -1
                route.append((x, y))
    return route if all(c in cells for c in route) else None


def build_path(cells):
    start, tour = plan_tour(cells)
    path, seen = [start], {start}
    for target in tour[1:]:
        if target in seen:          # already eaten on the way
            continue
        cands = [r for r in (l_route(cells, path[-1], target, True),
                             l_route(cells, path[-1], target, False)) if r]
        if not cands:
            cands = [bfs_route(cells, path[-1], target)]
        # choose the L-shape that eats more squares on the way
        route = max(cands, key=lambda r: sum(1 for c in r if c not in seen and cells[c] > 0))
        for c in route:
            path.append(c)
            seen.add(c)
    if len(path) < 2:               # nothing to eat: take one step so the animation is valid
        nb = next((c for c in ((start[0] + 1, start[1]), (start[0], start[1] + 1)) if c in cells), start)
        path.append(nb)
    return path


# ---------------------------------------------------------------- svg
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

    order = build_path(cells)
    n = len(order)
    T = (n - 1) * STEP
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

    # Board: a square disappears the first time the head reaches it
    eaten = {}
    for k, c in enumerate(order):
        eaten.setdefault(c, k)
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
    return "\n".join(out), n


def main():
    user = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    weeks = demo() if os.environ.get("SNAKE_DEMO") else fetch(user, os.environ["GITHUB_TOKEN"])
    for theme, name in (("light", "github-snake.svg"), ("dark", "github-snake-dark.svg")):
        svg, steps = build(weeks, theme)
        with open(os.path.join(out_dir, name), "w") as fh:
            fh.write(svg)
        print("wrote", name, f"({steps} steps)")


if __name__ == "__main__":
    main()
