"""Post-prediction follow-up questions and HINTS.

Rules of the game (safety):
- Questions are chosen from the AI's top 3; max 4 per scan.
- Answers NEVER change the AI's ranking, percentages or "not confident" flag. They only add hints:
    "fits"            -> a condition already in the top 3 that the answer supports (with the reason)
    "also_consider"   -> a condition the AI ranked low / doesn't cover (max 2, most serious first), with an info card
- Only "yes" counts. "no" and "not sure" change nothing.
These are standard clinical clues, shown as hints - not validated in this app.
"""
import json
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent / "kb"
UNCOVERED = json.loads((KB_DIR / "uncovered_kb.json").read_text())

# id: question text, supports (covered conditions), also (conditions to suggest if not in top 3), reason shown to user
QUESTIONS = {
    "ring_edge": dict(text="Does the patch have a raised edge with clearer-looking skin in the middle (like a ring)?",
                      supports=["Tinea"], reason="ring-shaped patch with a raised edge"),
    "new_product": dict(text="Did it start 1–3 days after using something new on the skin (soap, detergent, cream, jewellery, hair dye, plant)?",
                        supports=["Contact Dermatitis"], reason="started after a new product"),
    "herald_patch": dict(text="Did it start with one bigger oval patch, followed 1–2 weeks later by smaller spots on the chest or back?",
                         supports=["Pityriasis Rosea"], reason="one larger 'herald' patch came first"),
    "silvery_scale": dict(text="Are the scales thick and silvery-white?", supports=["Psoriasis"], reason="thick silvery scales"),
    "atopy": dict(text="Do you or close family have asthma, hay fever, or eczema since childhood?",
                  supports=["Eczema"], reason="personal or family history of allergies / eczema"),
    "greasy_dandruff": dict(text="Are there greasy flakes on the scalp (dandruff), eyebrows or sides of the nose?",
                            also=["Seborrheic dermatitis"], reason="greasy flakes on scalp / eyebrows / nose"),
    "tingle_before": dict(text="Did that exact spot burn, tingle or ache 1–2 days before the bumps appeared?",
                          supports=["Herpes Simplex", "Herpes Zoster"], reason="burning or tingling before the rash"),
    "one_side_band": dict(text="Are the blisters only on ONE side of the body or face, in a band or stripe?",
                          supports=["Herpes Zoster"], reason="one-sided band of blisters"),
    "both_sides_spread": dict(text="Are itchy spots or blisters spreading over BOTH sides of the body (face, chest, back)?",
                              also=["Chickenpox"], reason="itchy blisters spreading over both sides of the body"),
    "recurs_same_spot": dict(text="Has it come back in the same spot before (e.g. the lip)?",
                             supports=["Herpes Simplex"], reason="keeps coming back in the same spot"),
    "honey_crust": dict(text="Are there yellow, honey-coloured crusts (often near the nose or mouth)?",
                        supports=["Impetigo"], reason="honey-coloured crusts"),
    "blackheads": dict(text="Are there blackheads or whiteheads in the same area?", supports=["Acne"],
                       reason="blackheads / whiteheads nearby"),
    "hair_center": dict(text="Is there a hair in the centre of the bumps (especially after shaving, waxing or sweating)?",
                        supports=["Folliculitis"], reason="hair in the centre of the bumps"),
    "heat_sweat": dict(text="Did tiny prickly bumps appear after heat or heavy sweating, on covered skin?",
                       also=["Heat rash (miliaria)"], reason="tiny prickly bumps after heat / sweating"),
    "bite_marks": dict(text="Can you see a tiny bite mark in the centre, or bumps in lines/groups on uncovered skin?",
                       supports=["Insect Bite"], reason="bite marks or bumps in lines on uncovered skin"),
    "welts_24h": dict(text="Does each welt fade completely within 24 hours while new ones appear elsewhere?",
                      supports=["Urticaria"], reason="each welt fades within 24 hours"),
    "welts_long": dict(text="Do welts last MORE than a day in the same place, or leave bruise-like marks?",
                       alert="Welts that last over 24 hours or leave bruises can be a different, more serious condition (urticarial vasculitis). Please see a doctor.",
                       reason="welts last over a day"),
    "fine_scale_heat": dict(text="Does the patch show a fine, dusty scale when lightly scratched, and get more noticeable in hot, humid weather?",
                            supports=["Tinea Versicolor"], reason="fine dusty scale, worse in humid weather"),
    "milk_white": dict(text="Is the patch completely milk-white with no flaking at all?",
                       supports=["Vitiligo"], also_covered=["Vitiligo"], reason="milk-white patch with no flaking"),
    "child_face_pale": dict(text="Is this a child with faint pale, slightly dry patches on the face?", child_only=True,
                            also=["Pityriasis alba"], reason="faint pale dry patches on a child's face"),
    "kp_bumps": dict(text="Are these tiny, rough, painless bumps (like goosebumps) on the upper arms, thighs or cheeks, present for months or years?",
                     also=["Keratosis pilaris"], reason="tiny rough painless bumps on arms/thighs for months"),
    "stuck_on_growth": dict(text="Is it a waxy, raised brown or black spot that looks 'stuck on' the skin?",
                            also=["Seborrheic keratosis"], reason="waxy 'stuck-on' brown/black spot"),
    "palms_soles_mouth": dict(text="Does the child also have spots on the palms or soles AND sores in the mouth?", child_only=True,
                              also=["Hand-foot-mouth disease"], reason="spots on palms/soles with mouth sores"),
}

