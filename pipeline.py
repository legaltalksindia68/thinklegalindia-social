#!/usr/bin/env python3
"""
Think Legal India — social posting pipeline (scheduled run).

Each run produces a UNIQUE post:
  1. creative.py  → LLM writes a fresh hook + copy + captions + illustration brief
                    (avoids recent posts via state.json history; date-aware)
  2. generate_image.py → Recraft draws the no-text illustration
  3. design.py    → composes the ultra-premium "Dark Luxe" poster (real logo, brand type)
  4. host_image.py → public URL (GitHub Release asset in CI)
  5. preflight + POST {image_url, fb_caption, ig_caption} → Make webhook → FB + IG
  6. state.json   → record topic/angle/layout so the NEXT run never repeats

Safe by default: a bare run is a DRY RUN (renders locally, posts nothing). --live posts.

  python3 pipeline.py            # dry run: generate + render locally
  python3 pipeline.py --peek     # just print the freshly-written copy (no image)
  python3 pipeline.py --live     # generate + host + post via Make
Pause: create automation/PAUSED (or disable the GitHub Action).
"""
import os
import sys
import json
import argparse
import datetime
import requests

import config as C
from creative import generate_post_spec
from generate_image import generate_illustration
from design import render_post
from host_image import host_image

DISCLAIMER_EVERY = 5
MAKE_SCENARIO_ID = 5378537
MAKE_HOOK_ID_DEFAULT = 2450179

# Emergency spec (new format) used only if the creative LLM fails repeatedly — a slot
# is never missed. Plain, on-brand, evergreen.
EMERGENCY_SPEC = {
    "topic": "Company Registration", "angle": "evergreen fallback", "layout": "dark-hero-bottom",
    "accent": "carrot", "kicker": "Start Right",
    "headline": None,  # filled below via brand.parse_headline
    "subhook": "All-inclusive pricing, real CAs, and a status you can actually track.",
    "bullets": ["Transparent, all-in pricing", "Filed by partner CAs & CS", "Trackable, fast turnaround"],
    "cta": "Get started → thinklegalindia.co",
    "illustration_brief": "a flat-vector official certificate with a willow-green approval seal and "
                          "a small upward growth chart, plain light background, no text, no logos",
    "fb_caption": "Starting a business in India? We handle registration, GST, trademarks and ongoing "
                  "compliance at one transparent, all-inclusive price — signed off by partner CAs & "
                  "Company Secretaries. Visit thinklegalindia.co or comment “START”.",
    "ig_caption": "Start right. Stay compliant. ✅\n\nRegistration, GST, trademark & compliance — "
                  "transparent pricing, real experts.\n\nDM “START” or link in bio.\n\n"
                  "#StartupIndia #CompanyRegistration #SmallBusinessIndia #GSTIndia #ThinkLegalIndia",
}


def current_slot(now_utc=None):
    """Which daily slot are we in, in IST? Returns (ist_date_str, 'morning'|'evening').

    Targets: 09:30 IST (morning) and 21:30 IST (evening). We classify by IST hour so
    that a *catch-up* run firing late still counts toward the slot it belongs to:
    06:00–16:00 IST → morning, otherwise → evening.
    """
    now_utc = now_utc or datetime.datetime.utcnow()
    ist = now_utc + datetime.timedelta(hours=5, minutes=30)
    slot = "morning" if 6 <= ist.hour < 16 else "evening"
    return ist.date().isoformat(), slot


def already_posted_this_slot(history, day, slot):
    return any(e.get("ist_date") == day and e.get("slot") == slot for e in history)


