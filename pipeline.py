#!/usr/bin/env python3
"""
Think Legal India — social posting pipeline (scheduled run).

Each run:
  1. picks the next post from posts.json (round-robin via state.json)
  2. generates a clean illustration (OpenRouter / Recraft v4.1 utility)
  3. composites the high-end marketing graphic with design.py (text + logo)
  4. (live) hosts the image and POSTs {image_url, fb_caption, ig_caption} to the
     Make.com webhook, which posts to Facebook + Instagram
  5. records it in state.json so the next run advances the rotation

Safe by default: a bare run is a DRY RUN (renders + saves locally, no upload, no
post). Pass --live to actually host + POST. Requires MAKE_WEBHOOK_URL in .env.

Usage:
  python pipeline.py                 # dry run: render the next post locally
  python pipeline.py --live          # render + host + post via Make webhook
  python pipeline.py --post gst-registration   # force a specific post id
  python pipeline.py --peek          # show which post is next, do nothing
  python pipeline.py --no-image --post pvt-ltd-registration   # reuse last illustration

Pause/resume:  create the file automation/PAUSED to pause; delete it to resume.
"""
import os
import sys
import json
import argparse
import datetime
import requests

import config as C
from generate_image import generate_illustration
from design import render_post
from host_image import host_image

DISCLAIMER_EVERY = 5  # include the legal disclaimer on ~every 5th post


def log(msg):
    os.makedirs(C.OUT_DIR, exist_ok=True)
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with open(C.LOG_FILE, "a") as f:
        f.write(line + "\n")


# Make scenario / hook IDs — kept here (not secret) so preflight can self-check.
MAKE_SCENARIO_ID = 5378537
MAKE_HOOK_ID_DEFAULT = 2450179


def preflight_make(force_through_queued: bool = False) -> None:
    """Safety net: refuse to POST if Make's scenario is inactive (the bundle would
    sit forever) OR if there's already something queued (we'd duplicate the last
    failed bundle as Make replays it on next activation).

    This prevents the duplicate-post incident we hit during bring-up: a previously
    failed bundle stayed in the webhook queue, then got auto-replayed when the
    scenario was activated. Pass --force-queued to override (advanced)."""
    zone = C.ENV.get("MAKE_ZONE")
    tok  = C.ENV.get("MAKE_API_TOKEN")
    if not (zone and tok):
        log("preflight skipped — no Make API token in .env (can't self-check).")
        return
    H = {"Authorization": f"Token {tok}"}
    base = f"https://{zone}/api/v2"
    try:
        s = requests.get(f"{base}/scenarios/{MAKE_SCENARIO_ID}",
                         headers=H, timeout=20).json().get("scenario", {})
        if not s.get("isActive"):
            raise SystemExit(
                f"REFUSING TO POST: Make scenario {MAKE_SCENARIO_ID} is INACTIVE. "
                "The bundle would queue and fire whenever it's reactivated — risk of "
                "duplicate/stale posts. Activate it in the Make UI (or via "
                "make_wire.py activate) and retry.")
        hook_id = s.get("hookId") or MAKE_HOOK_ID_DEFAULT
        h = requests.get(f"{base}/hooks/{hook_id}",
                         headers=H, timeout=20).json().get("hook", {})
        qc = h.get("queueCount", 0)
        if qc and not force_through_queued:
            raise SystemExit(
                f"REFUSING TO POST: webhook {hook_id} already has {qc} bundle(s) "
                "queued. Posting now would publish the queued bundle in addition to "
                "this one (duplicate). Investigate via make_wire.py inspect, drain "
                "the queue, or rerun with --force-queued to override.")
        log(f"preflight OK — Make scenario {MAKE_SCENARIO_ID} active, hook {hook_id} queue=0.")
    except requests.RequestException as e:
        log(f"preflight skipped — Make API unreachable: {e}")


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def pick_post(posts, state, forced_id=None):
    if forced_id:
        for p in posts:
            if p["id"] == forced_id:
                return p
        raise SystemExit(f"No post with id {forced_id!r} in posts.json")
    cursor = state.get("cursor", 0)
    return posts[cursor % len(posts)]


