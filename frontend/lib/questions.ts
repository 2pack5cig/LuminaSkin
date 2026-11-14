// Question keys match SCIN column names (feature_spec.json) so the model sees the same features it was trained on.
// pus_oozing / rapid_spread, the "About the itch", "Safety check" and "About you" items are not in SCIN:
// they feed rule-based checks only (red flags, scabies screening, alerts) - never the AI.

export const DURATIONS: [string, string][] = [
  ["ONE_DAY", "1 day"],
  ["LESS_THAN_ONE_WEEK", "< 1 week"],
  ["ONE_TO_FOUR_WEEKS", "1–4 weeks"],
  ["ONE_TO_THREE_MONTHS", "1–3 months"],
  ["THREE_TO_TWELVE_MONTHS", "3–12 months"],
  ["MORE_THAN_ONE_YEAR", "> 1 year"],
  ["MORE_THAN_FIVE_YEARS", "> 5 years"],
  ["SINCE_CHILDHOOD", "Since childhood"],
];

export const GROUPS: { title: string; items: [string, string][] }[] = [
  {
    title: "Safety check (tap any that apply)",
    items: [
      ["lip_tongue_swelling", "Lips, tongue or eyelids swelling"],
      ["near_eye_nose", "On the eyelid, near the eye or tip of the nose"],
      ["spreading_red_hot", "Redness, heat and pain spreading fast"],
      ["numb_patch", "A patch feels numb / less sensitive to touch"],
      ["new_medicine", "Started a new medicine in the last 4 weeks"],
      ["steroid_cream", "Used a pharmacy or steroid cream on it (e.g. Betnovate, Panderm, Quadriderm, Fourderm)"],
    ],
  },
  {
    title: "About you",
    items: [
      ["is_child", "This is for a child (under 12)"],
      ["is_pregnant", "I am pregnant"],
    ],
  },
  {
    title: "What does the rash feel like?",
    items: [
      ["condition_symptoms_ITCHING", "Itchy"],
      ["condition_symptoms_BURNING", "Burning"],
      ["condition_symptoms_PAIN", "Painful"],
      ["condition_symptoms_BLEEDING", "Bleeding"],
      ["condition_symptoms_INCREASING_SIZE", "Getting bigger"],
      ["condition_symptoms_DARKENING", "Getting darker"],
    ],
  },
  {
    title: "What does it look like?",
    items: [
      ["textures_RAISED_OR_BUMPY", "Raised / bumpy"],
      ["textures_FLAT", "Flat"],
      ["textures_ROUGH_OR_FLAKY", "Rough / flaky"],
      ["textures_FLUID_FILLED", "Blisters (fluid-filled)"],
      ["pus_oozing", "Pus / oozing"],
      ["rapid_spread", "Spreading fast"],
    ],
  },
  {
    title: "About the itch",
    items: [
      ["itch_worse_night", "Worse at night"],
      ["household_itchy", "Others at home / close contacts itchy too"],
      ["lives_alone", "I live alone"],
      ["finger_wrist_spots", "Spots between fingers / on wrists"],
    ],
  },
  {
    title: "Any of these?",
    items: [
      ["other_symptoms_FEVER", "Fever"],
      ["other_symptoms_CHILLS", "Chills"],
      ["other_symptoms_FATIGUE", "Tiredness"],
      ["other_symptoms_JOINT_PAIN", "Joint pain"],
      ["other_symptoms_MOUTH_SORES", "Mouth sores"],
      ["other_symptoms_SHORTNESS_OF_BREATH", "Trouble breathing"],
    ],
  },
  {
    title: "Where on the body?",
    items: [
      ["body_parts_HEAD_OR_NECK", "Head / neck"],
      ["body_parts_ARM", "Arm"],
      ["body_parts_PALM", "Palm"],
      ["body_parts_BACK_OF_HAND", "Back of hand"],
      ["body_parts_TORSO_FRONT", "Chest / belly"],
      ["body_parts_TORSO_BACK", "Back"],
      ["body_parts_GENITALIA_OR_GROIN", "Groin"],
      ["body_parts_BUTTOCKS", "Buttocks"],
      ["body_parts_LEG", "Leg"],
      ["body_parts_FOOT_TOP_OR_SIDE", "Foot (top/side)"],
      ["body_parts_FOOT_SOLE", "Sole of foot"],
      ["body_parts_OTHER", "Other"],
    ],
  },
];

export const ALL_KEYS = GROUPS.flatMap((g) => g.items.map(([k]) => k));

export function labelFor(key: string) {
  for (const g of GROUPS) for (const [k, l] of g.items) if (k === key) return l;
  return key;
}

/** Pairs where choosing one un-chooses the other. */
export const EXCLUSIVE: Record<string, string> = { household_itchy: "lives_alone", lives_alone: "household_itchy" };
