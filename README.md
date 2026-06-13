# Think Legal India — Social Posting Pipeline

Generates a **high-end marketing graphic + platform captions** for one of our
services/compliance topics and posts it to **Facebook + Instagram** via a
**Make.com** scenario.

```
posts.json ──▶ pipeline.py
                 │  1. pick next topic (rotation, state.json)
                 │  2. generate illustration  (OpenRouter · Recraft v4.1 utility)
                 │  3. compose graphic        (design.py · brand fonts + logo)
                 │  4. host image             (host_image.py · catbox)
                 └▶ 5. POST {image_url, fb_caption, ig_caption} ──▶ Make webhook
                                                                      ├▶ Facebook Pages
                                                                      └▶ Instagram for Business
```

**Captions are written by Claude** (in `posts.json`). **Text + logo are composited
by code** (`design.py`) so every post uses exact brand colours, Archivo type, and
our real v2 logo — the AI model only draws the illustration.

---

## 1. Setup (one time)

```bash
cd automation
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

`.env` (already present, never committed) holds:
`OPENROUTER_API_KEY`, `MAKE_API_TOKEN`, `MAKE_TEAM_ID`, `MAKE_ZONE`,
`MAKE_WEBHOOK_URL`, `IMAGE_HOST`.

Brand assets are bundled in `assets/` (Archivo variable font + Source Serif 4 +
the v2 logo). Nothing else to download.

---

## 2. Running it

```bash
python3 pipeline.py                 # DRY RUN — render next post locally, post nothing
python3 pipeline.py --peek          # show which post is next + its captions, do nothing
python3 pipeline.py --post gst-registration   # render a specific post (dry run)
python3 pipeline.py --live          # render + host + POST to Make (real post)
```

A **bare run is always a dry run** — it writes `outputs/<id>_post.png` and
`outputs/<id>_payload.json` and posts nothing. Add `--live` to actually post.
Open the PNG in `outputs/` to preview before going live.

---

## 3. Adding / editing content

All copy lives in **`posts.json`** under `"posts"`. Posts are used **in order**
(round-robin) — the cursor is tracked in `state.json`, so topics don't repeat
until the list cycles. Add new entries anywhere; the rotation will reach them.

Each post:

```jsonc
{
  "id": "unique-slug",
  "topic": "Human label (for logs)",
  "kicker": "Category Tag",                  // small pill, top-left
  "title_lines": [                            // the hook — mixed fonts/colours
    {"runs": [{"t": "Register your", "w": "s", "c": "ink"}], "size": 52},
    {"runs": [{"t": "Pvt Ltd", "w": "x", "c": "carrot"},
              {"t": " Company", "w": "x", "c": "ink"}], "size": 90}
  ],
  "subhook": "One italic serif supporting line.",
  "bullets": ["Benefit one", "Benefit two", "Benefit three"],
  "cta": "DM “START” to begin",
  "illustration_brief": "what the AI should draw — NO text, brand style",
  "fb_caption": "2–4 sentences, link/CTA, 0–3 hashtags.",
  "ig_caption": "Punchy, line breaks, 1–2 emoji, 8–12 hashtags.",
  "include_disclaimer": false                 // optional: force the legal disclaimer
}
```

- **`w`** (font weight): `x` = ExtraBold, `b` = Bold, `s` = SemiBold.
- **`c`** (colour): `ink`, `carrot`, `willow`, `willow_deep`.
- **`size`**: title line height in px (canvas is 1080×1350). Keep the widest line
  ≲ 920 px wide so it fits the margins.
- The **disclaimer** is added automatically to ~every 5th post (and to any post
  with `"include_disclaimer": true`). Text lives in `config.py` (`DISCLAIMER`).

After editing, preview with `python3 pipeline.py --post <id>` and check `outputs/`.

> Want more topics in the rotation? Just send them to Claude (or add them to
> `posts.json` in the same shape). Current rotation: Pvt Ltd, GST registration,
> GSTR-3B deadline, Trademark, ROC/annual compliance, MSME/Udyam, LLP, GST filing,
> transparent-pricing, ITR filing.

---

## 4. Pause / resume

```bash
touch automation/PAUSED      # pause — every run no-ops until removed
rm   automation/PAUSED       # resume
```

The scheduled job still fires but does nothing while `PAUSED` exists.

---

## 5. Scheduling — runs in the cloud, twice a day

Posts are scheduled by **GitHub Actions** at `.github/workflows/post.yml` in this
repo. Runs on GitHub's servers, **independent of your laptop**.

| Cron (UTC) | IST | What happens |
|---|---|---|
| `0 4 * * *` | 09:30 | Generates the next post and publishes to FB + IG |
| `0 16 * * *` | 21:30 | Generates the next post and publishes to FB + IG |

**Watch a run / trigger one manually:**
- Open the repo on GitHub → **Actions** tab → **post-social** workflow
- Click **Run workflow** → confirm. Useful for testing without waiting for the cron.
- Click any run to see logs (pipeline output, Make response, generated image is uploaded as an artifact).

**Pause posting (temporary):**
- Easiest: GitHub repo → **Actions** tab → **post-social** → **⋯** menu → **Disable workflow**.
- Re-enable with the same menu.
- Or, commit a file named `PAUSED` at the repo root — the pipeline's preflight skips runs when present.

**Rotation state:** `state.json` is committed back to the repo after every successful
run, so the cursor and history persist across cloud runs. (Don't edit it manually
in two places at once — the auto-commit will conflict.)

**Safety net:** `pipeline.py` checks the Make API before every POST and refuses if
(a) the Make scenario is inactive, or (b) the Make webhook already has a queued
bundle. Either condition exits the workflow cleanly with no posting.

**Local testing** (any time, no schedule needed):
```bash
python3 pipeline.py --peek                 # show next post + captions, do nothing
python3 pipeline.py --post gst-registration # preview a specific post locally (dry run)
python3 pipeline.py --live                  # post immediately (use sparingly)
```

---

## 6. Make.com — finishing the posting side

The webhook and an (inactive) scenario shell already exist:

| Thing | Value |
|---|---|
| Webhook | **Think Legal India — Social Post** (`hook id 2450043`) — URL is in `.env` |
| Scenario | **Think Legal India — Auto Post (FB + IG)** (`id 5378537`, currently OFF) |
| Facebook Page | already selected (`page id 1233350009853178`) |
| Payload it receives | `{ image_url, fb_caption, ig_caption, post_id, topic }` |

### ⚠️ Two things only YOU can do (Meta requires a human OAuth login):

**A) Re-authorise Facebook with posting permission.**
The current Facebook connection can *read* the Page but is **missing
`pages_manage_posts`**, so it can't publish yet. In Make → *Connections* → open
"My Facebook connection" → **Reauthorize**, and on the Facebook screen **grant all
permissions** (especially *Manage your Page posts* / *Publish content*).

**B) Connect Instagram.** Instagram connects *through* Facebook (no separate IG
login). First make sure: your Instagram is a **Business/Creator** account **and is
linked to the Facebook Page** (Meta Business Suite → *Linked accounts*). Then in
Make, add an **"Instagram for Business"** module, click **Add** on its Connection
field, log in with the same Facebook account, **grant all permissions**, and pick
the linked Instagram account.

### Then build the two modules in scenario 5378537:

1. **Facebook Pages → Create a Photo Post** — Page = Think Legal India;
   Photo URL = `{{1.image_url}}`; Message = `{{1.fb_caption}}`.
2. **Instagram for Business → Create a Post** (or *Create a Photo Post*) —
   Account = your linked IG; Image URL = `{{1.image_url}}`; Caption = `{{1.ig_caption}}`.

Map by clicking the field and picking from the webhook (the data structure was
already taught with a sample run).

### Before switching ON:
- **Clear the webhook queue** — there is **1 test bundle** queued from setup. Open
  the webhook in the scenario and remove it, or it will post once on activation.
- Toggle the scenario **ON**. Schedule = "Immediately as data arrives".

Once both connections exist, Claude can finish/repair the two modules and activate
the scenario via the Make API on request.

---

## 7. Image hosting

Instagram's publishing API needs a **public image URL**, so `host_image.py`
uploads the rendered PNG and returns one. Default backend is **catbox.moe**
(permanent, no key). These are public marketing images, so a public host is fine.

Switch backends in `.env`: `IMAGE_HOST=catbox` (default) | `0x0` | `none` (dry).
To host on our own domain later, add a backend in `host_image.py`.

---

## 8. Files

| File | Purpose |
|---|---|
| `pipeline.py` | orchestrator + CLI (run this) |
| `posts.json` | content library (Claude-written copy) |
| `design.py` | composition engine (brand layout, text, logo) |
| `generate_image.py` | OpenRouter illustration generation |
| `host_image.py` | public image hosting |
| `config.py` | palette, fonts, paths, model, `.env` loader |
| `run.sh` | cron entrypoint (`--live`) |
| `state.json` | rotation cursor + post history (auto-created) |
| `assets/` | brand fonts + logo |
| `outputs/` | generated images, payloads, logs |

---

## 9. Troubleshooting

- **`MAKE_WEBHOOK_URL is not set`** — it's in `.env`; re-check the file.
- **OpenRouter HTTP 4xx** — check `OPENROUTER_API_KEY` / credits. The pipeline
  auto-retries on the vector fallback model (`recraft-v4.1-vector`).
- **A glyph shows as a box** — add the character's font coverage; Archivo VF
  covers Latin + ₹. (Captions are unaffected — they're plain text.)
- **Nothing posts but logs say HTTP 200** — the Make scenario is OFF or its FB/IG
  modules/connections aren't set up yet (see §6).
- Never print or commit `.env`.
```
