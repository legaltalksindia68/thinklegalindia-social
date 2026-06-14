#!/usr/bin/env python3
"""
One-time image-model bake-off. Generates the SAME two full-poster briefs across
several OpenRouter image models so we can compare which produces the most
attractive, on-brand, correctly-spelled marketing posters with text + design.

Output: outputs/bakeoff/<model>__<brief>.png   (+ a console summary)

Run:  python3 bakeoff.py
"""
import os
import re
import json
import base64
import concurrent.futures
import requests
from PIL import Image

import config as C

URL = "https://openrouter.ai/api/v1/chat/completions"
OUT = os.path.join(C.OUT_DIR, "bakeoff")

# Candidate models (output an image). Recraft uses image_config; the others ignore it.
MODELS = [
    "google/gemini-3-pro-image-preview",
    "openai/gpt-5-image",
    "google/gemini-2.5-flash-image",
    "recraft/recraft-v4.1-utility",
]

# Brand bible inlined here for the bake-off (moves to brand.py in the real build).
BRAND = (
    "Brand: Think Legal India — modern Indian company-registration & tax-compliance service. "
    "Strict colour palette: warm cream background #EAEFBD, near-white paper panels #FDFEF6, "
    "dark-khaki ink #37371F for text/shapes, carrot-orange #EA9010 as the primary accent, "
    "willow-green #90BE6D for ticks/positive, soft tea-green #C9E3AC for secondary fills. "
    "Aesthetic: clean modern fintech/SaaS marketing, flat geometric shapes, soft rounded "
    "corners, confident and trustworthy, generous whitespace. Portrait 4:5 (1080x1350). "
    "Leave the bottom-left corner relatively clean for a small logo. Spelling MUST be perfect; "
    "render ONLY the exact text specified, no other words, no lorem ipsum, no gibberish."
)

BRIEFS = {
    "company-danger": (
        "Layout archetype: BOLD TYPOGRAPHIC poster — the headline is the hero, huge and "
        "confident, with one supporting line and a small CTA. Minimal flat illustration of a "
        "lone founder figure standing on a cracking glass floor, with a protective rounded "
        "shield + checkmark motif. "
        "Render EXACTLY this text and nothing else:\n"
        "  HEADLINE: \"Your savings aren't a safety net\"\n"
        "  SUBLINE: \"No registered company = your personal assets are on the line\"\n"
        "  CTA PILL: \"Register right → thinklegalindia.co\""
    ),
    "gst-deadline": (
        "Layout archetype: EDITORIAL DATA-CARD — a clean dated card with a bold date motif, a "
        "calendar/clock element, and a willow-green checkmark. Calm, not alarming. "
        "Render EXACTLY this text and nothing else:\n"
        "  KICKER: \"GST DEADLINE\"\n"
        "  HEADLINE: \"GSTR-3B is due the 20th\"\n"
        "  BULLET: \"Miss it: Rs.50/day + 18% interest\"\n"
        "  CTA: \"DM 'FILE' to never miss one\""
    ),
}


def build_prompt(brief_body):
    return (f"Design a single polished social-media marketing POSTER. {BRAND}\n\n{brief_body}\n\n"
            "Make it genuinely attractive and scroll-stopping, professionally laid out, "
            "high visual hierarchy. Output one image.")


def extract_image(data):
    """Pull a base64 image out of an OpenRouter chat-completion response."""
    msg = (data.get("choices", [{}])[0].get("message", {}) or {})
    imgs = msg.get("images") or []
    if imgs:
        u = imgs[0].get("image_url", {})
        u = u.get("url") if isinstance(u, dict) else u
        if u:
            m = re.match(r"data:image/([\w+.\-]+);base64,(.*)", u, re.S)
            if m:
                return m.group(1), base64.b64decode(m.group(2))
    # some models may stuff base64 in content
    return None, None


def call_model(model, prompt):
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "modalities": ["image", "text"]}
    if model.startswith("recraft/"):
        payload["image_config"] = {"aspect_ratio": "4:5"}
    headers = {"Authorization": f"Bearer {C.require('OPENROUTER_API_KEY')}",
               "Content-Type": "application/json"}
    r = requests.post(URL, headers=headers, json=payload, timeout=240)
    if r.status_code != 200:
        # retry once without image_config / modalities text
        payload.pop("image_config", None)
        r = requests.post(URL, headers=headers, json=payload, timeout=240)
    return r


def run_one(model, brief_key, brief_body):
    tag = f"{model.split('/')[-1]}__{brief_key}"
    try:
        r = call_model(model, build_prompt(brief_body))
        if r.status_code != 200:
            return tag, None, f"HTTP {r.status_code}: {r.text[:160]}"
        subtype, raw = extract_image(r.json())
        if not raw:
            return tag, None, f"no image in response: {json.dumps(r.json())[:200]}"
        tmp = os.path.join(OUT, f"{tag}.raw")
        with open(tmp, "wb") as f:
            f.write(raw)
        out = os.path.join(OUT, f"{tag}.png")
        Image.open(tmp).convert("RGB").save(out)
        os.remove(tmp)
        return tag, out, None
    except Exception as e:
        return tag, None, f"{type(e).__name__}: {e}"


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [(m, bk, bb) for m in MODELS for bk, bb in BRIEFS.items()]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(run_one, *j) for j in jobs]
        for f in concurrent.futures.as_completed(futs):
            results.append(f.result())
    print("\n=== BAKE-OFF RESULTS ===")
    for tag, path, err in sorted(results):
        print(f"  {'OK ' if path else 'ERR'} {tag}: {path or err}")


if __name__ == "__main__":
    main()
