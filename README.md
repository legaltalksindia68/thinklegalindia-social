# Think Legal India — Social Posting Engine

Generates a **unique, ultra-premium marketing post** every run and publishes it to
**Facebook + Instagram** via **Make.com**. Runs twice a day in the cloud (GitHub
Actions) — independent of any laptop.

```
GitHub Actions cron (09:30 + 21:30 IST)
  └─ pipeline.py
       1. creative.py    → LLM (Claude Sonnet via OpenRouter) writes a UNIQUE post:
                            fresh problem-solver hook, mixed-font headline, 3 bullets,
                            CTA, illustration brief, + different FB & IG captions +
                            hashtags. Avoids recent posts (state.json) and is date-aware
                            (posts timely deadline reminders).
       2. generate_image → Recraft draws the no-text illustration (cheap)
       3. design.py      → composes the "Dark Luxe" poster IN CODE: gradient-mesh depth,
                            Archivo + Source-Serif headline, willow bullets, cut-out
                            illustration that blends, real v2 logo. Perfect every time.
       4. host_image.py  → public URL (GitHub Release asset)
       5. → Make webhook → Facebook Pages + Instagram for Business
       6. state.json committed back → next run never repeats
```

**Nothing repeats.** Copy + illustration are generated fresh each run; layout + accent
rotate; the LLM is told the last 25 topics/angles to avoid. With 50+ services × angles
it won't loop for months.

---

## Run / test locally

```bash
pip install -r requirements.txt          # requests, Pillow, numpy
python3 pipeline.py --peek               # print the freshly-written copy (no image)
python3 pipeline.py                       # DRY RUN: generate + render to outputs/, post nothing
python3 pipeline.py --live                # generate + host + post for real
open outputs/current_post.png             # preview the rendered poster
```

A bare run never posts. Only `--live` posts.

---

## Scheduling (cloud — no laptop needed)

`.github/workflows/post.yml` runs `pipeline.py --live` at **04:00 + 16:00 UTC = 09:30 +
21:30 IST**. Watch / control it from the repo's **Actions** tab:

- **Run now / test:** Actions → *post-social* → **Run workflow**
- **Pause:** Actions → *post-social* → ⋯ → **Disable workflow** (re-enable the same way)
- **Logs + the generated image:** click any run (image is uploaded as an artifact)

`state.json` (rotation history) is committed back after every successful run.

**Safety net:** before posting, `pipeline.py` checks the Make API and refuses if the
scenario is inactive or the webhook already has a queued bundle (prevents duplicates).
If the creative LLM ever fails, an emergency evergreen spec keeps the slot filled.

---

## Tuning the content

- **Topics / deadlines:** edit `themes.json` (services, compliance calendar, audiences,
  angle seeds). The LLM remixes these — add anything and it'll surface.
- **Voice / rules / look:** edit `brand.py` (`VOICE`, `GENRE`, `VISUAL`, the system
  prompt). This is the brand bible — self-contained so the cloud run needs nothing else.
- **Models:** `config.py` → `TEXT_MODEL` (copywriter), `IMAGE_MODEL` (illustration).
- **Design styles:** `design.py` → Dark-Luxe archetypes `dark-hero-bottom`, `dark-split`
  (rotated automatically). `light-glass` / `editorial-hero` also available.

---

## Make.com (already wired)

| Thing | Value |
|---|---|
| Webhook | hook `2450179`, URL in `.env` as `MAKE_WEBHOOK_URL` |
| Scenario | "Think Legal India — Auto Post (FB + IG)" id `5378537`, **active** |
| FB module | `facebook-pages:CreatePostWithPhotos` → page "Legal Talks India" |
| IG module | `instagram-business:CreatePostPhoto` → linked IG account |
| Connection | FB OAuth with `pages_manage_posts` + `instagram_content_publish` |

Posts receive `{ image_url, fb_caption, ig_caption, topic }`.

---

## Files

| File | Purpose |
|---|---|
| `pipeline.py` | orchestrator + CLI (run this) |
| `creative.py` | LLM copywriter/art-director → validated post spec |
| `brand.py` | brand bible + system prompt + headline parser |
| `themes.json` | topic universe (services + compliance calendar) |
| `design.py` | ultra-premium "Dark Luxe" composition engine |
| `generate_image.py` | Recraft illustration generation |
| `host_image.py` | public image hosting (GitHub Release in CI) |
| `config.py` | models, palette, fonts, paths, `.env` loader |
| `bakeoff.py` | one-off image-model comparison utility |
| `assets/` | brand fonts (Archivo VF + Source Serif 4) + logo |
| `state.json` | post history (anti-repeat; committed back each run) |
| `posts.json` | legacy hand-written pool (no longer used) |

Never commit `.env`. Secrets live in GitHub Actions Secrets for the cloud runs.
