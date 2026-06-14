#!/usr/bin/env python3
"""
Ultra-premium marketing-post composition engine for Think Legal India.

The AI supplies (a) unique copy and (b) a flat illustration; THIS module composes
an agency-grade poster in code so every brand detail is pixel-perfect:
  • depth (gradient ground, soft colour glows, fine grain)
  • mixed typography — Archivo (sans) with a Source-Serif italic accent word + a
    highlighter/underline marker on a key word
  • willow "check" benefit bullets with soft shadows
  • a CUT-OUT illustration that floats and blends into the canvas (no hard box)
  • a gradient CTA pill and the real v2 logo

Post spec (dict) — see SAMPLE at the bottom:
  kicker, headline (list of lines; each line = list of runs {t,f,c,mark}),
  subhook, bullets[], cta, layout (archetype name).

render_post(spec, illustration_path, out_path, layout=None)
"""
import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config as C

# ---------- palette ----------
INK = (55, 55, 31)
INK_SOFT = (84, 84, 58)
CREAM = (234, 239, 189)
CREAM_SOFT = (242, 245, 216)
PAPER = (253, 254, 246)
TEA = (201, 227, 172)
WILLOW = (144, 190, 109)
WILLOW_DEEP = (111, 161, 78)
CARROT = (234, 144, 16)
CARROT_DEEP = (201, 122, 10)
WHITE = (255, 255, 255)
COLORS = {"ink": INK, "ink_soft": INK_SOFT, "carrot": CARROT, "carrot_deep": CARROT_DEEP,
          "willow": WILLOW, "willow_deep": WILLOW_DEEP, "tea": TEA, "paper": PAPER, "white": WHITE}

W, H = C.POST_W, C.POST_H
CREAM_TXT = (240, 244, 208)
MUTED_DK = (196, 201, 165)
_DARK = False
_FC = {}


def col(c):
    if _DARK and c == "ink":
        return CREAM_TXT
    if _DARK and c == "ink_soft":
        return MUTED_DK
    return COLORS.get(c, INK)
VF = {"x": b"ExtraBold", "b": b"Bold", "s": b"SemiBold", "m": b"Medium"}


def font(weight, size):
    k = (weight, size)
    if k not in _FC:
        if weight == "serif":            # Source Serif italic accent
            f = ImageFont.truetype(os.path.join(C.FONT_DIR, "SourceSerif4-400italic.ttf"), size)
        else:
            f = ImageFont.truetype(C.FONT_VF, size)
            try:
                f.set_variation_by_name(VF.get(weight, b"Bold"))
            except Exception:
                pass
        _FC[k] = f
    return _FC[k]


# ---------- depth helpers ----------
def vgrad(w, h, top, bot):
    ramp = np.linspace(0, 1, h).reshape(h, 1, 1)
    arr = (np.array(top).reshape(1, 1, 3) * (1 - ramp) + np.array(bot).reshape(1, 1, 3) * ramp)
    return Image.fromarray(np.repeat(arr.astype(np.uint8), w, axis=1), "RGB").convert("RGBA")


def glow(base, cx, cy, r, color, alpha):
    g = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    base.alpha_composite(g.filter(ImageFilter.GaussianBlur(r * 0.55)))


