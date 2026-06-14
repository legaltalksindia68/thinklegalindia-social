#!/usr/bin/env python3
"""
The creative studio: calls the copywriter/art-director LLM (OpenRouter) and returns
ONE validated, unique post spec — fresh hook, mixed-font headline, bullets, CTA,
illustration brief, and platform captions — while avoiding recent posts.

    from creative import generate_post_spec
    spec = generate_post_spec(history, force_disclaimer=False)
"""
import os
import re
import json
import datetime
import requests

import config as C
import brand


def _openrouter_json(messages, model, timeout=120):
    headers = {"Authorization": f"Bearer {C.require('OPENROUTER_API_KEY')}",
               "Content-Type": "application/json",
               "X-Title": "Think Legal India Social"}
    payload = {"model": model, "messages": messages, "temperature": 0.95,
               "max_tokens": 1500, "response_format": {"type": "json_object"}}
    r = requests.post(C.OPENROUTER_URL, headers=headers, json=payload, timeout=timeout)
    if r.status_code != 200:
        # some models reject response_format — retry without it
        payload.pop("response_format", None)
        r = requests.post(C.OPENROUTER_URL, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse(content):
    content = content.strip()
    content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.M).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            return json.loads(m.group(0))
        raise


REQUIRED = ("topic", "headline_lines", "bullets", "cta", "illustration_brief",
            "fb_caption", "ig_caption")


def _valid(d):
    return (isinstance(d, dict) and all(d.get(k) for k in REQUIRED)
            and isinstance(d["headline_lines"], list) and isinstance(d["bullets"], list))


def generate_post_spec(history, force_disclaimer=False, today=None, max_tries=3):
    today = today or datetime.date.today().strftime("%A, %d %B %Y")
    universe = json.dumps(json.load(open(C.THEMES_FILE)), ensure_ascii=False)[:4000] \
        if os.path.exists(C.THEMES_FILE) else "(general company/GST/tax/trademark services)"
    msgs = brand.build_messages(history, today, universe, force_disclaimer)

    raw = None
    for _ in range(max_tries):
        try:
            content = _openrouter_json(msgs, C.TEXT_MODEL)
            d = _parse(content)
            if _valid(d):
                raw = d
                break
        except Exception:
            continue
    if not raw:
        raise RuntimeError("creative LLM did not return a valid post spec after retries")

    # normalise into the design spec + caption bundle
    layout = raw.get("layout") if raw.get("layout") in brand.LAYOUTS else brand.LAYOUTS[0]
    accent = raw.get("accent") if raw.get("accent") in brand.ACCENTS else "carrot"
    headline = brand.parse_headline(raw["headline_lines"])
    bullets = [b for b in raw["bullets"] if b][:3]
    hashtags = raw.get("hashtags") or []
    ig = raw["ig_caption"].rstrip()
    if hashtags:
        ig = ig + "\n\n" + " ".join(h if h.startswith("#") else "#" + h for h in hashtags)

    return {
        "topic": raw["topic"],
        "angle": raw.get("angle", ""),
        "layout": layout,
        "accent": accent,
        "kicker": raw.get("kicker", raw["topic"]),
        "headline": headline,
        "subhook": raw.get("subhook", ""),
        "bullets": bullets,
        "cta": raw.get("cta", f"Visit {C.WEBSITE}"),
        "illustration_brief": raw["illustration_brief"],
        "fb_caption": raw["fb_caption"],
        "ig_caption": ig,
    }


if __name__ == "__main__":
    spec = generate_post_spec([], force_disclaimer=False)
    print(json.dumps({k: v for k, v in spec.items() if k != "headline"}, indent=2, ensure_ascii=False))
    print("\nHEADLINE RUNS:")
    for line in spec["headline"]:
        print("  ", "".join(r["t"] for r in line["runs"]), f"(size {line['size']})")
