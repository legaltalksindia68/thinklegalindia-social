#!/usr/bin/env python3
"""
Wire the Make.com scenario 5378537 ("Think Legal India — Auto Post (FB + IG)").

The Make Public API doesn't expose its app/module catalog, so we discover the
exact module identifiers + mapper keys empirically: PATCH the blueprint, read
the validation error, adjust, repeat. This script encodes what we've learned so
the same call works every time.

Run:
    python3 make_wire.py inspect           # show current scenario + blueprint
    python3 make_wire.py probe <module>    # try a candidate module name; print result
    python3 make_wire.py patch             # push the final 3-module blueprint
    python3 make_wire.py activate          # turn the scenario ON
    python3 make_wire.py pause             # turn it OFF
    python3 make_wire.py clear-queue       # try to drain the webhook queue (best-effort)
"""
import sys, json, requests
import config as C

SCENARIO_ID = 5378537
HOOK_ID = 2450043
FB_CONN = 9387553
FB_PAGE_ID = "1233350009853178"  # Legal Talks India (Bangalore)
BASE = f"https://{C.require('MAKE_ZONE')}/api/v2"
H = {"Authorization": f"Token {C.require('MAKE_API_TOKEN')}",
     "Content-Type": "application/json"}
TEAM = int(C.require("MAKE_TEAM_ID"))


def trigger_webhook():
    return {
        "id": 1, "module": "gateway:CustomWebHook", "version": 1,
        "parameters": {"hook": HOOK_ID, "maxResults": 1},
        "mapper": {},
        "metadata": {"designer": {"x": 0, "y": 0},
                     "restore": {"parameters": {"hook": {"label": "Think Legal India — Social Post"}}},
                     "parameters": [{"name": "hook", "type": "hook:gateway-webhook",
                                     "label": "Webhook", "required": True}]}
    }


def fb_module(module_name, mapper):
    return {
        "id": 2, "module": module_name, "version": 6,
        "parameters": {"__IMTCONN__": FB_CONN},
        "mapper": mapper,
        "metadata": {"designer": {"x": 300, "y": 0},
                     "restore": {"parameters": {"__IMTCONN__": {"label": "My Facebook connection"}}},
                     "parameters": [{"name": "__IMTCONN__", "type": "account:facebook",
                                     "label": "Connection", "required": True}]}
    }


def ig_module(module_name, mapper):
    return {
        "id": 3, "module": module_name, "version": 1,
        "parameters": {"__IMTCONN__": FB_CONN},
        "mapper": mapper,
        "metadata": {"designer": {"x": 600, "y": 0},
                     "restore": {"parameters": {"__IMTCONN__": {"label": "My Facebook connection"}}},
                     "parameters": [{"name": "__IMTCONN__", "type": "account:facebook",
                                     "label": "Connection", "required": True}]}
    }


def blueprint(flow, name="Think Legal India — Auto Post (FB + IG)"):
    return {
        "name": name,
        "flow": flow,
        "metadata": {
            "version": 1,
            "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True,
                         "autoCommitTriggerLast": True, "sequential": False,
                         "confidential": False, "dataloss": False, "dlq": False},
            "designer": {"orphans": []}, "zone": C.require("MAKE_ZONE")
        }
    }


def patch_scenario(blueprint_obj):
    body = {"blueprint": json.dumps(blueprint_obj)}
    r = requests.patch(f"{BASE}/scenarios/{SCENARIO_ID}", headers=H, json=body, timeout=60)
    print(f"PATCH HTTP {r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2)[:1800])
    except Exception:
        print(r.text[:1800])
    return r


def cmd_inspect():
    s = requests.get(f"{BASE}/scenarios/{SCENARIO_ID}", headers=H, timeout=30).json()
    print(json.dumps(s, indent=2)[:1200])
    bp = requests.get(f"{BASE}/scenarios/{SCENARIO_ID}/blueprint",
                      headers=H, timeout=30).json()
    print("---- blueprint ----")
    print(json.dumps(bp, indent=2)[:2500])


def cmd_probe(args):
    """Push a 3-step blueprint with provided module names & default mapper guesses.
    Args: <fb_module> <ig_module>"""
    fb_name = args[0] if args else "facebook-pages:CreatePostWithPhotos"
    ig_name = args[1] if len(args) > 1 else "instagram-business:CreatePhotoPost"
    flow = [
        trigger_webhook(),
        fb_module(fb_name, {"page_id": FB_PAGE_ID,
                            "message": "{{1.fb_caption}}",
                            "photos": [{"url": "{{1.image_url}}"}]}),
        ig_module(ig_name, {"image_url": "{{1.image_url}}",
                            "caption": "{{1.ig_caption}}"}),
    ]
    patch_scenario(blueprint(flow))


def cmd_activate():
    r = requests.post(f"{BASE}/scenarios/{SCENARIO_ID}/start",
                      headers=H, timeout=30)
    print(f"start HTTP {r.status_code} -> {r.text[:300]}")


def cmd_pause():
    r = requests.post(f"{BASE}/scenarios/{SCENARIO_ID}/stop",
                      headers=H, timeout=30)
    print(f"stop HTTP {r.status_code} -> {r.text[:300]}")


def cmd_clear_queue():
    # try the queue endpoints; Make's API doesn't always expose a drain
    for path in (f"hooks/{HOOK_ID}/queue", f"hooks/{HOOK_ID}/queues",
                 f"hooks/{HOOK_ID}/data"):
        r = requests.delete(f"{BASE}/{path}", headers=H, timeout=30)
        print(f"DELETE /{path} -> HTTP {r.status_code} {r.text[:160]}")
    r = requests.get(f"{BASE}/hooks/{HOOK_ID}", headers=H, timeout=30).json()
    print("queueCount now:", r.get("hook", {}).get("queueCount"))


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    cmd, rest = sys.argv[1], sys.argv[2:]
    {"inspect": cmd_inspect, "probe": lambda: cmd_probe(rest),
     "patch":   lambda: cmd_probe(rest), "activate": cmd_activate,
     "pause":   cmd_pause, "clear-queue": cmd_clear_queue}.get(
        cmd, lambda: (_ for _ in ()).throw(SystemExit(f"unknown cmd: {cmd}")))()


if __name__ == "__main__":
    main()