def needs_disclaimer(post, state):
    if post.get("include_disclaimer"):
        return True
    # every Nth post in the rolling history
    return (len(state.get("history", [])) + 1) % DISCLAIMER_EVERY == 0


def build_captions(post, disclaimer):
    fb = post["fb_caption"]
    ig = post["ig_caption"]
    if disclaimer:
        fb = fb + "\n\n" + C.DISCLAIMER
        ig = ig + "\n\n" + C.DISCLAIMER
    return fb, ig


def run(args):
    if os.path.exists(C.PAUSE_FILE) and not args.peek:
        log("PAUSED (automation/PAUSED exists) — skipping this run. Delete the file to resume.")
        return 0

    posts = load_json(C.POSTS_FILE, {}).get("posts", [])
    if not posts:
        raise SystemExit("posts.json has no posts.")
    state = load_json(C.STATE_FILE, {"cursor": 0, "history": []})

    post = pick_post(posts, state, args.post)
    disclaimer = needs_disclaimer(post, state)
    log(f"Next post: {post['id']}  (topic: {post['topic']}) | disclaimer={disclaimer} | "
        f"mode={'LIVE' if args.live else 'dry-run'}")
    if args.peek:
        fb, ig = build_captions(post, disclaimer)
        print("\n--- FACEBOOK ---\n" + fb + "\n\n--- INSTAGRAM ---\n" + ig)
        return 0

    os.makedirs(C.OUT_DIR, exist_ok=True)
    illus = os.path.join(C.OUT_DIR, f"{post['id']}_illustration.png")
    final = os.path.join(C.OUT_DIR, f"{post['id']}_post.png")

    if not args.no_image or not os.path.exists(illus):
        log(f"Generating illustration → {os.path.basename(illus)}")
        generate_illustration(post["illustration_brief"], illus)
    render_post(post, illustration_path=illus, out_path=final)
    log(f"Rendered post → {os.path.basename(final)}")

    fb, ig = build_captions(post, disclaimer)

    if not args.live:
        payload_preview = {"image_local": final, "fb_caption": fb, "ig_caption": ig}
        save_json(os.path.join(C.OUT_DIR, f"{post['id']}_payload.json"), payload_preview)
        log("DRY RUN complete — image + captions saved locally, nothing posted. "
            "Use --live to host + post.")
        print("\n--- FACEBOOK CAPTION ---\n" + fb + "\n\n--- INSTAGRAM CAPTION ---\n" + ig)
        return 0

    # --- LIVE ---
    webhook = C.ENV.get("MAKE_WEBHOOK_URL")
    if not webhook:
        raise SystemExit("MAKE_WEBHOOK_URL is not set in automation/.env — cannot post. "
                         "Create the Make scenario webhook first (see README).")
    preflight_make(args.force_queued)
    log("Hosting image…")
    image_url = host_image(final)
    log(f"Image URL: {image_url}")
    body = {"image_url": image_url, "fb_caption": fb, "ig_caption": ig,
            "post_id": post["id"], "topic": post["topic"]}
    log("POSTing to Make webhook…")
    r = requests.post(webhook, json=body, timeout=120)
    log(f"Make webhook responded HTTP {r.status_code}: {r.text[:200]}")
    r.raise_for_status()

    # advance rotation + record history (only on a real post, and only when not forced)
    if not args.post:
        state["cursor"] = state.get("cursor", 0) + 1
    state.setdefault("history", []).append({
        "id": post["id"], "topic": post["topic"],
        "posted_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "image_url": image_url, "disclaimer": disclaimer,
    })
    save_json(C.STATE_FILE, state)
    log(f"Posted {post['id']} ✓  (cursor now {state.get('cursor', 0)})")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Think Legal India social posting pipeline")
    ap.add_argument("--live", action="store_true", help="host image + POST to Make webhook")
    ap.add_argument("--post", metavar="ID", help="force a specific post id from posts.json")
    ap.add_argument("--peek", action="store_true", help="show the next post + captions, do nothing")
    ap.add_argument("--no-image", action="store_true", help="reuse existing illustration if present")
    ap.add_argument("--force-queued", action="store_true",
                    help="post even if the Make webhook already has a queued bundle "
                         "(advanced — risk of duplicate post)")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()
