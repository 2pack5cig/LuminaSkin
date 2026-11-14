"""Build the negatives test set (photos that are NOT one of our 15 conditions).

g1_*  not skin at all              (Wikimedia Commons, free licences)
g2_*  skin-like look-alikes        (Wikimedia Commons)
g3_*  real skin, other condition   (SCIN + DermaCon-IN photos of OTHER diagnoses - never used in training;
                                    + Commons photos of healthy skin, tattoo, mehendi, scar)
g4_*  bad-quality photos           (blurred / dark / glare versions made from real photos)
Writes ml/data/negatives/*.jpg and ml/data/negatives/sources.csv (source + licence for every photo).
"""
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "negatives"
UA = {"User-Agent": "LuminaSkinHackathon/1.0 (student research test set; non-commercial)"}
rng = np.random.default_rng(0)

COMMONS = {  # group: {short name: search query}
    "g1": {"mug": "coffee mug on table", "keyboard": "laptop keyboard close-up", "remote": "television remote control",
           "bottle": "plastic water bottle", "keys": "house keys", "wall": "painted wall texture", "tiles": "floor tiles",
           "table": "wooden table top", "bedsheet": "bed sheet fabric", "carpet": "carpet texture", "cardboard": "cardboard box",
           "roti": "chapati roti", "dal": "dal lentil curry bowl", "rice": "cooked rice bowl", "orange": "orange fruit",
           "banana": "banana fruit", "leaf": "green leaf close-up", "grass": "grass lawn close-up", "flower": "marigold flower",
           "bark": "tree bark texture", "dogfur": "dog fur close-up", "catfur": "cat fur close-up", "kurta": "printed cotton fabric india",
           "towel": "bath towel texture", "soil": "soil ground close-up"},
    "g2": {"leather": "brown leather texture", "woodspoon": "wooden spoon", "sand": "sand texture close-up",
           "dough": "wheat dough", "peanutbutter": "peanut butter", "tomato": "tomato close-up", "strawberry": "strawberry close-up",
           "redcloth": "red cloth texture", "mannequin": "mannequin hand", "chickenskin": "raw chicken skin"},
    "g3": {"healthyarm": "human forearm skin", "hand": "back of human hand", "palm": "human palm hand", "tattoo": "arm tattoo",
           "mehendi": "mehndi henna hand", "scar": "scar on skin", "mole": "mole on skin", "nails": "fingernails close-up"},
}


def commons_search(query, n=1):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
                                "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
                                "iiurlwidth": 900})
    data = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers=UA), timeout=30).read())
    out = []
    for p in sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
        out.append({"url": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl"), "license": lic, "title": p["title"]})
        if len(out) >= n:
            break
    return out


def save(img_bgr, name, rows, **meta):
    cv2.imwrite(str(OUT / name), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    rows.append({"file": name, **meta})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    # ---- Groups 1-3 from Wikimedia Commons ----
    for g, items in COMMONS.items():
        for short, query in items.items():
            try:
                hits = commons_search(query)
                if not hits:
                    print("  no result:", query); continue
                h = hits[0]
                raw = urllib.request.urlopen(urllib.request.Request(h["url"], headers=UA), timeout=30).read()
                img = cv2.cvtColor(np.array(Image.open(io.BytesIO(raw)).convert("RGB")), cv2.COLOR_RGB2BGR)
                save(img, f"{g}_{short}_01.jpg", rows, group=g, source="Wikimedia Commons", license=h["license"], link=h["page"], note=h["title"])
                time.sleep(0.3)
            except Exception as e:  # noqa: BLE001
                print("  failed:", query, e)
    # ---- Group 3: real patient photos of OTHER conditions (never used in training) ----
    d = pd.read_csv(ROOT / "data" / "dermacon" / "Skin_Metadata.csv")
    used = {r for rs in json.loads((ROOT / "data" / "dermacon_map.json").read_text())["map"].values() for r in rs}
    files = {p.name: p for p in (ROOT / "data" / "dermacon" / "images").rglob("*.jpg")}
    other = ["Melasma", "Alopecia Areata", "Lichen Planus", "Wart", "Candidal Intertrigo", "Seborrheic Dermatitis", "Keloid",
             "Nevocytic nevus", "Post-Inflammatory hyperpigmentation", "Xerosis", "Acrochordon", "Pityriasis Alba",
             "Onychomycosis", "Palmoplantar Keratoderma", "Dermatosis Papulosa Nigra"]
    for lab in other:
        assert lab not in used
        r = d[(d.Disease_label == lab) & d.Image_name.isin(files)].sample(1, random_state=0).iloc[0]
        save(cv2.imread(str(files[r.Image_name])), f"g3_dcn_{lab.lower().replace(' ', '').replace('-', '')[:18]}_01.jpg", rows,
             group="g3", source="DermaCon-IN (other diagnosis, not used in training)", license="CC BY-NC-SA 4.0", link="doi:10.7910/DVN/W7OUZM", note=lab)
    # ---- Group 4: bad-quality versions of real photos ----
    base = [OUT / r["file"] for r in rows if r["group"] in ("g3",)][:3] + [OUT / r["file"] for r in rows if r["group"] == "g1"][:2]
    for i, p in enumerate(base):
        img = cv2.imread(str(p))
        if img is None:
            continue
        variants = {"blurry": cv2.GaussianBlur(img, (0, 0), 7), "dark": (img * 0.18).astype(np.uint8)}
        g = img.copy(); h, w = g.shape[:2]
        cv2.circle(g, (w // 2, h // 2), min(h, w) // 3, (255, 255, 255), -1); variants["glare"] = cv2.GaussianBlur(g, (0, 0), 15)
        for k, v in variants.items():
            save(v, f"g4_{k}_{i+1:02d}.jpg", rows, group="g4", source=f"made from {p.name}", license="as source", link="", note=k)
    pd.DataFrame(rows).to_csv(OUT / "sources.csv", index=False)
    print(pd.DataFrame(rows).groupby("group").size().to_dict(), "total", len(rows))


if __name__ == "__main__":
    main()