def grain(base, amt=7):
    n = (np.random.rand(base.height, base.width, 1) - 0.5) * 2 * amt
    arr = np.array(base.convert("RGB")).astype(np.int16) + n.astype(np.int16)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def shadow(base, box, radius, blur=26, alpha=55, dy=14, color=(31, 31, 17)):
    x0, y0, x1, y1 = box
    pad = blur * 3
    s = Image.new("RGBA", (int(x1 - x0 + pad * 2), int(y1 - y0 + pad * 2)), (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle([pad, pad, pad + (x1 - x0), pad + (y1 - y0)],
                                        radius=radius, fill=color + (alpha,))
    base.alpha_composite(s.filter(ImageFilter.GaussianBlur(blur)), (int(x0 - pad), int(y0 - pad + dy)))


def cutout(path):
    """Remove the flat border background of a Recraft illustration (flood-fill from
    corners → transparent) so the subject floats. Falls back to as-is if not flat."""
    im = Image.open(path).convert("RGB")
    corners = [im.getpixel((1, 1)), im.getpixel((im.width - 2, 1)),
               im.getpixel((1, im.height - 2)), im.getpixel((im.width - 2, im.height - 2))]
    arr0 = np.array(corners)
    if arr0.std(0).mean() > 14:                      # corners not uniform → no clean bg
        return Image.open(path).convert("RGBA"), False
    work = im.copy()
    SENT = (255, 0, 255)
    for c in [(0, 0), (work.width - 1, 0), (0, work.height - 1), (work.width - 1, work.height - 1)]:
        ImageDraw.floodfill(work, c, SENT, thresh=42)
    a = np.array(work)
    mask = ~((a[:, :, 0] == 255) & (a[:, :, 1] == 0) & (a[:, :, 2] == 255))
    out = np.dstack([np.array(im), (mask * 255).astype(np.uint8)])
    rgba = Image.fromarray(out, "RGBA")
    # feather the alpha a touch for clean edges
    alpha = rgba.split()[-1].filter(ImageFilter.GaussianBlur(1.2))
    rgba.putalpha(alpha)
    return rgba, True


def place_illustration(base, path, cx, cy, target_w, drop=True):
    """Place a cut-out illustration centered at (cx, bottom=cy-ish) with a soft shadow."""
    im, cut = cutout(path)
    scale = target_w / im.width
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    x = int(cx - im.width / 2)
    y = int(cy - im.height)
    if drop:
        sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
        sil = Image.new("RGBA", im.size, (31, 31, 17, 90))
        sh.paste(sil, (x + 8, y + 20), im)
        base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    base.alpha_composite(im, (x, y))
    return im.height


# ---------- type helpers ----------
def _f(run, size):
    return font("serif", size) if run.get("f") == "serif" else font(run.get("f", "x"), size)


def runs_width(d, runs, size):
    return sum(d.textlength(r["t"], font=_f(r, size)) for r in runs)


def draw_line(img, d, x, y, runs, size, align="left", maxw=None):
    total = runs_width(d, runs, size)
    if align == "center" and maxw:
        x = x + (maxw - total) / 2
    cx = x
    for r in runs:
        f = _f(r, size)
        w = d.textlength(r["t"], font=f)
        if r.get("mark") == "hl":      # highlighter block behind the word
            asc, desc = f.getmetrics()
            pad = size * 0.10
            box = [cx - pad, y + size * 0.18, cx + w + pad, y + size * 0.96]
            hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(hl).rounded_rectangle(box, radius=int(size * 0.16),
                                                 fill=CARROT + (255,))
            img.alpha_composite(hl)
            d.text((cx, y), r["t"], font=f, fill=WHITE)
        elif r.get("mark") == "ul":    # underline swash (rounded caps)
            d.text((cx, y), r["t"], font=f, fill=col(r.get("c", "ink")))
            uy = y + size * 1.0
            tw = max(6, int(size * 0.08))
            d.line([(cx + tw / 2, uy), (cx + w - tw / 2, uy)], fill=CARROT, width=tw, joint="curve")
            d.ellipse([cx, uy - tw / 2, cx + tw, uy + tw / 2], fill=CARROT)
            d.ellipse([cx + w - tw, uy - tw / 2, cx + w, uy + tw / 2], fill=CARROT)
        else:
            d.text((cx, y), r["t"], font=f, fill=col(r.get("c", "ink")))
        cx += w
    return cx - x


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def tracked(d, xy, s, f, fill, tr=2):
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tr
    return x - xy[0]


def check_disc(img, cx, cy, r):
    """Willow gradient disc + white check, soft shadow."""
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - r, cy - r + 4, cx + r, cy + r + 4], fill=(111, 161, 78, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    disc = Image.new("RGBA", (r * 2 + 4, r * 2 + 4), (0, 0, 0, 0))
    dd = ImageDraw.Draw(disc)
    for i in range(r, 0, -1):                       # cheap radial: willow→willow_deep
        t = i / r
        col = tuple(int(WILLOW_DEEP[k] * (1 - t) + WILLOW[k] * t) for k in range(3))
        dd.ellipse([r - i + 2, r - i + 2, r + i + 2, r + i + 2], fill=col + (255,))
    img.alpha_composite(disc, (cx - r - 2, cy - r - 2))
    d = ImageDraw.Draw(img)
    s = r
    d.line([(cx - .42 * s, cy + .02 * s), (cx - .10 * s, cy + .32 * s),
            (cx + .44 * s, cy - .30 * s)], fill=WHITE, width=max(4, int(r * .30)), joint="curve")


def gradient_pill(img, box, c1, c2, radius):
    x0, y0, x1, y1 = box
    g = vgrad(int(x1 - x0), int(y1 - y0), c1, c2).convert("RGBA")
    mask = Image.new("L", g.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, g.size[0] - 1, g.size[1] - 1], radius=radius, fill=255)
    img.paste(g, (int(x0), int(y0)), mask)


def logo_lockup(img, x, y, h=58, wordmark=True, dark=False):
    d = ImageDraw.Draw(img)
    if dark:                                   # paper chip so the ink icon reads on dark
        pad = int(h * 0.14)
        shadow(img, [x - pad, y - pad, x + h + pad, y + h + pad], int(h * 0.28),
               blur=14, alpha=70, dy=6)
        d.rounded_rectangle([x - pad, y - pad, x + h + pad, y + h + pad],
                            radius=int(h * 0.28), fill=PAPER)
    logo = Image.open(C.LOGO_SVG.replace(".svg", "-512.png")).convert("RGBA").resize((h, h), Image.LANCZOS)
    img.alpha_composite(logo, (int(x), int(y)))
    if wordmark:
        name_c = (238, 242, 205) if dark else INK
        site_c = (181, 209, 140) if dark else WILLOW_DEEP
        wf = font("x", int(h * 0.5))
        tx = x + h + 16
        d.text((tx, y + h * 0.04), "Think Legal ", font=wf, fill=name_c)
        adv = d.textlength("Think Legal ", font=wf)
        d.text((tx + adv, y + h * 0.04), "India", font=wf, fill=CARROT)
        d.text((tx, y + h * 0.58), C.WEBSITE, font=font("s", int(h * 0.31)), fill=site_c)


# ---------- archetype: editorial hero ----------
def editorial_hero(spec, illustration_path, accent):
    img = vgrad(W, H, CREAM_SOFT, CREAM)
    glow(img, W * 0.82, H * 0.12, 460, TEA, 90)
    glow(img, W * 0.15, H * 0.42, 380, accent, 40)
    d = ImageDraw.Draw(img)
    M = 92
    y = M + 8

    # logo top-right
    logo_lockup(img, W - M - 250, M - 6, h=54)

    # kicker pill (paper, shadow, willow dot)
    kick = spec.get("kicker", "").upper()
    if kick:
        kf = font("b", 24)
        tw = sum(d.textlength(c, font=kf) + 3 for c in kick)
        pw, ph = int(tw) + 92, 58
        shadow(img, [M, y, M + pw, y + ph], 29, blur=16, alpha=34, dy=7)
        d.rounded_rectangle([M, y, M + pw, y + ph], radius=29, fill=PAPER)
        d.ellipse([M + 26, y + ph / 2 - 7, M + 40, y + ph / 2 + 7], fill=WILLOW)
        tracked(d, (M + 52, y + ph / 2 - 15), kick, kf, INK, tr=3)
        y += ph + 40

    # headline (mixed fonts + marker)
    for line in spec["headline"]:
        size = line.get("size", 92)
        draw_line(img, d, M, y, line["runs"], size)
        y += int(size * 1.02)
    y += 22

    # subhook (serif italic)
    sub = spec.get("subhook")
    if sub:
        sf = font("serif", 35)
        for ln in wrap(d, sub, sf, W - 2 * M):
            d.text((M, y), ln, font=sf, fill=INK_SOFT); y += 48
        y += 24

    # bullets
    bf = font("s", 32)
    for b in spec.get("bullets", []):
        check_disc(img, M + 22, y + 22, 22)
        for i, ln in enumerate(wrap(d, b, bf, W - 2 * M - 86)):
            d.text((M + 70, y + (3 if i == 0 else 0)), ln, font=bf, fill=INK); y += 44
        y += 18

    # CTA pill (gradient carrot)
    cta = spec.get("cta")
    if cta:
        y += 8
        cf = font("b", 31)
        cw = int(d.textlength(cta, font=cf)) + 78
        ch = 72
        shadow(img, [M, y, M + cw, y + ch], 36, blur=20, alpha=70, dy=10, color=CARROT_DEEP)
        gradient_pill(img, [M, y, M + cw, y + ch], CARROT, CARROT_DEEP, 36)
        bb = d.textbbox((0, 0), cta, font=cf)
        d.text((M + 39, y + (ch - (bb[3] - bb[1])) / 2 - bb[1]), cta, font=cf, fill=WHITE)
        y += ch + 24

    # illustration — floats, blended, bleeds off bottom, centered in the lower band
    if illustration_path and os.path.exists(illustration_path):
        glow(img, W * 0.5, H * 0.88, 400, accent, 64)
        place_illustration(img, illustration_path, cx=W * 0.5, cy=H + 48, target_w=int(W * 0.72))

    return grain(img).convert("RGB")


# ---------- premium surfaces ----------
def glass_panel(base, box, radius=42, tint=WHITE, alpha=44, border_alpha=80, blur=20):
    x0, y0, x1, y1 = [int(v) for v in box]
    shadow(base, box, radius, blur=34, alpha=80, dy=18)
    region = base.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(blur)).convert("RGBA")
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, tint + (alpha,)))
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, region.size[0] - 1, region.size[1] - 1],
                                           radius=radius, fill=255)
    base.paste(region, (x0, y0), mask)
    bd = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(bd).rounded_rectangle([x0, y0, x1, y1], radius=radius,
                                         outline=tint + (border_alpha,), width=2)
    base.alpha_composite(bd)