def log(msg):
    os.makedirs(C.OUT_DIR, exist_ok=True)
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with open(C.LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def preflight_make(force_queued=False):
    zone, tok = C.ENV.get("MAKE_ZONE"), C.ENV.get("MAKE_API_TOKEN")
    if not (zone and tok):
        log("preflight skipped — no Make API token."); return
    H = {"Authorization": f"Token {tok}"}
    base = f"https://{zone}/api/v2"
    try:
        s = requests.get(f"{base}/scenarios/{MAKE_SCENARIO_ID}", headers=H, timeout=20).json().get("scenario", {})
        if not s.get("isActive"):
            raise SystemExit(f"REFUSING TO POST: Make scenario {MAKE_SCENARIO_ID} is INACTIVE.")
        hid = s.get("hookId") or MAKE_HOOK_ID_DEFAULT
        qc = requests.get(f"{base}/hooks/{hid}", headers=H, timeout=20).json().get("hook", {}).get("queueCount", 0)
        if qc and not force_queued:
            raise SystemExit(f"REFUSING TO POST: webhook {hid} has {qc} queued bundle(s) — would duplicate. "
                             "Use --force-queued to override.")
        log(f"preflight OK — scenario active, hook {hid} queue=0.")
    except requests.RequestException as e:
        log(f"preflight skipped — Make API unreachable: {e}")


def make_spec(history, force_disclaimer):
    try:
        return generate_post_spec(history, force_disclaimer=force_disclaimer)
    except Exception as e:
        log(f"creative LLM failed ({e}); using emergency spec.")
        import brand
        spec = dict(EMERGENCY_SPEC)
        spec["headline"] = brand.parse_headline(["Start right.", "Stay *compliant*."])
        return spec


def run(args):
    if os.path.exists(C.PAUSE_FILE) and not args.peek:
        log("PAUSED — skipping run. Delete automation/PAUSED to resume."); return 0

    state = load_json(C.STATE_FILE, {"history": []})
    history = state.get("history", [])

    # Timing is driven by Make.com, which triggers GitHub twice a day and passes the
    # slot explicitly via the SLOT env (morning/evening). We trust that over the wall
    # clock, so a run still records the correct slot even if GitHub starts it a little
    # late. ('manual'/unset → fall back to clock-derived slot.) The dedup then makes a
    # same-slot retry a no-op so we never double-post.
    day, clock_slot = current_slot()
    env_slot = os.environ.get("SLOT", "").strip().lower()
    slot = env_slot if env_slot in ("morning", "evening") else clock_slot
    if args.live and not args.force_slot and already_posted_this_slot(history, day, slot):
        log(f"Already posted in the {day} {slot} slot — skipping (self-heal dedup, no double-post).")
        return 0

    force_disc = (len(history) + 1) % DISCLAIMER_EVERY == 0

    log(f"Generating unique post (mode={'LIVE' if args.live else 'dry-run'}, "
        f"disclaimer={force_disc})…")
    spec = make_spec(history, force_disc)
    # guarantee visual variety in code (don't rely on the LLM not clustering)
    import brand
    spec["layout"] = brand.LAYOUTS[len(history) % len(brand.LAYOUTS)]
    spec["accent"] = brand.ACCENTS[len(history) % len(brand.ACCENTS)]
    headline_txt = " / ".join("".join(r["t"] for r in ln["runs"]) for ln in spec["headline"])
    log(f"Topic: {spec['topic']} | layout: {spec['layout']} | accent: {spec['accent']}")
    log(f"Hook: {headline_txt}")

    if args.peek:
        print("\n=== HEADLINE ===\n" + headline_txt)
        print("\n=== FACEBOOK ===\n" + spec["fb_caption"])
        print("\n=== INSTAGRAM ===\n" + spec["ig_caption"])
        return 0

    os.makedirs(C.OUT_DIR, exist_ok=True)
    illus = os.path.join(C.OUT_DIR, "current_illustration.png")
    final = os.path.join(C.OUT_DIR, "current_post.png")
    if not args.no_image or not os.path.exists(illus):
        log("Generating illustration…")
        generate_illustration(spec["illustration_brief"], illus)
    render_post(spec, illustration_path=illus, out_path=final, layout=spec["layout"])
    log(f"Rendered → {final}")

    fb, ig = spec["fb_caption"], spec["ig_caption"]
    if not args.live:
        save_json(os.path.join(C.OUT_DIR, "current_payload.json"),
                  {"image_local": final, "fb_caption": fb, "ig_caption": ig, "spec_topic": spec["topic"]})
        log("DRY RUN complete — saved locally, nothing posted. Use --live to post.")
        print("\n=== FACEBOOK ===\n" + fb + "\n\n=== INSTAGRAM ===\n" + ig)
        return 0

    # --- LIVE ---
    if not C.ENV.get("MAKE_WEBHOOK_URL"):
        raise SystemExit("MAKE_WEBHOOK_URL not set in .env.")
    preflight_make(args.force_queued)
    log("Hosting image…")
    image_url = host_image(final)
    log(f"Image URL: {image_url}")
    body = {"image_url": image_url, "fb_caption": fb, "ig_caption": ig,
            "topic": spec["topic"]}
    r = requests.post(C.ENV["MAKE_WEBHOOK_URL"], json=body, timeout=120)
    log(f"Make webhook HTTP {r.status_code}: {r.text[:160]}")
    r.raise_for_status()

    history.append({
        "posted_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "ist_date": day, "slot": slot,
        "topic": spec["topic"], "angle": spec["angle"], "layout": spec["layout"],
        "accent": spec["accent"], "headline": headline_txt, "image_url": image_url,
        "disclaimer": force_disc,
    })
    state["history"] = history
    save_json(C.STATE_FILE, state)
    log(f"Posted ✓  ({spec['topic']}) — history now {len(history)} posts.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Think Legal India social posting pipeline")
    ap.add_argument("--live", action="store_true", help="host + POST to Make webhook")
    ap.add_argument("--peek", action="store_true", help="print freshly-written copy, no image")
    ap.add_argument("--no-image", action="store_true", help="reuse existing illustration")
    ap.add_argument("--force-queued", action="store_true", help="post even if a bundle is queued")
    ap.add_argument("--force-slot", action="store_true", help="post even if this slot already posted")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()
