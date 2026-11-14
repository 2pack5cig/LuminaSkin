"""Photo quality gate: blur, darkness, glare. Thresholds are starting points; tune on real phone photos."""
import cv2
import numpy as np

BLUR_MIN = 60.0        # Laplacian variance on a 512-px image; lower = blurrier
DARK_MIN = 60.0        # mean brightness (HSV V, 0-255)
GLARE_MAX = 0.06       # fraction of near-white, low-saturation pixels

MESSAGES = {
    "BLURRY": "Photo is blurry. Hold the phone steady and tap to focus on the rash.",
    "TOO_DARK": "Photo is too dark. Move to daylight or turn on more lights.",
    "GLARE": "Too much glare. Avoid direct flash or shiny reflections.",
    "UNREADABLE": "Could not read this image. Please try another photo.",
}


def decode(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def check(bgr) -> dict:
    if bgr is None:
        return {"ok": False, "issues": [{"code": "UNREADABLE", "message": MESSAGES["UNREADABLE"]}], "metrics": {}}
    h, w = bgr.shape[:2]
    scale = 512 / max(h, w)
    img = cv2.resize(bgr, (int(w * scale), int(h * scale))) if scale < 1 else bgr
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(hsv[..., 2].mean())
    glare = float(((hsv[..., 2] > 240) & (hsv[..., 1] < 30)).mean())
    issues = []
    if blur < BLUR_MIN:
        issues.append("BLURRY")
    if bright < DARK_MIN:
        issues.append("TOO_DARK")
    if glare > GLARE_MAX:
        issues.append("GLARE")
    return {
        "ok": not issues,
        "issues": [{"code": c, "message": MESSAGES[c]} for c in issues],
        "metrics": {"blur": round(blur, 1), "brightness": round(bright, 1), "glare": round(glare, 3)},
    }
