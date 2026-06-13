#!/usr/bin/env python3
"""
Make the rendered post image publicly reachable so Make.com (and therefore the
Facebook Pages / Instagram for Business modules) can fetch it.

Instagram's Content Publishing API only accepts a public image URL (not binary),
so hosting is required for IG. These are public marketing images by design, so a
public host is fine.

Backends (choose via IMAGE_HOST in .env, default "catbox"):
  - github-release : upload as a release asset on the public repo itself.
                     Used in GitHub Actions (datacenter IPs work here, catbox blocks them).
                     Needs GITHUB_TOKEN + GITHUB_REPOSITORY env vars (CI provides both).
  - catbox  : catbox.moe anonymous upload — permanent public URL, no API key.
              Works from residential IPs; rejects datacenter IPs (412).
  - 0x0     : 0x0.st — public URL, long retention for small files, no key.
  - none    : skip hosting (dry-run); returns a file:// path.
"""
import os
import time
import requests
import config as C

GH_RELEASE_TAG = "media"  # single "media" release on the repo holds all post images


def _catbox(path):
    with open(path, "rb") as f:
        r = requests.post("https://catbox.moe/user/api.php",
                          data={"reqtype": "fileupload"},
                          files={"fileToUpload": f}, timeout=120)
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"catbox upload failed: {url[:200]}")
    return url


def _zerox(path):
    with open(path, "rb") as f:
        r = requests.post("https://0x0.st", files={"file": f},
                          headers={"User-Agent": "ThinkLegalIndia/1.0"}, timeout=120)
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"0x0 upload failed: {url[:200]}")
    return url


def _github_release(path):
    """Upload the file as an asset on the repo's `media` release. The asset's
    browser_download_url is a public CDN URL that Make.com can fetch directly.
    Run-ID + basename keeps every asset unique. Old assets are pruned (keep ~60)."""
    token = os.environ.get("GITHUB_TOKEN") or C.ENV.get("GITHUB_TOKEN")
    repo  = os.environ.get("GITHUB_REPOSITORY") or C.ENV.get("GITHUB_REPOSITORY")
    if not (token and repo):
        raise RuntimeError("github-release backend needs GITHUB_TOKEN + "
                           "GITHUB_REPOSITORY env vars (auto-set inside GitHub Actions)")
    H = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    # 1) Resolve the release id by tag (created once via API; reused forever)
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/tags/{GH_RELEASE_TAG}",
                     headers=H, timeout=30)
    if r.status_code == 404:
        r = requests.post(f"https://api.github.com/repos/{repo}/releases", headers=H,
                          json={"tag_name": GH_RELEASE_TAG,
                                "name": "Media (post images)",
                                "body": "Auto-uploaded post images for Make.com to fetch.",
                                "prerelease": True}, timeout=30)
    r.raise_for_status()
    rel = r.json()
    upload_base = rel["upload_url"].split("{")[0]
    release_id = rel["id"]

    # 2) Build a unique asset name and upload
    run_id = os.environ.get("GITHUB_RUN_ID") or str(int(time.time()))
    name   = f"{run_id}_{os.path.basename(path)}"
    with open(path, "rb") as f:
        data = f.read()
    r = requests.post(f"{upload_base}?name={name}", headers={**H,
                      "Content-Type": "image/png"}, data=data, timeout=120)
    r.raise_for_status()
    url = r.json()["browser_download_url"]

    # 3) Best-effort prune: keep the 60 most recent assets, delete older ones
    try:
        assets = requests.get(f"https://api.github.com/repos/{repo}/releases/{release_id}/assets"
                              "?per_page=100", headers=H, timeout=30).json()
        if isinstance(assets, list) and len(assets) > 60:
            for a in sorted(assets, key=lambda a: a["created_at"])[:len(assets) - 60]:
                requests.delete(f"https://api.github.com/repos/{repo}/releases/assets/{a['id']}",
                                headers=H, timeout=30)
    except Exception:
        pass  # never fail the post over a prune error

    return url


BACKENDS = {"catbox": _catbox, "0x0": _zerox, "github-release": _github_release}


def host_image(path: str) -> str:
    """Upload `path` and return a public URL (or a file:// path in 'none' mode)."""
    backend = (C.ENV.get("IMAGE_HOST") or "catbox").lower()
    if backend == "none":
        return "file://" + os.path.abspath(path)
    fn = BACKENDS.get(backend)
    if not fn:
        raise SystemExit(f"Unknown IMAGE_HOST={backend!r}. Options: {list(BACKENDS)} or 'none'.")
    return fn(path)


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(C.OUT_DIR, "design_sample.png")
    print(host_image(p))
