"""
Shared config for the Think Legal India social-posting pipeline.

Loads automation/.env WITHOUT printing any secret values, and exposes the
brand palette + paths used by the image generator and pipeline.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "outputs")
POSTS_FILE = os.path.join(HERE, "posts.json")
STATE_FILE = os.path.join(HERE, "state.json")   # rotation cursor + post history
PAUSE_FILE = os.path.join(HERE, "PAUSED")        # create this file to pause posting
LOG_FILE = os.path.join(OUT_DIR, "pipeline.log")
ASSETS = os.path.join(HERE, "assets")
LOGO_SVG = os.path.join(ASSETS, "logo-icon.svg")
FONT_DIR = os.path.join(ASSETS, "fonts")
# Variable Archivo (full glyph set incl. ₹ U+20B9) — weights via named instances.
FONT_VF = os.path.join(FONT_DIR, "Archivo-VF.ttf")

# Final raster post dimensions — Instagram-feed-friendly portrait 4:5.
POST_W, POST_H = 1080, 1350


def load_env(path=None):
    """Parse .env into a dict. Never prints values."""
    path = path or os.path.join(HERE, ".env")
    env = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()


def require(key):
    val = ENV.get(key) or os.environ.get(key)
    if not val:
        raise SystemExit(f"Missing {key} in automation/.env")
    return val


# --- Brand palette v2 (BRAND_GUIDE.md, 12 Jun 2026) as RGB triples ---
# Hex -> RGB
INK = [55, 55, 31]        # #37371F  text / dark bands
CREAM = [234, 239, 189]   # #EAEFBD  page background
CREAM_SOFT = [242, 245, 216]  # #F2F5D8
PAPER = [253, 254, 246]   # #FDFEF6  cards / clean surface
TEA = [201, 227, 172]     # #C9E3AC  soft fill
WILLOW = [144, 190, 109]  # #90BE6D  success / checkmarks
CARROT = [234, 144, 16]   # #EA9010  primary accent / badges

# Default palette + background fed to Recraft for brand-consistent vectors.
SOCIAL_RGB_COLORS = [INK, CARROT, WILLOW, TEA, PAPER]
SOCIAL_BACKGROUND_RGB = CREAM

# Raster model — renders crisp marketing text + illustration (validated 13 Jun 2026).
IMAGE_MODEL = "recraft/recraft-v4.1-utility"
IMAGE_MODEL_FALLBACK = "recraft/recraft-v4.1-vector"  # vector (SVG); used only if utility fails
ASPECT_RATIO = "4:5"  # portrait, Instagram-feed friendly; used for both platforms

DISCLAIMER = (
    "Think Legal India is a private facilitation platform and is not a government body "
    "or law firm. Listed prices are professional/platform fees — government fees and "
    "18% GST are additional unless explicitly marked “all-inclusive.” Certified "
    "filings are signed off by our partner CAs/Company Secretaries/Advocates."
)

WEBSITE = "thinklegalindia.co"
