"""Spot tracker: measure a mole/spot or a rash patch from a phone photo with a coin for scale, and compare with
the previous check. Classical image measurement (no new AI model). Not a diagnosis.

Coin sizes differ by series (e.g. older stainless-steel Rs1 = 25 mm, new Rs1 = 20 mm), so the user picks coin + series
or types the diameter. Presets: new series Rs1 20, Rs2 23, Rs5 25, Rs10 27 mm; older Rs1 25 mm.
"""
import base64

import cv2
import numpy as np

COINS_MM = {"1": 20.0, "2": 23.0, "5": 25.0, "10": 27.0, "1_old": 25.0}


def coin_mm(value: str) -> float:
    """Preset key ('1', '2', '5', '10', '1_old') or a diameter in mm typed by the user (e.g. '25' or '21.9')."""
    if value in COINS_MM:
        return COINS_MM[value]
    try:
        v = float(value)
        return v if 10 <= v <= 40 else 23.0
    except ValueError:
        return 23.0


# ---------------------------------------------------------------- coin
def find_coin(bgr, avoid_xy=None):
    """Largest plausible circle (coin) via Hough transform. Returns (x, y, r) in pixels or None."""
    h, w = bgr.shape[:2]
    g = cv2.medianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 5)
    cands = []
    for p1, p2 in ((110, 38), (70, 32), (55, 24)):   # strict first, then more sensitive (low-contrast coins)
        c = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=w // 8, param1=p1, param2=p2,
                             minRadius=int(w * 0.04), maxRadius=int(w * 0.42))
        if c is not None:
            cands += c[0][:5].tolist()
    if not cands:
        return None
    edge = cv2.dilate(cv2.Canny(g, 40, 120), np.ones((9, 9), np.uint8))  # tolerate a few px of radius error
    best = None
    for x, y, r in cands:
        if avoid_xy is not None and np.hypot(x - avoid_xy[0], y - avoid_xy[1]) < r:  # don't pick the spot itself
            continue
        ring = cv2.circle(np.zeros((h, w), np.uint8), (int(x), int(y)), int(r), 255, 2)
        support = (edge[ring > 0] > 0).mean()  # how much of the circle follows a real edge
        if best is None or support > best[3]:
            best = (float(x), float(y), float(r), support)
    return best[:3] if best and best[3] > 0.35 else None


# ---------------------------------------------------------------- lesion
def _plane(win, mask):
    """Least-squares plane per Lab channel through the masked pixels: models uneven lighting across the window."""
    hh, ww = win.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww]
    A = np.c_[xx[mask], yy[mask], np.ones(mask.sum())].astype(np.float32)
    out = np.empty_like(win)
    for ch in range(3):
        coef, *_ = np.linalg.lstsq(A, win[..., ch][mask], rcond=None)
        out[..., ch] = coef[0] * xx + coef[1] * yy + coef[2]
    return out


