"""Generates the animated SVG artwork used by the profile README.

Every graphic is rendered twice (dark + light) and embeds only the glyphs it
needs from the fonts in ./fonts, so the images look identical everywhere.

    pip install fonttools brotli
    python assets/build.py
"""

import base64
import io
import math
import random
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

HERE = Path(__file__).parent
OUT = HERE / "svg"

FONTS = {
    "serif": "instrument-serif-latin-400-normal.woff2",
    "serif-i": "instrument-serif-latin-400-italic.woff2",
    "sans": "inter-tight-latin-400-normal.woff2",
    "sans-m": "inter-tight-latin-500-normal.woff2",
    "mono": "jetbrains-mono-latin-400-normal.woff2",
    "mono-m": "jetbrains-mono-latin-500-normal.woff2",
}
FALLBACK = {
    "serif": "Georgia,serif",
    "serif-i": "Georgia,serif",
    "sans": "Helvetica,Arial,sans-serif",
    "sans-m": "Helvetica,Arial,sans-serif",
    "mono": "Menlo,Consolas,monospace",
    "mono-m": "Menlo,Consolas,monospace",
}
_fonts = {k: TTFont(HERE / "fonts" / v) for k, v in FONTS.items()}

THEMES = {
    "dark": dict(
        bg="#0B0B0C", surface="#121213", line="#262628", text="#F2EFE9",
        muted="#8C8A85", faint="#3A3A3D", accent="#FF6A3D", on_accent="#0B0B0C",
        grain=0.07,
    ),
    "light": dict(
        bg="#F5F3EE", surface="#EFECE6", line="#DAD6CD", text="#141414",
        muted="#6A6863", faint="#C4C0B7", accent="#E2461B", on_accent="#FFFFFF",
        grain=0.05,
    ),
}


def measure(s, font, size, ls=0.0):
    f = _fonts[font]
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    w = 0
    for ch in s:
        g = cmap.get(ord(ch))
        if g is None:
            raise ValueError(f"glyph {ch!r} missing from {font}")
        w += hmtx[g][0]
    return w / upm * size + ls * len(s)


def wrap(s, font, size, width):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, font, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SVG:
    def __init__(self, w, h, title, theme):
        self.w, self.h, self.title, self.t = w, h, title, THEMES[theme]
        self.body, self.css, self.used = [], [], {}

    def add(self, s):
        self.body.append(s)

    def text(self, x, y, runs, size, fill, anchor="start", ls=0, cls="", extra=""):
        """runs: a string (sans) or a list of (text, font[, fill]) tuples."""
        if isinstance(runs, str):
            runs = [(runs, "sans")]
        spans = []
        for run in runs:
            s, font = run[0], run[1]
            color = run[2] if len(run) > 2 else None
            measure(s, font, size)  # fail loudly on missing glyphs
            self.used.setdefault(font, set()).update(s)
            fc = f' fill="{color}"' if color else ""
            spans.append(f'<tspan font-family="f-{font},{FALLBACK[font]}"{fc}>{esc(s)}</tspan>')
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        l = f' letter-spacing="{ls}"' if ls else ""
        c = f' class="{cls}"' if cls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}"{a}{l}{c} {extra}>{"".join(spans)}</text>')

    def panel(self, rx=22):
        t = self.t
        self.add(
            f'<rect x=".5" y=".5" width="{self.w-1}" height="{self.h-1}" rx="{rx}" fill="{t["bg"]}" stroke="{t["line"]}"/>'
            f'<rect width="{self.w}" height="{self.h}" rx="{rx}" filter="url(#grain)" opacity="{t["grain"]}"/>'
        )

    def render(self):
        faces = []
        for font, chars in sorted(self.used.items()):
            opts = Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga"]
            sub = Subsetter(opts)
            sub.populate(text="".join(chars) + " ")
            f = TTFont(HERE / "fonts" / FONTS[font])
            sub.subset(f)
            f.flavor = "woff2"
            buf = io.BytesIO()
            f.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            faces.append(f"@font-face{{font-family:f-{font};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
        css = "".join(faces) + BASE_CSS + "".join(self.css)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" fill="none" role="img" aria-label="{esc(self.title)}">'
            f"<title>{esc(self.title)}</title><style>{css}</style>"
            '<defs><filter id="grain" x="0" y="0" width="100%" height="100%">'
            '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/>'
            '<feColorMatrix values="0 0 0 0 .5 0 0 0 0 .5 0 0 0 0 .5 0 0 0 1 0"/></filter></defs>'
            + "".join(self.body)
            + "</svg>"
        )