def mesh(dark):
    if dark:
        base = vgrad(W, H, (46, 46, 28), (27, 27, 16))
        glow(base, W * 0.18, H * 0.10, 540, CARROT, 50)
        glow(base, W * 0.88, H * 0.30, 480, WILLOW, 42)
        glow(base, W * 0.55, H * 0.74, 620, TEA, 26)
    else:
        base = vgrad(W, H, CREAM_SOFT, CREAM)
        glow(base, W * 0.85, H * 0.10, 470, TEA, 95)
        glow(base, W * 0.12, H * 0.42, 410, WILLOW, 42)
        glow(base, W * 0.62, H * 0.86, 430, CARROT, 40)
    return base


def draw_content(img, M, top, content_w, spec, sub_color):
    """Shared block: kicker → headline → subhook → bullets → CTA. Returns final y."""
    d = ImageDraw.Draw(img)
    y = top
    kick = spec.get("kicker", "").upper()
    if kick:
        kf = font("b", 24)
        tw = sum(d.textlength(c, font=kf) + 3 for c in kick)
        pw, ph = int(tw) + 92, 58
        if _DARK:
            glass_panel(img, [M, y, M + pw, y + ph], radius=29, tint=WHITE, alpha=30,
                        border_alpha=70, blur=14)
            kt = CREAM_TXT
        else:
            shadow(img, [M, y, M + pw, y + ph], 29, blur=16, alpha=34, dy=7)
            d.rounded_rectangle([M, y, M + pw, y + ph], radius=29, fill=PAPER)
            kt = INK
        d.ellipse([M + 26, y + ph / 2 - 7, M + 40, y + ph / 2 + 7], fill=WILLOW)
        tracked(d, (M + 52, y + ph / 2 - 15), kick, kf, kt, tr=3)
        y += ph + 40
    # auto-fit the headline to the column so long lines never overflow
    hl = spec["headline"]
    maxw = max((runs_width(d, ln["runs"], ln.get("size", 90)) for ln in hl), default=1)
    scale = min(content_w / maxw, 1.0) if maxw else 1.0
    for line in hl:
        size = max(40, int(line.get("size", 90) * scale))
        draw_line(img, d, M, y, line["runs"], size)
        y += int(size * 1.04)
    y += 22
    sub = spec.get("subhook")
    if sub:
        sf = font("serif", 35)
        for ln in wrap(d, sub, sf, content_w):
            d.text((M, y), ln, font=sf, fill=sub_color); y += 48
        y += 24
    bf = font("s", 32)
    for b in spec.get("bullets", []):
        check_disc(img, M + 22, y + 22, 22)
        for i, ln in enumerate(wrap(d, b, bf, content_w - 86)):
            d.text((M + 70, y + (3 if i == 0 else 0)), ln, font=bf, fill=col("ink")); y += 44
        y += 18
    cta = spec.get("cta")
    if cta:
        y += 8
        cf = font("b", 31)
        cw = int(d.textlength(cta, font=cf)) + 78
        ch = 72
        shadow(img, [M, y, M + cw, y + ch], 36, blur=20, alpha=80, dy=10, color=CARROT_DEEP)
        gradient_pill(img, [M, y, M + cw, y + ch], CARROT, CARROT_DEEP, 36)
        bb = d.textbbox((0, 0), cta, font=cf)
        d.text((M + 39, y + (ch - (bb[3] - bb[1])) / 2 - bb[1]), cta, font=cf, fill=WHITE)
        y += ch + 24
    return y


