"""Derm triage backend. Uses the real models when ml/models/ has them; otherwise demo (mock) results."""
import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from pydantic import BaseModel

from . import followups, medicines, models, quality, redflags

ROOT = Path(__file__).resolve().parent.parent
KB = json.loads((ROOT / "kb" / "clinical_kb.json").read_text())
DISCLAIMER = ("This is an AI triage aid, not a diagnosis. Always consult a qualified doctor, "
              "especially if symptoms are severe or getting worse.")
log = logging.getLogger("uvicorn.error")

PIPE = None
if models.available():
    log.info("Loading trained models...")
    PIPE = models.Pipeline()
    log.info("Models ready.")
else:
    log.warning("Trained models not found in ml/models - running in DEMO mode.")

app = FastAPI(title="LuminaSkin API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "mock": PIPE is None}


@app.post("/quality")
async def check_quality(image: UploadFile = File(...)):
    return quality.check(quality.decode(await image.read()))


def triage_text(label: str) -> dict:
    entry = KB.get(label) or {}
    return {
        "summary": entry.get("summary", "No information available for this condition yet."),
        "contagious": entry.get("contagious"),
        "steroid_warning": entry.get("steroid_warning"),
        "soothing_care": entry.get("soothing_care", []),
        "see_doctor_when": entry.get("see_doctor_when", []),
    }


def mock_predict(symptoms: dict) -> dict:
    answered = any(v not in (None, "", False) for v in symptoms.values())
    return {
        "ood": {"rejected": False, "reason": None},
        "top3": [{"label": "Tinea", "prob": 0.62}, {"label": "Eczema", "prob": 0.21}, {"label": "Psoriasis", "prob": 0.09}],
        "uncertain": False,
        "contributions": {"image": 0.7, "symptoms": 0.3} if answered else None,
        "symptoms_used": answered,
        "heatmap_png_b64": None,
    }


@app.post("/analyze")
async def analyze(images: list[UploadFile] = File(...), symptoms: str = Form("{}"), shots: str = Form("[]")):
    """images: 1-5 photos of the same rash, close-up first. shots: matching list like ["close_up","angle","distance"]."""
    sym = json.loads(symptoms or "{}")
    shot_list = json.loads(shots or "[]")
    bgrs = [quality.decode(await f.read()) for f in images[:5]]
    checks = [quality.check(b) for b in bgrs]
    good = [i for i, c in enumerate(checks) if c["ok"]]
    q = dict(checks[good[0]] if good else checks[0])
    q["skipped_photos"] = [{"index": i, "shot": shot_list[i] if i < len(shot_list) else None, "issues": c["issues"]}
                           for i, c in enumerate(checks) if not c["ok"]] if good else []
    flags = redflags.evaluate(sym)  # always runs, even if the photo is rejected
    scab = redflags.scabies_screen(sym)  # clinical-history rule; runs regardless of the AI
    if scab["positive"]:
        e = KB.get("Scabies", {})
        scab.update(summary=e.get("summary"), contagious=e.get("contagious"), steroid_warning=e.get("steroid_warning"),
                    soothing_care=e.get("soothing_care", []), see_doctor_when=e.get("see_doctor_when", []))
    alerts = redflags.core_alerts(sym)  # leprosy / steroid / child / pregnancy cards, no AI needed
    base = {"quality": q, "red_flags": flags, "scabies": scab, "alerts": alerts, "followups": [],
            "disclaimer": DISCLAIMER, "mock": PIPE is None}
    if not q["ok"]:
        scab["prominent"] = True
        return {**base, "ood": {"rejected": False, "reason": None}, "top3": None, "uncertain": False,
                "contributions": None, "symptoms_used": False, "heatmap_png_b64": None, "triage": None}

    if PIPE:
        pred = await run_in_threadpool(PIPE.run_multi, [bgrs[i] for i in good], sym)
        if pred.get("heatmap_photo") is not None:
            pred["heatmap_photo"] = good[pred["heatmap_photo"]]  # index in the photos the user sent
    else:
        pred = {**mock_predict(sym), "photos_used": len(good), "heatmap_photo": good[0]}
    if not pred["top3"]:
        scab["prominent"] = True
        return {**base, **pred, "display": None, "triage": None}
    display, triage = group_dermatitis(pred["top3"])
    if PIPE and display[0].get("members"):  # confident about the eczema family as a whole?
        pred["uncertain"] = display[0]["prob"] < PIPE.p_min
    # AI confident about something else -> smaller "also consider" note; otherwise full card
    scab["prominent"] = bool(pred["uncertain"] or display[0]["label"] == "Scabies")
    if pred["uncertain"]:
        triage = None
    elif triage is None:
        triage = triage_text(display[0]["label"])
    labels = [t["label"] for t in pred["top3"]]
    if "Herpes Zoster" in labels and sym.get("condition_duration") in ("ONE_DAY", "LESS_THAN_ONE_WEEK"):
        alerts.append({"kind": "zoster72", "level": "urgent", "title": "If this could be shingles, see a doctor within 72 hours",
                       "text": "Antiviral tablets work best when started within 3 days of the rash appearing."})
    if sym.get("steroid_cream") and set(labels) & {"Tinea", "Eczema", "Psoriasis", "Contact Dermatitis"}:
        for a in alerts:
            if a["kind"] == "steroid":
                a["text"] += " Because steroid cream was used, the AI's result for these look-alike conditions is less reliable."
    base["followups"] = followups.pick(labels, bool(sym.get("is_child")))
    base["medicine_warning"] = medicines.warning(labels, sym)   # fixed rule, not AI
    if pred["uncertain"]:   # no condition-specific reasons when the AI isn't confident (they'd read like a diagnosis)
        base["medicine_warning"]["reasons"] = []
    return {**base, **pred, "display": display, "triage": triage}


class HintRequest(BaseModel):
    top_labels: list[str]
    answers: dict[str, str]


@app.post("/hints")
def get_hints(req: HintRequest):
    """Follow-up answers -> hints. Never changes the AI's ranking (it isn't even sent here)."""
    return followups.hints(req.top_labels, req.answers, KB)


DERM_FAMILY = ("Eczema", "Contact Dermatitis")
GROUP_LABEL = "Dermatitis (eczema family)"
CONTACT_TIP = {"tip": "If it started after a new soap, cream, detergent, jewellery or hair dye, it may be contact "
                      "dermatitis: stop using that product.", "caution": None}


def group_dermatitis(top3):
    """Eczema + Contact Dermatitis both in the top 3 -> one combined 'eczema family' entry (probabilities add)."""
    members = [t for t in top3 if t["label"] in DERM_FAMILY]
    if len(members) < 2:
        return [dict(t) for t in top3], None
    group = {"label": GROUP_LABEL, "prob": round(sum(m["prob"] for m in members), 3), "members": members}
    display = sorted([group] + [t for t in top3 if t["label"] not in DERM_FAMILY], key=lambda t: -t["prob"])
    ecz, cd = triage_text("Eczema"), triage_text("Contact Dermatitis")
    triage = {
        "summary": "Eczema and contact dermatitis are both part of the eczema (dermatitis) family: inflamed, itchy "
                   "skin. " + ecz["summary"].split(". ", 1)[-1] + " Contact dermatitis is caused by something "
                   "touching the skin, so finding and avoiding the trigger is key.",
        "contagious": "No.",
        "steroid_warning": ecz["steroid_warning"],
        "soothing_care": [c for c in ecz["soothing_care"]] +
                         [c for c in cd["soothing_care"] if c["tip"] not in {x["tip"] for x in ecz["soothing_care"]}][:2],
        "see_doctor_when": list(dict.fromkeys(ecz["see_doctor_when"] + cd["see_doctor_when"]))[:5],
    }
    return display, triage
