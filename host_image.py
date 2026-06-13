#!/usr/bin/env python3
"""
Make the rendered post image publicly reachable so Make.com (and therefore the
Facebook Pages / Instagram for Business modules) can fetch it.

Instagram's Content Publishing API only accepts a public image URL (not binary),
so hosting is required for IG. These are public marketing images by design, so a
public host is fine.

Backends (choose via IMAGE_HOST in .env, default "catbox"):
  - catbox  : catbox.moe anonymous upload — permanent public URL, no API key
  - 0x0     : 0x0.st — public URL, long retention for small files, no key
  - none    : skip hosting (dry-run); returns a file:// path

To use your own bucket/Vercel later, add a backend here and set IMAGE_HOST.
"""
import os
import requests
import config as C


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


BACKENDS = {"catbox": _catbox, "0x0": _zerox}


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