def segment(bgr, tap_xy, coin=None):
    """Outline of the tapped spot, robust to uneven lighting and multi-coloured spots:
    1) skin colour modelled as a smooth plane fitted to the window border (removes lighting gradients),
    2) contrast = Lab distance from that local skin colour,
    3) spot = connected region around the tap with contrast >= HALF of the spot's core contrast
       (measures the spot itself, not the faint shading around it). Works for dark moles and light patches."""
    h, w = bgr.shape[:2]
    lab = cv2.cvtColor(cv2.GaussianBlur(bgr, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    tx, ty = int(tap_xy[0]), int(tap_xy[1])
    results = []
    for frac in (0.06, 0.12, 0.2, 0.32, 0.45):  # grow the window until the spot fits inside it
        R = max(int(w * frac), 24)
        x0, y0, x1, y1 = max(0, tx - R), max(0, ty - R), min(w, tx + R), min(h, ty + R)
        win = lab[y0:y1, x0:x1]
        valid = np.ones(win.shape[:2], np.uint8)
        if coin is not None:
            cv2.circle(valid, (int(coin[0] - x0), int(coin[1] - y0)), int(coin[2] * 1.15), 0, -1)
        valid = valid.astype(bool)
        b = max(4, R // 12)
        border = np.zeros(win.shape[:2], bool)
        border[:b], border[-b:], border[:, :b], border[:, -b:] = True, True, True, True
        ref = border & valid
        if ref.sum() < 40:
            continue
        skin = _plane(win, ref)
        diff = win - skin
        d = np.sqrt((diff[..., 0] * 1.0) ** 2 + (diff[..., 1] * 1.6) ** 2 + (diff[..., 2] * 1.6) ** 2)
        # spot core = strongest contrast near the tap (tolerates a tap a few px off-centre)
        r0 = max(3, int(w * 0.012))
        cy, cx = ty - y0, tx - x0
        core_win = d[max(0, cy - r0):cy + r0 + 1, max(0, cx - r0):cx + r0 + 1]
        core = float(np.percentile(core_win, 90))
        noise = float(np.percentile(d[ref], 90))
        if core < max(6.0, noise * 1.5):      # nothing distinct where the user tapped
            continue
        # two-level (hysteresis) threshold: strong core, extended into connected moderately-distinct pixels,
        # so multi-coloured spots stay whole while faint shading around the spot is left out
        strong = max(0.5 * core, noise * 1.2, 5.0)
        weak = max(0.25 * core, noise * 1.6, 5.0)
        m = ((d >= weak) & valid).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n_, cc_ = cv2.connectedComponents(m)
        keep = np.unique(cc_[(d >= strong) & (m > 0)])
        m = np.isin(cc_, keep[keep > 0]).astype(np.uint8)
        n, cc = cv2.connectedComponents(m)
        if n <= 1:
            continue
        sub = cc[max(0, cy - r0):cy + r0 + 1, max(0, cx - r0):cx + r0 + 1]
        ids = sub[sub > 0]
        if ids.size == 0:
            continue
        comp = (cc == np.bincount(ids).argmax()).astype(np.uint8)
        full = np.zeros((h, w), np.uint8)
        full[y0:y1, x0:x1] = comp
        touches = comp[:b].any() or comp[-b:].any() or comp[:, :b].any() or comp[:, -b:].any()
        results.append((full, touches))
    # A small window can sit entirely INSIDE a big spot (then its 'skin' is really the spot). So take the first
    # non-touching result whose area is confirmed by the next larger window (changes < 25%).
    ok = [r for r, t in results if not t]
    best = None
    for a, b2 in zip(ok, ok[1:]):
        if abs(int(b2.sum()) - int(a.sum())) <= 0.25 * max(int(a.sum()), 1):
            best = a
            break
    if best is None and ok:
        best = max(ok, key=lambda r: int(r.sum())) if len(ok) > 1 else ok[0]
    if best is None and results:
        best = results[-1][0]
    if best is None or best.sum() < 6:
        return None
    cnts, _ = cv2.findContours(best, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    filled = cv2.drawContours(np.zeros_like(best), [c], -1, 1, -1)
    return filled, c


def colour_count(bgr, mask):
    """Number of distinct colour groups inside the spot (k-means 4 in Lab, groups >=8% that differ by dE >= 12)."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)[mask > 0]
    if len(lab) < 40:
        return 1
    _, lbl, ctr = cv2.kmeans(lab, 4, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5), 3,
                             cv2.KMEANS_PP_CENTERS)
    share = np.bincount(lbl.ravel(), minlength=4) / len(lbl)
    keep = [ctr[i] for i in range(4) if share[i] >= 0.08]
    groups = []
    for c in keep:
        if all(np.linalg.norm(c - g) >= 12 for g in groups):
            groups.append(c)
    return max(1, len(groups))


def asymmetry(mask):
    """Mismatch when the shape is flipped across its two main axes (0 = perfectly symmetric)."""
    ys, xs = np.nonzero(mask)
    pts = np.c_[xs, ys].astype(np.float32)
    mean = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - mean, full_matrices=False)
    rot = (pts - mean) @ vt.T
    s = max(np.abs(rot).max(), 1)
    size = 201
    grid = np.zeros((size, size), np.uint8)
    q = np.clip(((rot / s) * 100 + 100).round().astype(int), 0, size - 1)
    grid[q[:, 1], q[:, 0]] = 1
    grid = cv2.morphologyEx(grid, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    a = grid.sum()
    return float(max((grid ^ grid[:, ::-1]).sum(), (grid ^ grid[::-1, :]).sum()) / (2 * a)) if a else 0.0


def measure(bgr, tap_xy, coin_mm, coin_px=None):
    """Returns metrics in real units (if a coin is found) + outline for display."""
    h, w = bgr.shape[:2]
    coin = None
    if coin_px is not None:  # user tapped two opposite coin edges -> (x, y, r)
        coin = coin_px
    else:
        coin = find_coin(bgr, avoid_xy=tap_xy)
    seg = segment(bgr, tap_xy, coin)
    if seg is None:
        return {"ok": False, "reason": "spot_not_found"}
    mask, contour = seg
    area_px = float(mask.sum())
    perim = float(cv2.arcLength(contour, True))
    (cx, cy), (rw, rh), _ = cv2.minAreaRect(contour)
    mm_per_px = (coin_mm / (2 * coin[2])) if coin else None
    eq_diam_px = 2 * np.sqrt(area_px / np.pi)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    ring = cv2.dilate(mask, np.ones((25, 25), np.uint8)) - mask
    dL = float(lab[..., 0][mask > 0].mean() - lab[..., 0][ring > 0].mean()) if ring.sum() else 0.0
    m = {
        "ok": True,
        "coin_found": coin is not None,
        "coin": [round(float(v), 1) for v in coin] if coin else None,
        "scale_mm_per_px": mm_per_px,
        "area_mm2": round(area_px * mm_per_px ** 2, 1) if coin else None,
        "diameter_mm": round(max(rw, rh) * mm_per_px, 1) if coin else None,
        "eq_diameter_mm": round(eq_diam_px * mm_per_px, 1) if coin else None,
        "area_pct_of_photo": round(100 * area_px / (h * w), 2),
        "colours": colour_count(bgr, mask),
        "irregularity": round(perim ** 2 / (4 * np.pi * area_px), 2),   # 1.0 = perfect circle
        "asymmetry": round(asymmetry(mask), 2),
        "lightness_vs_skin": round(dL, 1),                              # <0 darker than skin, >0 lighter
        "outline": (contour.reshape(-1, 2)[:: max(1, len(contour) // 120)] / [w, h]).round(4).tolist(),
    }
    return m


# ---------------------------------------------------------------- compare
def compare(kind: str, location: str, prev: dict, now: dict, similarity):
    """Change assessment between two checks. kind: 'spot' (mole/spot) or 'rash'."""
    # 'same spot?' threshold calibrated on SCIN photo pairs: at 0.5, 5% of same-spot pairs are flagged, 72% of different spots caught
    out = {"changes": [], "alerts": [], "verdict": "no_change", "similarity": similarity}
    different = similarity is not None and similarity < 0.50
    same_note = ("This photo looks quite different from last time. Make sure it's the same spot, photographed the same way "
                 "(same distance, daylight, coin beside it).")
    if not (prev.get("ok") and now.get("ok")):
        if different:
            out["alerts"].append(same_note); out["verdict"] = "check_same_spot"
        return out
    both_scaled = prev.get("eq_diameter_mm") is not None and now.get("eq_diameter_mm") is not None
    if both_scaled:
        d0, d1 = prev["eq_diameter_mm"], now["eq_diameter_mm"]
        a0, a1 = prev["area_mm2"], now["area_mm2"]
        dd, da = d1 - d0, (a1 - a0) / max(a0, 1e-6)
        out["changes"].append({"what": "Size", "before": f"{d0:.1f} mm", "now": f"{d1:.1f} mm",
                               "delta": f"{dd:+.1f} mm ({da*100:+.0f}% area)"})
    else:
        da = (now["area_pct_of_photo"] - prev["area_pct_of_photo"]) / max(prev["area_pct_of_photo"], 1e-6)
        dd = None
        out["changes"].append({"what": "Size (no coin, approximate)", "before": f"{prev['area_pct_of_photo']}% of photo",
                               "now": f"{now['area_pct_of_photo']}% of photo", "delta": f"{da*100:+.0f}%"})
    out["changes"].append({"what": "Colours", "before": str(prev["colours"]), "now": str(now["colours"]),
                           "delta": f"{now['colours'] - prev['colours']:+d}"})
    out["changes"].append({"what": "Outline unevenness", "before": f"{prev['irregularity']:.2f}", "now": f"{now['irregularity']:.2f}",
                           "delta": f"{(now['irregularity'] - prev['irregularity']) / prev['irregularity'] * 100:+.0f}%"})

    if kind == "spot":
        grew = (dd is not None and (dd >= 1.0 or (da >= 0.20 and dd >= 0.7))) or (dd is None and da >= 0.30)
        if grew:
            out["alerts"].append("The spot has grown since last time.")
        if now["colours"] > prev["colours"]:
            out["alerts"].append("New colour shades have appeared in the spot.")
        if now["irregularity"] > prev["irregularity"] * 1.15 or now["asymmetry"] > prev["asymmetry"] + 0.10:
            out["alerts"].append("The outline has become more uneven or less symmetric.")
        if both_scaled and now["eq_diameter_mm"] > 6 and prev["eq_diameter_mm"] <= 6:
            out["alerts"].append("The spot is now larger than 6 mm.")
        if location in ("palm", "sole", "nail") and (grew or now["colours"] > prev["colours"]):
            out["alerts"].append("A changing dark spot on the palm, sole or nail should always be checked by a doctor.")
        if out["alerts"]:
            out["verdict"] = "changed_see_doctor"
        elif different:
            out["verdict"] = "check_same_spot"
    else:  # rash / patch: treatment progress
        if da <= -0.10:
            out["verdict"] = "smaller"
        elif da >= 0.25:
            out["verdict"] = "bigger_see_doctor"
            out["alerts"].append("The patch has grown by a quarter or more. If you're on treatment, show this to your doctor.")
        elif da >= 0.10:
            out["verdict"] = "bigger"
        else:
            out["verdict"] = "check_same_spot" if different else "about_same"
    if different:
        out["alerts"].append(same_note)   # always last, as a gentle reminder
    return out


def emb_to_b64(e):
    return base64.b64encode(np.asarray(e, np.float16).tobytes()).decode()


def emb_from_b64(s):
    return np.frombuffer(base64.b64decode(s), np.float16).astype(np.float32)


def overlay_png(bgr, m):
    """Photo with the measured outline (teal) and coin (dashed ink) for the user to confirm."""
    img = bgr.copy()
    h, w = img.shape[:2]
    if m.get("outline"):
        pts = (np.array(m["outline"]) * [w, h]).astype(np.int32)
        cv2.polylines(img, [pts], True, (88, 95, 11), 3, cv2.LINE_AA)
    if m.get("coin"):
        x, y, r = m["coin"]
        cv2.circle(img, (int(x), int(y)), int(r), (230, 239, 243), 3, cv2.LINE_AA)
        cv2.circle(img, (int(x), int(y)), int(r), (15, 19, 22), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", cv2.resize(img, (512, 512)), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode()


# ---------------------------------------------------------------- concern bar (moles / spots only)
# Clinical basis: AAD "ABCDEs of melanoma": Asymmetry (halves don't match); Border jagged/scalloped/ill-defined;
# Colour uneven (tan, brown, black, or patches of white, red, blue); Diameter usually > 6 mm, but melanomas can be
# smaller (2-22% under 6 mm in studies); Evolving: changing size/shape/colour, a spot that looks unlike the others
# ("ugly duckling"), bleeding, crusting, itching, or a sore that doesn't heal. Evolution is the strongest sign.
# Phone measurements of border/asymmetry are noisy, so only CLEAR values count. Not a cancer test.
A_THR, B_THR, C_THR, D_MM = 0.35, 1.6, 3, 6.0


def concern(location: str, now: dict, prev: dict | None = None, symptoms: dict | None = None) -> dict:
    if not now.get("ok"):
        return None
    sym = symptoms or {}
    acral = location in ("palm", "sole", "nail")
    d = now.get("eq_diameter_mm")
    d_long = now.get("diameter_mm")
    A = now["asymmetry"] >= A_THR
    B = now["irregularity"] >= B_THR
    C = now["colours"] >= C_THR
    D = (d_long or d or 0) > D_MM if (d_long or d) is not None else False
    abcd = sum([A, B, C, D])
    checklist = [
        {"letter": "A", "label": "Asymmetry", "warn": A, "detail": "halves don't match" if A else "roughly symmetric"},
        {"letter": "B", "label": "Border", "warn": B, "detail": "uneven or jagged edge" if B else "fairly smooth edge"},
        {"letter": "C", "label": "Colour", "warn": C, "detail": f"{now['colours']} different shades" if C else f"{now['colours']} shade{'s' if now['colours'] > 1 else ''}"},
        {"letter": "D", "label": "Diameter",
         "warn": D, "detail": (f"{d_long or d} mm across (over 6 mm)" if D else f"{d_long or d} mm across (melanomas can still be smaller)")
         if (d_long or d) is not None else "no coin, size unknown"},
    ]
    why, pts = [], 0
    for item, w in ((A, 12), (B, 12), (C, 15), (D, 15)):
        pts += w if item else 0
    if A: why.append("asymmetric shape")
    if B: why.append("uneven or jagged border")
    if C: why.append(f"{now['colours']} different colours")
    if D: why.append(f"larger than 6 mm ({d_long or d} mm)")
    if acral:
        pts += 10; why.append("on a palm, sole or under a nail")

    # ---- E: evolution (measured change) + symptoms the user reports ----
    e_change, e_items = False, []
    if prev and prev.get("ok"):
        if d is not None and prev.get("eq_diameter_mm") is not None:
            dd = d - prev["eq_diameter_mm"]
            if dd >= 1.0:
                e_change = True; pts += 35; e_items.append(f"grew {dd:+.1f} mm"); why.append(f"grew {dd:+.1f} mm since last check")
            elif dd >= 0.5:
                pts += 12; e_items.append(f"may have grown {dd:+.1f} mm (near measurement error)")
                why.append(f"may have grown {dd:+.1f} mm (recheck)")
        elif (now["area_pct_of_photo"] - prev["area_pct_of_photo"]) / max(prev["area_pct_of_photo"], 1e-6) >= 0.3:
            e_change = True; pts += 30; e_items.append("looks bigger (no coin)"); why.append("looks bigger than last time (no coin, approximate)")
        new_c = now["colours"] - prev["colours"]
        if new_c > 0:
            e_change = True; pts += 25; e_items.append(f"{new_c} new colour{'s' if new_c > 1 else ''}"); why.append(f"{new_c} new colour{'s' if new_c > 1 else ''}")
        if now["irregularity"] > prev["irregularity"] * 1.15 or now["asymmetry"] > prev["asymmetry"] + 0.10:
            e_change = True; pts += 15; e_items.append("shape/border changed"); why.append("outline became more uneven or less symmetric")
    bleed = bool(sym.get("bleeds"))          # bleeds, crusts, or a sore that doesn't heal
    itch = bool(sym.get("itches"))
    ugly = bool(sym.get("ugly_duckling"))    # looks different from your other moles
    if bleed: pts += 35; e_items.append("bleeds / crusts / won't heal"); why.append("bleeds, crusts or doesn't heal")
    if itch: pts += 15; e_items.append("itchy or painful"); why.append("itchy or painful")
    if ugly: pts += 20; e_items.append("looks unlike your other moles"); why.append("looks different from your other moles ('ugly duckling')")
    first = not (prev and prev.get("ok"))
    checklist.append({"letter": "E", "label": "Evolving", "warn": bool(e_change or bleed or itch or ugly),
                      "detail": ", ".join(e_items) if e_items else ("first check - recheck to see change" if first else "no change measured")})

    # ---- level: clinical rules first, the score only fills the bar ----
    if e_change or bleed or abcd >= 2 or (acral and (abcd >= 1 or itch or ugly)):
        level = "high"
    elif abcd == 1 or itch or ugly or acral or any("may have grown" in w for w in why):
        level = "medium"
    else:
        level = "low"
    score = int(min(100, pts))
    score = max(score, 65) if level == "high" else max(min(score, 59), 35) if level == "medium" else min(score, 29)
    return {"score": score, "level": level, "reasons": why, "checklist": checklist,
            "note": "Based on the ABCDE warning signs doctors use. Not a cancer test: melanomas can be small or look ordinary, "
                    "so see a doctor anytime a spot worries you."}
