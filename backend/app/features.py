"""Shared symptom feature spec. Used by ml/ training scripts AND the backend, so features always match.

SCIN encodes each checkbox as "YES" or blank. A whole section blank = question skipped -> NaN.
The app sends keys like "condition_symptoms_ITCHING" (any case); they are lower-cased here.
"""
import numpy as np

SECTIONS = {
    "condition_symptoms": ["bothersome_appearance", "bleeding", "increasing_size", "darkening", "itching",
                           "burning", "pain", "no_relevant_experience"],
    "other_symptoms": ["fever", "chills", "fatigue", "joint_pain", "mouth_sores", "shortness_of_breath",
                       "no_relevant_symptoms"],
    "textures": ["raised_or_bumpy", "flat", "rough_or_flaky", "fluid_filled"],
    "body_parts": ["head_or_neck", "arm", "palm", "back_of_hand", "torso_front", "torso_back",
                   "genitalia_or_groin", "buttocks", "leg", "foot_top_or_side", "foot_sole", "other"],
}
NONE_FLAG = {"condition_symptoms": "no_relevant_experience", "other_symptoms": "no_relevant_symptoms"}
DURATIONS = ["ONE_DAY", "LESS_THAN_ONE_WEEK", "ONE_TO_FOUR_WEEKS", "ONE_TO_THREE_MONTHS",
             "THREE_TO_TWELVE_MONTHS", "MORE_THAN_ONE_YEAR", "MORE_THAN_FIVE_YEARS", "SINCE_CHILDHOOD"]

COLUMNS = [f"{s}_{k}" for s, ks in SECTIONS.items() for k in ks]
FEATURE_NAMES = COLUMNS + ["duration_ordinal", "answered"]
N_FEATURES = len(FEATURE_NAMES)


def _section_block(values: dict, section: str):
    keys = [f"{section}_{k}" for k in SECTIONS[section]]
    if not any(k in values for k in keys):
        return [np.nan] * len(keys), False
    block = [1.0 if values.get(k) else 0.0 for k in keys]
    flag = NONE_FLAG.get(section)
    if flag and sum(block) == 0:  # answered the section but ticked nothing = "none of these"
        block[keys.index(f"{section}_{flag}")] = 1.0
    return block, True


def featurize(answers: dict) -> np.ndarray:
    """answers from the app: {"condition_symptoms_ITCHING": true, ..., "condition_duration": "ONE_DAY"}. {} = skipped."""
    vals = {k.lower(): v for k, v in answers.items() if k.lower() in COLUMNS and v is not None}
    row, any_answered = [], False
    for s in SECTIONS:
        block, answered = _section_block(vals, s)
        row += block
        any_answered |= answered
    d = answers.get("condition_duration")
    row.append(float(DURATIONS.index(d)) if d in DURATIONS else np.nan)
    any_answered |= d in DURATIONS
    row.append(1.0 if any_answered else 0.0)
    return np.array(row, dtype=np.float32)


def featurize_scin_row(r) -> np.ndarray:
    """Same features from a SCIN cases.csv row (pandas Series)."""
    answers = {}
    for s in SECTIONS:
        cols = [f"{s}_{k}" for k in SECTIONS[s]]
        if any(str(r.get(c)) == "YES" for c in cols):  # section answered
            answers.update({c: str(r.get(c)) == "YES" for c in cols})
    if r.get("condition_duration") in DURATIONS:
        answers["condition_duration"] = r["condition_duration"]
    return featurize(answers)