# which questions to ask for each AI condition (most useful first)
BY_CLASS = {
    "Tinea": ["ring_edge", "new_product", "silvery_scale"],
    "Eczema": ["atopy", "new_product", "ring_edge"],
    "Contact Dermatitis": ["new_product", "atopy", "ring_edge"],
    "Psoriasis": ["silvery_scale", "greasy_dandruff", "stuck_on_growth", "ring_edge"],
    "Pityriasis Rosea": ["herald_patch", "ring_edge"],
    "Herpes Zoster": ["one_side_band", "both_sides_spread", "tingle_before"],
    "Herpes Simplex": ["recurs_same_spot", "tingle_before", "honey_crust"],
    "Impetigo": ["honey_crust", "both_sides_spread", "palms_soles_mouth"],
    "Insect Bite": ["bite_marks", "welts_24h", "kp_bumps", "heat_sweat"],
    "Urticaria": ["welts_24h", "welts_long", "bite_marks"],
    "Folliculitis": ["hair_center", "kp_bumps", "blackheads", "heat_sweat"],
    "Acne": ["blackheads", "kp_bumps", "hair_center", "stuck_on_growth"],
    "Tinea Versicolor": ["fine_scale_heat", "milk_white", "child_face_pale"],
    "Vitiligo": ["milk_white", "fine_scale_heat", "child_face_pale"],
    "Scabies": ["bite_marks", "atopy"],
}
MAX_Q = 4


def pick(top_labels: list, is_child: bool) -> list:
    """2-4 questions for this scan: #1's questions first, then #2, #3. Child-only questions only for children."""
    out = []
    for rnd in range(3):  # take the best question of each top-3 condition, round-robin
        for lab in top_labels:
            qs = [q for q in BY_CLASS.get(lab, []) if is_child or not QUESTIONS[q].get("child_only")]
            if rnd < len(qs) and qs[rnd] not in out:
                out.append(qs[rnd])
            if len(out) >= MAX_Q:
                return [{"id": q, "text": QUESTIONS[q]["text"]} for q in out]
    return [{"id": q, "text": QUESTIONS[q]["text"]} for q in out]


def hints(top_labels: list, answers: dict, kb: dict) -> dict:
    """answers: {question_id: "yes" | "no" | "unsure"}. Only "yes" counts. Never changes the AI's ranking."""
    yes = [q for q, a in answers.items() if a == "yes" and q in QUESTIONS]
    fits, also, alerts = {}, {}, []
    for q in yes:
        spec = QUESTIONS[q]
        for lab in spec.get("supports", []):
            if lab in top_labels:
                fits.setdefault(lab, []).append(spec["reason"])
        for name in spec.get("also", []):
            info = UNCOVERED[name]
            also.setdefault(name, {"name": name, "covered_by_ai": False, "reasons": [], "severity": info["severity"], **info})
            also[name]["reasons"].append(spec["reason"])
        for lab in spec.get("also_covered", []):
            if lab not in top_labels and lab in kb:
                also.setdefault(lab, {"name": lab, "covered_by_ai": True, "reasons": [], "severity": 2, **kb[lab]})
                also[lab]["reasons"].append(spec["reason"])
        if spec.get("alert"):
            alerts.append(spec["alert"])
    also_list = sorted(also.values(), key=lambda a: -a["severity"])[:2]
    return {
        "fits": [{"label": k, "reasons": v} for k, v in fits.items()],
        "also_consider": also_list,
        "alerts": alerts,
        "note": "Hints come from your answers (standard clinical clues). They do not change the AI's ranking and are not a diagnosis.",
    }
