"""Deterministic red-flag rules. Runs on every request, before and independent of the AI. Never cut."""

# (level, condition on symptoms, reason shown to user)
# level: "emergency" > "urgent" > "soon"
RULES = [
    ("emergency", lambda s: s.get("lip_tongue_swelling"),
     "Swelling of the lips, tongue or eyelids can be a severe allergic reaction. Seek emergency care now."),
    ("emergency", lambda s: s.get("new_medicine") and (s.get("other_symptoms_FEVER") or s.get("other_symptoms_MOUTH_SORES")
                                                       or s.get("textures_FLUID_FILLED")),
     "A new medicine with fever, mouth sores or blisters can be a severe drug reaction. Stop and seek emergency care now."),
    ("urgent", lambda s: s.get("near_eye_nose"),
     "A rash on the eyelid, near the eye or on the tip of the nose can affect the eye (especially shingles). See a doctor today."),
    ("urgent", lambda s: s.get("spreading_red_hot"),
     "Fast-spreading redness, heat and throbbing pain can be a skin infection (cellulitis). See a doctor today."),
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
    ("soon", lambda s: s.get("condition_symptoms_INCREASING_SIZE") and (s.get("condition_symptoms_BLEEDING") or s.get("condition_symptoms_DARKENING")),
     "A spot that is growing and bleeding or darkening should be checked by a doctor to rule out skin cancer."),
    ("soon", lambda s: s.get("new_medicine"),
     "A rash after a new medicine may be a drug reaction. Tell the doctor who prescribed it."),
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
    "household_itchy": "others at home / close contacts are itchy too",
    "lives_alone": "lives alone (both typical signs present)",
    "finger_wrist_spots": "spots between fingers or on wrists",
}


def scabies_screen(s: dict) -> dict:
    """IACS-style history: itch + close contacts itchy + typical features. Living alone: the contact clue can't
    apply, so BOTH typical features are required instead."""
    itchy = bool(s.get("condition_symptoms_ITCHING"))
    night, sites = bool(s.get("itch_worse_night")), bool(s.get("finger_wrist_spots"))
    if s.get("lives_alone"):
        positive = itchy and night and sites
    else:
        positive = itchy and bool(s.get("household_itchy")) and (night or sites)
    reasons = (["itchy rash"] + [v for k, v in SCABIES_REASONS.items() if s.get(k)]) if positive else []
    return {"positive": positive, "reasons": reasons, "basis": "Clinical screening criteria, not the AI"}


# ---------- background alerts that need no AI (shown as cards) ----------
def core_alerts(s: dict) -> list:
    a = []
    if s.get("numb_patch"):
        a.append({"kind": "leprosy", "level": "soon", "title": "A numb patch needs a doctor's check",
                  "text": "Reduced feeling in a pale or reddish patch is the main sign doctors check for leprosy. It is fully "
                          "curable, and testing and treatment are free at government health centres in India. Please see a doctor soon."})
    if s.get("steroid_cream"):
        a.append({"kind": "steroid", "level": "info", "title": "Stop steroid creams until a doctor checks the rash",
                  "text": "Steroid and 'combination' creams can disguise ringworm so it looks like eczema, make it spread and "
                          "keep coming back. They can also cause acne and thin the skin."})
    if s.get("is_child"):
        a.append({"kind": "child", "level": "info", "title": "For a child",
                  "text": "Children's rashes can look different and change fast. Use this only as a guide and see a doctor, "
                          "especially if the child has a fever, is unusually sleepy, or isn't drinking."})
    if s.get("is_pregnant"):
        a.append({"kind": "pregnancy", "level": "soon", "title": "During pregnancy",
                  "text": "Please don't use creams or tablets without asking your doctor, and get any new rash checked - some "
                          "(like chickenpox or pityriasis rosea) need extra care in pregnancy."})
    return a
