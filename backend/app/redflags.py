"""Deterministic red-flag rules. Runs on every request, before and independent of the AI. Never cut."""

# (level, condition on symptoms, reason shown to user)
# level: "emergency" > "urgent" > "soon"
RULES = [
    ("emergency", lambda s: s.get("other_symptoms_SHORTNESS_OF_BREATH"),
     "Difficulty breathing with a rash can be a serious allergic reaction. Seek emergency care now."),
    ("urgent", lambda s: s.get("other_symptoms_MOUTH_SORES"),
     "Mouth sores with a skin rash can signal a severe drug or immune reaction. See a doctor today."),
    ("urgent", lambda s: s.get("other_symptoms_FEVER") and (s.get("rapid_spread") or s.get("condition_symptoms_INCREASING_SIZE")),
     "Fever with a spreading rash needs a doctor's check today."),
    ("urgent", lambda s: s.get("pus_oozing") and s.get("other_symptoms_FEVER"),
     "Pus or oozing with fever may mean a spreading infection. See a doctor today."),
    ("urgent", lambda s: s.get("textures_FLUID_FILLED") and s.get("other_symptoms_FEVER"),
     "Blisters with fever should be checked by a doctor today."),
    ("soon", lambda s: s.get("rapid_spread"),
     "The rash is spreading quickly. See a doctor within 24 hours."),
    ("soon", lambda s: s.get("pus_oozing"),
     "Pus or oozing may mean infection. See a doctor within 24-48 hours."),
    ("soon", lambda s: s.get("condition_symptoms_BLEEDING"),
     "A bleeding skin spot should be checked by a doctor."),
]
ORDER = {"emergency": 3, "urgent": 2, "soon": 1, None: 0}


def evaluate(symptoms: dict) -> dict:
    hits = [(lvl, msg) for lvl, cond, msg in RULES if cond(symptoms)]
    level = max((lvl for lvl, _ in hits), key=ORDER.get, default=None)
    return {
        "urgent": ORDER[level] >= 2,
        "level": level,
        "reasons": [msg for _, msg in hits],
    }


# ---------- Scabies screening (clinical-history rule, NOT the AI) ----------
# Photos alone rarely show scabies; doctors rely on history: itch + close contacts itchy + night itch / typical sites.
SCABIES_REASONS = {
    "itch_worse_night": "itch is worse at night",
    "household_itchy": "others at home are itchy too",
    "finger_wrist_spots": "spots between fingers or on wrists",
}


def scabies_screen(s: dict) -> dict:
    itchy = bool(s.get("condition_symptoms_ITCHING"))
    household = bool(s.get("household_itchy"))
    typical = bool(s.get("itch_worse_night") or s.get("finger_wrist_spots"))
    positive = itchy and household and typical
    reasons = (["itchy rash"] + [v for k, v in SCABIES_REASONS.items() if s.get(k)]) if positive else []
    return {"positive": positive, "reasons": reasons, "basis": "Clinical screening criteria, not the AI"}