BASE_CSS = (
    "text{font-kerning:normal}"
    ".rise{animation:rise 1.1s cubic-bezier(.16,.8,.2,1) both}"
    "@keyframes rise{from{opacity:0;transform:translateY(22px)}}"
    ".fade{animation:fade 1.2s ease both}"
    "@keyframes fade{from{opacity:0}}"
    ".draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.6s cubic-bezier(.65,0,.35,1) forwards}"
    "@keyframes draw{to{stroke-dashoffset:0}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)


def d(delay):
    return f'style="animation-delay:{delay:.2f}s"'


def hline(svg, x1, x2, y, color, delay=0.0, cls="draw"):
    svg.add(f'<path d="M{x1} {y}H{x2}" stroke="{color}" pathLength="1" class="{cls}" {d(delay)}/>')


def pulse_dot(svg, cx, cy, color, r=4.5):
    svg.add(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{color}" stroke-width="1.5">'
        f'<animate attributeName="r" values="{r};{r*3.2}" dur="2s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values=".8;0" dur="2s" repeatCount="indefinite"/></circle>'
    )


# --------------------------------------------------------------------------- hero

def hero(theme):
    W, H = 1200, 640
    s = SVG(W, H, "Rana Selim — Computer Engineer, AI & Data Science", theme)
    t = s.t
    s.panel(26)
    P = 56

    s.text(P, 78, [("RANA SELIM", "mono-m"), ("  /  PROFILE", "mono", t["muted"])], 15, t["text"], ls=1.6, cls="fade")
    right = "CURRENTLY BUILDING WITH LLMS & RAG"
    s.text(W - P, 78, [(right, "mono")], 15, t["muted"], anchor="end", ls=1.6, cls="fade")
    pulse_dot(s, W - P - measure(right, "mono", 15, 1.6) - 16, 73, t["accent"])
    hline(s, P, W - P, 104, t["line"], 0.1)

    s.text(44, 300, [("Rana", "serif")], 208, t["text"], cls="rise", extra=d(0.15))
    sel = measure("Selim", "serif-i", 208)
    s.text(150, 474, [("Selim", "serif-i")], 208, t["text"], cls="rise", extra=d(0.3))
    s.text(150 + sel + 4, 474, [(".", "serif")], 208, t["accent"], cls="rise", extra=d(0.45))

    # causal self-attention matrix — the hero's generative piece
    tokens = ["build", "systems", "that", "learn", "and", "ship"]
    n, cell, gap = len(tokens), 38, 7
    pitch = cell + gap
    gx, gy = W - P - (n * pitch - gap), 196
    rnd = random.Random(7)
    for i, tok in enumerate(tokens):
        cy = gy + i * pitch + cell / 2
        s.text(gx - 16, cy + 5, [(tok, "mono")], 15, t["muted"], anchor="end", cls="fade", extra=d(0.6 + i * 0.05))
        cx = gx + i * pitch + cell / 2
        s.text(cx - 4, gy - 16, [(tok, "mono")], 15, t["muted"], cls="fade",
               extra=f'transform="rotate(-50 {cx-4} {gy-16})" ' + d(0.6 + i * 0.05))
    for i in range(n):
        states = []
        for _ in range(3):
            w = [math.exp(rnd.gauss(0, 1.3)) for _ in range(i + 1)]
            m = max(w)
            states.append([0.1 + 0.9 * v / m for v in w])
        for j in range(n):
            x, y = gx + j * pitch, gy + i * pitch
            delay = 0.7 + (i + j) * 0.045
            if j <= i:
                vals = ";".join(f"{st[j]:.2f}" for st in states + states[:1])
                s.add(
                    f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="5" fill="{t["accent"]}" class="fade" {d(delay)}>'
                    f'<animate attributeName="fill-opacity" values="{vals}" keyTimes="0;.33;.66;1" dur="9s" '
                    f'calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/></rect>'
                )
            else:
                s.add(f'<rect x="{x+.5}" y="{y+.5}" width="{cell-1}" height="{cell-1}" rx="5" stroke="{t["faint"]}" '
                      f'stroke-dasharray="3 4" class="fade" {d(delay)}/>')
    s.text(W - P, gy + n * pitch + 26, [("FIG. 01 — CAUSAL SELF-ATTENTION", "mono")], 14, t["muted"],
           anchor="end", ls=1.4, cls="fade", extra=d(1.2))

    hline(s, P, W - P, 548, t["line"], 0.5)
    s.text(P, 598, [("Computer engineer bridging software architecture and machine learning.", "sans")],
           21, t["text"], cls="fade", extra=d(0.9))
    words = ["LLMS", "RAG PIPELINES", "COMPUTER VISION", "DATA SCIENCE"]
    s.text(W - P - max(measure(w, "mono-m", 15, 1.6) for w in words) - 28, 597, [("FOCUS /", "mono")], 15, t["muted"], anchor="end", ls=1.6, cls="fade", extra=d(1))
    for k, wd in enumerate(words):
        s.text(W - P, 597, [(wd, "mono-m")], 15, t["accent"], anchor="end", ls=1.6, cls="rot", extra=d(k * 3))
    s.css.append(
        ".rot{opacity:0;animation:rot 12s cubic-bezier(.16,.8,.2,1) infinite}"
        "@keyframes rot{0%{opacity:0;transform:translateY(10px)}4%,22%{opacity:1;transform:none}"
        "27%,100%{opacity:0;transform:translateY(-10px)}}"
    )
    return s


# ------------------------------------------------------------------ section heads

def section(theme, num, runs, caption, title):
    W, H = 1200, 132
    s = SVG(W, H, title, theme)
    t = s.t
    s.text(2, 88, [(f"({num})", "mono-m")], 17, t["accent"], ls=1, cls="fade")
    s.text(76, 96, runs, 70, t["text"], cls="rise", extra=d(0.05))
    s.text(W - 2, 88, [(caption, "mono")], 15, t["muted"], anchor="end", ls=1.6, cls="fade", extra=d(0.2))
    hline(s, 0, W, 124, t["line"], 0.1)
    s.add(f'<path d="M0 124H64" stroke="{t["accent"]}" stroke-width="2" pathLength="1" class="draw" {d(0.4)}/>')
    return s


# --------------------------------------------------------------------- trajectory

def trajectory(theme):
    W, H = 1200, 368
    s = SVG(W, H, "Trajectory: software development, AI specialist program, AI engineering", theme)
    t = s.t
    s.panel()
    P, gap = 56, 40
    colw = (W - 2 * P - 2 * gap) / 3
    ly = 104
    hline(s, P, W - P, ly, t["line"], 0.1)
    s.add(f'<path d="M{P} {ly}H{W-P}" stroke="{t["accent"]}" stroke-width="2" stroke-linecap="round" '
          f'pathLength="100" stroke-dasharray="9 91"><animate attributeName="stroke-dashoffset" '
          f'values="9;-91" dur="4.5s" repeatCount="indefinite"/></path>')
    cols = [
        ("PREVIOUSLY", "Software", "Ecodation · Granobra",
         "Built scalable web applications, multilingual platforms and payment interfaces on microservices."),
        ("RECENTLY", "AI Specialist", "Europe Coding School",
         "Intensive program focused on LLM architectures and model deployment."),
        ("NOW", "AI Engineering", "LLMs · RAG · Vision",
         "Designing intelligent products with Transformers, Hugging Face and vector databases."),
    ]
    for k, (lab, title, sub, body) in enumerate(cols):
        x = P + k * (colw + gap)
        dl = 0.2 + k * 0.15
        now = k == 2
        s.text(x, 72, [(lab, "mono-m")], 15, t["accent"] if now else t["muted"], ls=1.6, cls="fade", extra=d(dl))
        if now:
            pulse_dot(s, x + 5, ly, t["accent"], 5.5)
        else:
            s.add(f'<circle cx="{x+5}" cy="{ly}" r="5.5" fill="{t["bg"]}" stroke="{t["text"]}" stroke-width="1.5"/>')
        s.text(x, 178, [(title, "serif-i" if now else "serif")], 48, t["text"], cls="rise", extra=d(dl + 0.1))
        s.text(x, 218, [(sub, "sans-m")], 18, t["text"], cls="fade", extra=d(dl + 0.2))
        for i, line in enumerate(wrap(body, "sans", 18, colw - 10)):
            s.text(x, 262 + i * 28, [(line, "sans")], 18, t["muted"], cls="fade", extra=d(dl + 0.25))
    return s


# -------------------------------------------------------------------------- stack

def stack(theme):
    W, H = 1200, 500
    s = SVG(W, H, "Toolkit: data, models, language, product", theme)
    t = s.t
    s.panel()
    P, gap = 56, 36
    colw = (W - 2 * P - 3 * gap) / 4
    cols = [
        ("DATA", "Explore", ["Python", "Pandas", "SQL", "EDA", "Feature engineering"]),
        ("MODELS", "Learn", ["Scikit-learn", "PyTorch", "TensorFlow", "Computer vision"]),
        ("LANGUAGE", "Reason", ["Transformers", "Hugging Face", "LangChain", "Vector databases", "RAG pipelines"]),
        ("PRODUCT", "Ship", ["React", "Next.js", "Node.js", "Java", "Gradio", "Flutter"]),
    ]
    ry = 162
    for k, (lab, verb, items) in enumerate(cols):
        x = P + k * (colw + gap)
        dl = 0.1 + k * 0.12
        s.text(x, 76, [(f"0{k+1}", "mono-m", t["accent"]), (f"  {lab}", "mono")], 15, t["muted"], ls=1.6,
               cls="fade", extra=d(dl))
        s.text(x - 2, 136, [(verb, "serif-i" if k == 3 else "serif")], 50, t["text"], cls="rise", extra=d(dl + 0.05))
        hline(s, x, x + colw, ry, t["text"], dl + 0.1)
        for i, it in enumerate(items):
            y = ry + 40 + i * 42
            s.text(x, y, [(it, "sans")], 19, t["text"], cls="fade", extra=d(dl + 0.2 + i * 0.06))
            hline(s, x, x + colw, y + 16, t["line"], dl + 0.25 + i * 0.06)
        if k < 3:
            ax = x + colw + gap / 2
            s.add(f'<path d="M{ax-5} 118l6 6-6 6" stroke="{t["accent"]}" stroke-width="1.6" '
                  f'stroke-linecap="round" stroke-linejoin="round" class="fade" {d(dl+0.3)}/>')
    s.add(f'<circle r="3.5" fill="{t["accent"]}"><animateMotion path="M{P} {ry}H{W-P}" dur="5s" '
          f'repeatCount="indefinite" calcMode="spline" keyTimes="0;1" keySplines=".6 0 .4 1"/></circle>')
    s.text(W - P, H - 34, [("FIG. 02 — FROM RAW DATA TO PRODUCTION INTERFACES", "mono")], 14, t["muted"],
           anchor="end", ls=1.4, cls="fade", extra=d(0.9))
    return s


# -------------------------------------------------------------------------- cards

def glyph_regression(s, ox, oy):
    t = s.t
    s.add(f'<path d="M{ox} {oy}V{oy+130}H{ox+150}" stroke="{t["faint"]}"/>')
    rnd = random.Random(3)
    for k in range(13):
        x = ox + 12 + k * 10.5
        y = oy + 118 - (x - ox) * 0.72 + rnd.gauss(0, 11)
        s.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{t["muted"]}" class="fade" {d(0.3+k*0.05)}/>')
    s.add(f'<path d="M{ox+6} {oy+122}L{ox+148} {oy+18}" stroke="{t["accent"]}" stroke-width="2" '
          f'stroke-linecap="round" pathLength="1" stroke-dasharray="1 1"><animate attributeName="stroke-dashoffset" '
          f'values="1;0;0;-1" keyTimes="0;.35;.75;1" dur="5s" repeatCount="indefinite"/></path>')


def glyph_vision(s, ox, oy):
    t = s.t
    s.add(f'<circle cx="{ox+60}" cy="{oy+78}" r="30" stroke="{t["muted"]}" stroke-width="1.5"/>'
          f'<path d="M{ox+104} {oy+110}l22-40 22 40z" stroke="{t["faint"]}" stroke-width="1.5"/>')
    bx, by, bw, bh, c = ox + 22, oy + 40, 76, 76, 12
    corners = (f"M{bx} {by+c}V{by}H{bx+c}M{bx+bw-c} {by}H{bx+bw}V{by+c}"
               f"M{bx+bw} {by+bh-c}V{by+bh}H{bx+bw-c}M{bx+c} {by+bh}H{bx}V{by+bh-c}")
    s.add(f'<path d="{corners}" stroke="{t["accent"]}" stroke-width="2"><animate attributeName="opacity" '
          f'values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></path>')
    s.text(bx, by - 10, [("word: ball  0.97", "mono")], 12, t["accent"])
    s.add(f'<rect x="{ox}" width="150" height="1.5" fill="{t["accent"]}" opacity=".55">'
          f'<animate attributeName="y" values="{oy+20};{oy+130};{oy+20}" dur="3.6s" repeatCount="indefinite"/></rect>')


def glyph_services(s, ox, oy):
    t = s.t
    nodes = [(ox + 20, oy + 30), (ox + 130, oy + 22), (ox + 75, oy + 78), (ox + 22, oy + 124), (ox + 132, oy + 120)]
    edges = [(0, 2), (1, 2), (2, 3), (2, 4), (0, 1)]
    for a, b in edges:
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        s.add(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{t["faint"]}"/>')
    for k, (a, b) in enumerate(edges[:4]):
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        s.add(f'<circle r="3" fill="{t["accent"]}"><animateMotion path="M{x1} {y1}L{x2} {y2}" dur="2.2s" '
              f'begin="{k*0.55:.2f}s" repeatCount="indefinite"/></circle>')
    for k, (x, y) in enumerate(nodes):
        fill = t["accent"] if k == 2 else t["bg"]
        s.add(f'<rect x="{x-9}" y="{y-9}" width="18" height="18" rx="4" fill="{fill}" stroke="{t["text"] if k != 2 else t["accent"]}" stroke-width="1.5"/>')


def glyph_database(s, ox, oy):
    t = s.t
    for tx, ty in [(ox, oy + 8), (ox + 92, oy + 58)]:
        s.add(f'<rect x="{tx}" y="{ty}" width="58" height="76" rx="5" stroke="{t["muted"]}" stroke-width="1.5"/>'
              f'<path d="M{tx} {ty+18}H{tx+58}" stroke="{t["muted"]}" stroke-width="1.5"/>')
        for r in range(3):
            y = ty + 24 + r * 16
            begin = (r + (1 if tx > ox else 0) * 3) * 0.5
            s.add(f'<rect x="{tx+6}" y="{y}" width="46" height="10" rx="2" fill="{t["accent"]}" fill-opacity=".12">'
                  f'<animate attributeName="fill-opacity" values=".12;.9;.12" dur="3s" begin="{begin:.1f}s" '
                  f'repeatCount="indefinite"/></rect>')
    s.add(f'<path d="M{ox+58} {oy+40}H{ox+75}V{oy+90}H{ox+92}" stroke="{t["accent"]}" stroke-width="1.5"/>'
          f'<path d="M{ox+86} {oy+84}l6 6-6 6" stroke="{t["accent"]}" stroke-width="1.5"/>')


PROJECTS = [
    ("P—01", "MACHINE LEARNING", "Car Price & Titanic Prediction",
     "Supervised learning models with EDA and feature engineering, deployed on Hugging Face.",
     ["Python", "Scikit-learn", "Gradio"], glyph_regression),
    ("P—02", "COMPUTER VISION", "Language Learning App",
     "Cross-platform app using object recognition to make language learning interactive.",
     ["Flutter", "Vision", "AI"], glyph_vision),
    ("P—03", "PLATFORM", "EVT PAY & Paycell Interfaces",
     "Scalable management interfaces and secure payment modules in a microservices architecture.",
     ["React", "REST", "Microservices"], glyph_services),
    ("P—04", "DATA SYSTEMS", "Job Postings DB System",
     "End-to-end database system, from EER modeling to SQL and a Java GUI.",
     ["SQL", "Java", "DB design"], glyph_database),
]


def card(theme, idx):
    num, cat, title, desc, tags, glyph = PROJECTS[idx]
    W, H = 590, 384
    s = SVG(W, H, f"{title}: {desc}", theme)
    t = s.t
    s.panel(20)
    P = 36
    s.text(P, 60, [(num, "mono-m")], 14, t["accent"], ls=1.4, cls="fade")
    s.text(W - P, 60, [(cat, "mono")], 14, t["muted"], anchor="end", ls=1.4, cls="fade")
    hline(s, P, W - P, 82, t["line"], 0.1)
    textw = 330
    y = 136
    for line in wrap(title, "serif", 40, textw):
        s.text(P, y, [(line, "serif")], 40, t["text"], cls="rise", extra=d(0.1))
        y += 42
    y += 10
    for line in wrap(desc, "sans", 17, textw):
        s.text(P, y, [(line, "sans")], 17, t["muted"], cls="fade", extra=d(0.25))
        y += 26
    glyph(s, W - P - 150, 112)
    x, ty = P, H - 58
    for tag in tags:
        tw = measure(tag.upper(), "mono", 12, 1.2) + 26
        s.add(f'<rect x="{x+.5}" y="{ty+.5}" width="{tw-1:.1f}" height="29" rx="14.5" stroke="{t["line"]}" class="fade" {d(0.35)}/>')
        s.text(x + tw / 2, ty + 19.5, [(tag.upper(), "mono")], 12, t["text"], anchor="middle", ls=1.2, cls="fade", extra=d(0.35))
        x += tw + 8
    return s


# ------------------------------------------------------------------------- footer

def footer(theme):
    W, H = 1200, 440
    s = SVG(W, H, "Let's build something intelligent.", theme)
    t = s.t
    s.panel(26)
    P = 56
    s.text(P, 80, [("WHAT’S NEXT", "mono-m")], 15, t["muted"], ls=1.6, cls="fade")
    pulse_dot(s, W - P - 6, 75, t["accent"])
    s.text(P - 4, 218, [("Let’s build something", "serif")], 118, t["text"], cls="rise", extra=d(0.1))
    iw = measure("intelligent", "serif-i", 118)
    s.text(P - 4, 334, [("intelligent", "serif-i")], 118, t["text"], cls="rise", extra=d(0.25))
    s.text(P - 4 + iw + 4, 334, [(".", "serif")], 118, t["accent"], cls="rise", extra=d(0.4))
    hline(s, P, W - P, 374, t["line"], 0.3)
    s.text(P, 408, [("© 2026 RANA SELIM", "mono")], 13, t["muted"], ls=1.4, cls="fade", extra=d(0.6))
    s.text(W - P, 408, [("SET IN INSTRUMENT SERIF, INTER TIGHT & JETBRAINS MONO", "mono")], 13, t["muted"],
           anchor="end", ls=1.4, cls="fade", extra=d(0.6))
    return s


def button(theme, label, primary):
    t = THEMES[theme]
    size, h = 19, 60
    w = round(measure(label, "sans-m", size) + 32 + 34 + 18)
    s = SVG(w, h, label, theme)
    if primary:
        s.add(f'<rect width="{w}" height="{h}" rx="{h/2}" fill="{t["accent"]}"/>')
        fg = t["on_accent"]
    else:
        s.add(f'<rect x=".75" y=".75" width="{w-1.5}" height="{h-1.5}" rx="{(h-1.5)/2}" stroke="{t["text"]}" stroke-width="1.5"/>')
        fg = t["text"]
    s.text(32, h / 2 + 6.5, [(label, "sans-m")], size, fg)
    ax, ay = w - 38, h / 2
    s.add(f'<g stroke="{fg}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
          f'<path d="M{ax-6} {ay+6}L{ax+6} {ay-6}M{ax-3} {ay-6}H{ax+6}V{ay+3}"/>'
          f'<animateTransform attributeName="transform" type="translate" values="0 0;2.5 -2.5;0 0" dur="1.8s" '
          f'repeatCount="indefinite"/></g>')
    return s


# -------------------------------------------------------------------------- build

def main():
    OUT.mkdir(exist_ok=True)
    jobs = {
        "hero": hero,
        "about": lambda th: section(th, "01", [("About", "serif")], "WHO I AM", "01 About"),
        "trajectory": trajectory,
        "toolkit": lambda th: section(th, "02", [("Tool", "serif"), ("kit", "serif-i")], "WHAT I WORK WITH", "02 Toolkit"),
        "stack": stack,
        "work": lambda th: section(th, "03", [("Selected ", "serif"), ("work", "serif-i")], "WHAT I’VE BUILT", "03 Selected work"),
        **{f"project-{i+1}": (lambda th, i=i: card(th, i)) for i in range(len(PROJECTS))},
        "footer": footer,
        "btn-portfolio": lambda th: button(th, "Portfolio", True),
        "btn-linkedin": lambda th: button(th, "LinkedIn", False),
        "btn-email": lambda th: button(th, "Email", False),
    }
    for name, fn in jobs.items():
        for theme in THEMES:
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(fn(theme).render())
            print(f"{path.relative_to(HERE)}  {path.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
