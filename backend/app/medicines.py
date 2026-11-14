"""Self-medication warning (fixed rule, not AI). Shown on every analysed scan as a red banner.

Real-world problem in India: steroid / 'combination' creams and antibiotic tablets bought over the counter
without a prescription. Steroids make fungal infections and scabies spread (tinea incognito) and thin the skin;
antibiotics don't treat eczema, fungal or viral rashes, cause resistance, and penicillin can cause severe allergy.
Doctors DO prescribe steroid creams for some conditions (eczema, psoriasis) - so the rule is "never without a
prescription", not "never".
"""

STEROID_EXAMPLES = "Betnovate / Betnovate-N / Betnovate-C, Lobate / Lobate-GM, Panderm, Quadriderm, Fourderm, other 'clobetasol' or 'betamethasone' creams"
ANTIBIOTIC_EXAMPLES = "penicillin, amoxicillin, azithromycin, ciprofloxacin tablets or injections"

# conditions where these medicines actively make things worse -> specific reason
WORSE = {
    "Tinea": "Steroid creams make ringworm spread, change its look so it's harder to diagnose, and keep it coming back.",
    "Tinea Versicolor": "Steroid creams can make this fungal infection spread.",
    "Scabies": "Steroid creams hide the itch while the mites keep spreading, to you and your family.",
    "Impetigo": "Steroid creams make bacterial skin infections worse; this usually needs a doctor-prescribed antibiotic.",
    "Herpes Simplex": "Steroid creams can make this viral infection spread; antibiotics don't work on viruses.",
    "Herpes Zoster": "Steroid creams don't treat shingles and antibiotics don't work on viruses; antiviral tablets from a doctor do.",
    "Acne": "Steroid and 'fairness' creams cause or worsen acne (steroid acne).",
    "Folliculitis": "Steroid creams can make follicle infections worse.",
    "Eczema": "Steroid creams for eczema must be the right strength, for the right time, on a doctor's advice. Antibiotics don't treat eczema.",
    "Contact Dermatitis": "Strong steroid creams used without advice can damage the skin. Antibiotics don't treat this.",
    "Psoriasis": "Strong steroid creams used without advice can make psoriasis flare when stopped.",
    "Urticaria": "Antibiotics don't treat hives, and penicillin itself is a common cause of allergic hives.",
    "Insect Bite": "Antibiotics are not needed unless a doctor finds an infection.",
    "Vitiligo": "Steroid and 'fairness' creams used on your own can thin and damage the skin.",
    "Pityriasis Rosea": "Antibiotics don't help; this usually settles by itself.",
}


def warning(top_labels: list, symptoms: dict) -> dict:
    labels = [l for l in top_labels if l in WORSE]
    reasons = [f"{l}: {WORSE[l]}" for l in labels[:2]]
    strong = any(l in ("Tinea", "Tinea Versicolor", "Scabies", "Impetigo", "Herpes Simplex", "Herpes Zoster", "Acne", "Folliculitis")
                 for l in top_labels[:3])
    used = bool(symptoms.get("steroid_cream"))
    return {
        "show": True,
        "level": "danger" if (strong or used) else "warn",
        "title": "Do not use these medicines without a doctor's prescription",
        "medicines": [
            {"name": "Steroid or 'combination' creams", "examples": STEROID_EXAMPLES},
            {"name": "Antibiotic tablets or injections", "examples": ANTIBIOTIC_EXAMPLES},
            {"name": "Steroid tablets or injections", "examples": "prednisolone, dexamethasone, 'quick relief' injections"},
        ],
        "why": "Medicines bought from a nearby shop without a check-up often make skin infections spread, hide the real problem, "
               "cause antibiotic resistance, and can cause serious allergic reactions (especially penicillin).",
        "reasons": reasons,
        "already_used": used,
        "used_text": "You said you've used a steroid or pharmacy cream: stop using it now and show this report to a doctor." if used else None,
        "do_instead": "See a doctor or ask a pharmacist to refer you. Take this report with you. Use only the Soothing Care tips until then.",
    }