def dark_hero_bottom(spec, illustration_path, accent):
    """Dark Luxe — text up top, glowing hero illustration centered along the bottom."""
    global _DARK
    _DARK = True
    img = mesh(dark=True)
    logo_lockup(img, W - 92 - 250, 86, h=54, dark=True)
    if illustration_path and os.path.exists(illustration_path):
        glow(img, W * 0.5, H * 0.9, 470, accent, 150)
        glow(img, W * 0.5, H * 0.9, 300, WHITE, 36)
        place_illustration(img, illustration_path, cx=W * 0.5, cy=H + 52,
                           target_w=int(W * 0.72), drop=False)
    draw_content(img, 92, 100, W - 184, spec, MUTED_DK)
    out = grain(img, 5).convert("RGB")
    _DARK = False
    return out


def dark_split(spec, illustration_path, accent):
    """Dark Luxe — text in a left column, glowing illustration on the right, bleeding off-edge."""
    global _DARK
    _DARK = True
    img = mesh(dark=True)
    logo_lockup(img, 92, 86, h=54, dark=True)
    if illustration_path and os.path.exists(illustration_path):
        glow(img, W * 0.82, H * 0.60, 430, accent, 150)
        glow(img, W * 0.82, H * 0.60, 270, WHITE, 34)
        place_illustration(img, illustration_path, cx=W * 0.83, cy=H * 0.74,
                           target_w=int(W * 0.52), drop=False)
    draw_content(img, 92, 184, int(W * 0.58), spec, MUTED_DK)
    out = grain(img, 5).convert("RGB")
    _DARK = False
    return out


