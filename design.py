#!/usr/bin/env python3
"""
High-end marketing-post composition engine for Think Legal India.

The AI model supplies only an illustration; THIS module lays out every text
element with pixel-perfect brand typography and colour so each post is on-brand
and consistent: a kicker tag, a multi-weight/colour "hook" title, a serif
sub-hook, willow-check benefit bullets, a carrot CTA pill, the AI illustration,
and a footer carrying our real v2 logo + website.

Render one post:
    from design import render_post
    render_post(post_dict, illustration_path="outputs/x.png", out_path="outputs/x_final.png")
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config as C

# ---- palette (RGB) --------------------------------------------------------
INK = tuple(C.INK)
CREAM = tuple(C.CREAM)
CREAM_SOFT = tuple(C.CREAM_SOFT)
PAPER = tuple(C.PAPER)
TEA = tuple(C.TEA)
WILLOW = tuple(C.WILLOW)
WILLOW_DEEP = (111, 161, 78)     # #6FA14E
CARROT = tuple(C.CARROT)
CARROT_DEEP = (201, 122, 10)     # #C97A0A

COLORS = {
    "ink": INK, "carrot": CARROT, "carrot_deep": CARROT_DEEP,
    "willow": WILLOW, "willow_deep": WILLOW_DEEP, "tea": TEA,
    "paper": PAPER, "cream": CREAM, "white": (255, 255, 255),
}
VF_INSTANCE = {"x": b"ExtraBold", "b": b"Bold", "s": b"SemiBold"}

W, H = C.POST_W, C.POST_H
MARGIN = 76                       # outer content margin
_FONT_CACHE = {}


def font(weight: str, size: int):
    """Archivo at the given weight (x=ExtraBold, b=Bold, s=SemiBold) from the
    variable font, so every glyph — including ₹ — is available."""
    key = (weight, size)
    if key not in _FONT_CACHE:
        f = ImageFont.truetype(C.FONT_VF, size)
        try:
            f.set_variation_by_name(VF_INSTANCE.get(weight, b"Bold"))
        except Exception:
            pass
        _FONT_CACHE[key] = f
    return _FONT_CACHE[key]


def serif(size: int, italic=True):
    key = ("serif-i" if italic else "serif", size)
    if key not in _FONT_CACHE:
        p = os.path.join(C.FONT_DIR, "SourceSerif4-400italic.ttf" if italic
                         else "SourceSerif4-600.ttf")
        _FONT_CACHE[key] = ImageFont.truetype(p, size)
    return _FONT_CACHE[key]


# ---- low-level helpers ----------------------------------------------------
def _text_size(draw, s, fnt):
    if not s:
        return 0, 0
    b = draw.textbbox((0, 0), s, font=fnt)
    return b[2] - b[0], b[3] - b[1]


def rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def soft_shadow(base, box, radius, blur=22, alpha=46, dy=12):
    """Paste a blurred dark shadow under a rounded box onto base (RGBA)."""
    x0, y0, x1, y1 = box
    pad = blur * 3
    sh = Image.new("RGBA", (int(x1 - x0 + pad * 2), int(y1 - y0 + pad * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.rounded_rectangle([pad, pad, pad + (x1 - x0), pad + (y1 - y0)],
                        radius=radius, fill=(31, 31, 17, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(sh, (int(x0 - pad), int(y0 - pad + dy)))


def draw_tracked(draw, xy, s, fnt, fill, tracking=2):
    """Draw text with letter-spacing (tracking px between chars). Returns width."""
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x - xy[0] - (tracking if s else 0)


def runs_width(draw, runs, size):
    return sum(draw.textlength(r["t"], font=font(r.get("w", "x"), size)) for r in runs)


def draw_runs(draw, x, y, runs, size, ascent_ref="x"):
    """Draw inline styled runs left→right at baseline-aligned top y. Returns x-end."""
    cx = x
    for r in runs:
        f = font(r.get("w", "x"), size)
        draw.text((cx, y), r["t"], font=f, fill=COLORS.get(r.get("c", "ink"), INK))
        cx += draw.textlength(r["t"], font=f)
    return cx


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_check(draw, cx, cy, r, ring=WILLOW, tick=PAPER):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ring)
    # checkmark
    s = r
    pts = [(cx - 0.42 * s, cy + 0.02 * s),
           (cx - 0.12 * s, cy + 0.34 * s),
           (cx + 0.46 * s, cy - 0.34 * s)]
    draw.line(pts, fill=tick, width=max(3, int(r * 0.28)), joint="curve")


def brand_texture(img, box, alpha=11):
    """Faint ink '+ and dot' brand texture confined to an empty rectangle so it
    never crosses body text. Used in the flanks beside the illustration tile."""
    bx0, by0, bx1, by1 = box
    if bx1 - bx0 < 40 or by1 - by0 < 40:
        return
    d = ImageDraw.Draw(img, "RGBA")
    step = 80
    col = (55, 55, 31, alpha)
    row = 0
    for gy in range(int(by0) + 18, int(by1) - 6, step):
        off = (step // 2) if row % 2 else 0
        for gx in range(int(bx0) + 16 + off, int(bx1) - 10, step):
            d.line([(gx - 5, gy), (gx + 5, gy)], fill=col, width=2)
            d.line([(gx, gy - 5), (gx, gy + 5)], fill=col, width=2)
        row += 1


def fit_illustration(ill_path, box_w, box_h):
    im = Image.open(ill_path).convert("RGBA")
    scale = min(box_w / im.width, box_h / im.height)
    return im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                     Image.LANCZOS)


# ---- main ---------------------------------------------------------------
def render_post(post, illustration_path=None, out_path=None, layout=None, **_kw):
    # Compatibility shim: the pipeline feeds the AI-written creative spec, which calls
    # the hook lines "headline" (and passes a Dark-Luxe "layout" we ignore here — this
    # is the original cream-background brand design). Map it to this engine's fields.
    post = dict(post)
    post.setdefault("title_lines", post.get("headline", []))

    img = Image.new("RGBA", (W, H), CREAM + (255,))
    draw = ImageDraw.Draw(img)

    x0 = MARGIN
    x1 = W - MARGIN
    content_w = x1 - x0
    y = MARGIN

    # --- kicker pill ---
    kicker = post.get("kicker", "").upper()
    if kicker:
        kf = font("b", 25)
        tw = sum(draw.textlength(c, font=kf) + 3 for c in kicker)
        ph, pw = 56, int(tw) + 56
        rounded(draw, [x0, y, x0 + pw, y + ph], radius=ph // 2, fill=TEA)
        draw_tracked(draw, (x0 + 28, y + (ph - 25) // 2 - 4), kicker, kf, INK, tracking=3)
        y += ph + 30

    # --- title (hook) : list of lines, each {runs, size} ---
    for line in post.get("title_lines", []):
        size = line.get("size", 88)
        draw_runs(draw, x0, y, line["runs"], size)
        y += int(size * 1.04)
    y += 24

    # --- sub-hook (serif italic) ---
    sub = post.get("subhook")
    if sub:
        sf = serif(33, italic=True)
        for ln in wrap(draw, sub, sf, content_w):
            draw.text((x0, y), ln, font=sf, fill=INK)
            y += 46
        y += 30

    # --- bullets ---
    bullets = post.get("bullets", [])
    bf = font("s", 31)
    rcheck = 21
    for b in bullets:
        lines = wrap(draw, b, bf, content_w - (rcheck * 2 + 22))
        draw_check(draw, x0 + rcheck, y + 20, rcheck)
        tx = x0 + rcheck * 2 + 22
        for i, ln in enumerate(lines):
            draw.text((tx, y + (4 if len(lines) == 1 else 0)), ln, font=bf, fill=INK)
            y += 42
        y += 18
    if bullets:
        y += 6

    # --- CTA pill (carrot) ---
    cta = post.get("cta")
    cta_h = 0
    if cta:
        cf = font("b", 30)
        cw = int(draw.textlength(cta, font=cf)) + 64
        cta_h = 64
        rounded(draw, [x0, y, x0 + cw, y + cta_h], radius=cta_h // 2, fill=CARROT)
        draw.text((x0 + 32, y + (cta_h - 30) // 2 - 4), cta, font=cf, fill=(255, 255, 255))
        y += cta_h + 30

    # --- footer geometry (pinned to bottom) ---
    footer_h = 92
    footer_top = H - MARGIN - footer_h

    # --- illustration area: centered square paper tile (art floats seamlessly) ---
    ill_top = y
    ill_bottom = footer_top - 24
    avail_h = ill_bottom - ill_top
    if illustration_path and avail_h > 170:
        panel = min(avail_h, content_w)            # square, hugs the art
        cx0 = (W - panel) // 2
        cy0 = ill_top + (avail_h - panel) // 2
        cb = [cx0, cy0, cx0 + panel, cy0 + panel]
        # subtle brand texture in the empty flanks beside the tile
        brand_texture(img, [x0, cy0, cx0 - 22, cy0 + panel])
        brand_texture(img, [cx0 + panel + 22, cy0, x1, cy0 + panel])
        soft_shadow(img, cb, radius=36)
        rounded(draw, cb, radius=36, fill=PAPER)
        pad = 30
        im = fit_illustration(illustration_path, panel - pad * 2, panel - pad * 2)
        img.alpha_composite(im, (cx0 + (panel - im.width) // 2,
                                 cy0 + (panel - im.height) // 2))

    # --- footer: divider + logo lockup (left) + website (right) ---
    draw.line([(x0, footer_top - 2), (x1, footer_top - 2)], fill=TEA, width=3)
    fy = footer_top + 14
    logo = Image.open(C.LOGO_SVG.replace(".svg", "-512.png") if os.path.exists(
        C.LOGO_SVG.replace(".svg", "-512.png")) else C.LOGO_SVG).convert("RGBA")
    lh = 64
    logo = logo.resize((lh, lh), Image.LANCZOS)
    img.alpha_composite(logo, (x0, fy))
    wf = font("x", 34)
    wx = x0 + lh + 18
    draw.text((wx, fy + 4), "Think Legal ", font=wf, fill=INK)
    wadv = draw.textlength("Think Legal ", font=wf)
    draw.text((wx + wadv, fy + 4), "India", font=wf, fill=CARROT)
    draw.text((wx, fy + 42), C.WEBSITE, font=font("s", 24), fill=WILLOW_DEEP)

    # right side: tagline chip
    tag = "Start Right. Stay Compliant."
    tf = font("s", 25)
    tw = draw.textlength(tag, font=tf)
    draw.text((x1 - tw, fy + 20), tag, font=tf, fill=INK)

    out = img.convert("RGB")
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        out.save(out_path, quality=95)
    return out_path


if __name__ == "__main__":
    sample = {
        "kicker": "Company Registration",
        "title_lines": [
            {"runs": [{"t": "Register your", "w": "s", "c": "ink"}], "size": 52},
            {"runs": [{"t": "Pvt Ltd", "w": "x", "c": "carrot"},
                      {"t": " Company", "w": "x", "c": "ink"}], "size": 92},
        ],
        "subhook": "All-inclusive pricing, real CAs, and a status you can actually track.",
        "bullets": [
            "Transparent all-in price — no hidden govt-fee surprises",
            "Incorporated in 7–10 working days",
            "Signed off by partner CAs & Company Secretaries",
        ],
        "cta": "DM “START” to begin",
    }
    ill = os.path.join(C.OUT_DIR, "test_utility_text.webp")
    ill = ill if os.path.exists(ill) else None
    render_post(sample, illustration_path=ill,
                out_path=os.path.join(C.OUT_DIR, "design_sample.png"))
    print("OK -> outputs/design_sample.png")
