#!/usr/bin/env python3
"""
Generate the ILLUSTRATION for a Think Legal India post via OpenRouter
(Recraft V4.1 utility — raster, validated 13 Jun 2026).

Important: this produces ONLY a clean illustration with NO text. All marketing
copy, hierarchy, bullets and the logo are composited later by design.py with
exact brand fonts/colours — AI text can't be trusted for brand-perfect output.

    from generate_image import generate_illustration
    generate_illustration("a Pvt Ltd certificate with an approval seal ...",
                          "outputs/post1.png")
"""
import os
import re
import json
import base64
import requests
from PIL import Image

import config as C

URL = "https://openrouter.ai/api/v1/chat/completions"

STYLE = (
    "Clean modern flat-design vector illustration, contemporary fintech / SaaS "
    "marketing style. Bold simple geometric shapes, soft rounded corners, subtle "
    "long shadows, flat colour fills, crisp and minimal. A single clear focal "
    "subject, centered, well-composed with comfortable padding around it. "
)
PALETTE = (
    "Strict colour palette: dark khaki ink (#37371F) for primary shapes and "
    "outlines, carrot-orange (#EA9010) as the main accent, willow-green (#90BE6D) "
    "for checkmarks / approval / positive elements, soft tea-green (#C9E3AC) for "
    "secondary fills, on a near-white paper (#FDFEF6) background. "
)
CONSTRAINTS = (
    "Absolutely NO text, NO letters, NO numbers, NO words, NO labels anywhere. "
    "No photorealistic human faces (simple flat stylized figures only). "
    "No logos, no watermarks, no UI chrome, no borders, no clutter. "
    "Plain solid paper-coloured background."
)


def build_prompt(brief: str) -> str:
    return f"{STYLE}Subject: {brief.strip().rstrip('.')}. {PALETTE}{CONSTRAINTS}"


def _call(model, prompt, timeout):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image"],
        "image_config": {
            "aspect_ratio": "1:1",
            "rgb_colors": C.SOCIAL_RGB_COLORS,
            "background_rgb_color": C.PAPER,
        },
    }
    headers = {"Authorization": f"Bearer {C.require('OPENROUTER_API_KEY')}",
               "Content-Type": "application/json"}
    r = requests.post(URL, headers=headers, json=payload, timeout=timeout)
    return r


def generate_illustration(brief: str, out_path: str, *, timeout: int = 180) -> str:
    """Generate a clean no-text illustration; returns a PNG path on PAPER bg."""
    prompt = build_prompt(brief)
    r = _call(C.IMAGE_MODEL, prompt, timeout)
    if r.status_code != 200:
        # one retry on the fallback model
        r = _call(C.IMAGE_MODEL_FALLBACK, prompt, timeout)
        if r.status_code != 200:
            raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    images = (data.get("choices", [{}])[0].get("message", {}) or {}).get("images") or []
    if not images:
        raise RuntimeError(f"No image returned: {json.dumps(data)[:500]}")
    url = images[0]["image_url"]["url"]
    m = re.match(r"data:image/([\w+]+);base64,(.*)", url, re.S)
    if not m:
        raise RuntimeError(f"Unexpected image url: {url[:120]}")
    subtype, b64 = m.groups()
    raw = base64.b64decode(b64)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if "svg" in subtype:  # fallback vector model — rasterize via rsvg-convert
        svg_path = out_path + ".svg"
        with open(svg_path, "wb") as f:
            f.write(raw)
        os.system(f'rsvg-convert -w 1200 "{svg_path}" -o "{out_path}"')
    else:
        tmp = out_path + f".{ 'jpg' if 'jpeg' in subtype else subtype }"
        with open(tmp, "wb") as f:
            f.write(raw)
        Image.open(tmp).convert("RGB").save(out_path)
        if tmp != out_path:
            os.remove(tmp)
    return out_path


if __name__ == "__main__":
    out = os.path.join(C.OUT_DIR, "illus_test.png")
    generate_illustration(
        "an official company-incorporation certificate with a willow-green approval "
        "seal and ribbon, a small upward growth bar chart beside it, and a tiny "
        "storefront — symbolising a newly registered Indian business",
        out)
    print(f"OK -> {out}")
