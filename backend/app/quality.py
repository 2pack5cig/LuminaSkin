"""Photo quality gate: blur, darkness, glare. Thresholds are starting points; tune on real phone photos."""
import cv2
import numpy as np

BLUR_MIN = 30.0        # Laplacian variance at a fixed 256 px: 0.8% of 504 good photos rejected, 100% of out-of-focus caught
DARK_MIN = 50.0        # mean brightness; kept low so darker skin is not mistaken for a dark photo
GLARE_MAX = 0.05       # fraction of BLOWN-OUT pixels (all colour channels >= 250). Pale skin / vitiligo is not glare.

MESSAGES = {
    "BLURRY": "Photo is blurry. Hold the phone steady and tap to focus on the rash.",
    "TOO_DARK": "Photo is too dark. Move to daylight or turn on more lights.",
    "GLARE": "Some glare or shine in the photo. Results may be less reliable; a retake without flash may help.",
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
    # measured at a FIXED small size so enlarged low-resolution photos (and smooth skin) aren't punished
    g256 = cv2.cvtColor(cv2.resize(bgr, (256, 256), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(g256, cv2.CV_64F).var())
    bright = float(hsv[..., 2].mean())
    glare = float((img.min(axis=2) >= 250).mean())  # blown-out highlights only
    issues, warnings = [], []          # issues block analysis; warnings are shown with the result
    if blur < BLUR_MIN:
        issues.append("BLURRY")
    if bright < DARK_MIN:
        issues.append("TOO_DARK")
    if glare > GLARE_MAX:
        warnings.append("GLARE")
    return {
        "ok": not issues,
        "issues": [{"code": c, "message": MESSAGES[c]} for c in issues],
        "warnings": [{"code": c, "message": MESSAGES[c]} for c in warnings],
        "metrics": {"blur": round(blur, 1), "brightness": round(bright, 1), "glare": round(glare, 3)},
    }