def light_glass(spec, illustration_path, accent):
    global _DARK
    _DARK = False
    img = mesh(dark=False)
    # frosted glass card holds the content
    card = [56, 150, W - 56, H - 56]
    glass_panel(img, card, radius=48, tint=WHITE, alpha=150, border_alpha=120, blur=22)
    logo_lockup(img, 92, 80, h=52)
    if illustration_path and os.path.exists(illustration_path):
        glow(img, W * 0.5, H * 0.92, 360, accent, 70)
        place_illustration(img, illustration_path, cx=W * 0.5, cy=H - 60, target_w=int(W * 0.62))
    draw_content(img, 104, 200, W - 208, spec, INK_SOFT)
    return grain(img).convert("RGB")


ARCHETYPES = {"dark-hero-bottom": dark_hero_bottom, "dark-split": dark_split,
              "light-glass": light_glass, "editorial-hero": editorial_hero}


def render_post(spec, illustration_path=None, out_path=None, layout=None):
    layout = layout or spec.get("layout") or "dark-hero-bottom"
    fn = ARCHETYPES.get(layout, dark_hero_bottom)
    accent = COLORS.get(spec.get("accent", "willow"), WILLOW)
    img = fn(spec, illustration_path, accent)
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path, quality=95)
    return out_path


SAMPLE = {
    "kicker": "Company Registration",
    "accent": "carrot",
    "headline": [
        {"runs": [{"t": "Your savings", "f": "x", "c": "ink"}], "size": 90},
        {"runs": [{"t": "aren’t a ", "f": "x", "c": "ink"},
                  {"t": "safety net", "f": "serif", "c": "carrot", "mark": "ul"}], "size": 90},
    ],
    "subhook": "Run it as “just yourself” and a single client dispute reaches your personal assets.",
    "bullets": [
        "Limited liability — your home & savings stay yours",
        "Investors & big clients only sign with registered entities",
        "Signed off by partner CAs & Company Secretaries",
    ],
    "cta": "Register right → thinklegalindia.co",
}

if __name__ == "__main__":
    ill = os.path.join(C.OUT_DIR, "pvt-ltd-registration_illustration.png")
    ill = ill if os.path.exists(ill) else None
    for layout in ("dark-luxe", "light-glass", "editorial-hero"):
        render_post(SAMPLE, illustration_path=ill,
                    out_path=os.path.join(C.OUT_DIR, f"premium_{layout}.png"), layout=layout)
        print(f"OK -> outputs/premium_{layout}.png")
