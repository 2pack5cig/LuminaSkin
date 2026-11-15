export type Issue = { code: string; message: string };
export type Care = { tip: string; caution: string | null };
export type Shot = "close_up" | "angle" | "distance" | "extra_close_up";
export type Photo = { blob: Blob; dataUrl: string; shot: Shot };
export type Ranked = { label: string; prob: number; members?: { label: string; prob: number }[] };

export type Alert = { kind: string; level: "urgent" | "soon" | "info"; title: string; text: string };
export type FollowUp = { id: string; text: string };
export type AlsoConsider = {
  name: string; covered_by_ai: boolean; reasons: string[]; severity: number;
  summary?: string; contagious?: string | null; soothing_care?: Care[]; see_doctor_when?: string[];
};
export type Hints = { fits: { label: string; reasons: string[] }[]; also_consider: AlsoConsider[]; alerts: string[]; note: string };

export type MedicineWarning = {
  show: boolean; level: "danger" | "warn"; title: string; why: string; reasons: string[];
  medicines: { name: string; examples: string }[]; already_used: boolean; used_text: string | null; do_instead: string;
};

export type AnalyzeResult = {
  quality: { ok: boolean; issues: Issue[]; warnings?: Issue[]; metrics: Record<string, number>; skipped_photos?: { index: number; shot: Shot | null; issues: Issue[] }[] };
  ood: { rejected: boolean; reason: "NOT_SKIN" | "OUT_OF_DISTRIBUTION" | null; unusual?: boolean };
  red_flags: { urgent: boolean; level: "emergency" | "urgent" | "soon" | null; reasons: string[] };
  scabies?: {
    positive: boolean; prominent?: boolean; reasons: string[]; basis: string;
    summary?: string; contagious?: string; steroid_warning?: string; soothing_care?: Care[]; see_doctor_when?: string[];
  };
  top3: { label: string; prob: number }[] | null;
  display?: Ranked[] | null;
  uncertain: boolean;
  contributions: { image: number; symptoms: number } | null;
  symptoms_used: boolean;
  heatmap_png_b64: string | null;
  heatmap_photo?: number;
  photos_used?: number;
  triage: {
    summary: string;
    contagious: string | null;
    steroid_warning: string | null;
    soothing_care: Care[];
    see_doctor_when: string[];
  } | null;
  disclaimer: string;
  mock?: boolean;
  alerts?: Alert[];
  medicine_warning?: MedicineWarning;
  followups?: FollowUp[];
  hints?: Hints;
  followup_answers?: Record<string, string>;
};

export type Answers = {
  skipped: boolean;
  bools: Record<string, boolean>;
  condition_duration: string | null;
  itch: number; // 0-5, tracker/PDF only (not a model input)
  pain: number; // 0-5, tracker/PDF only
};

export type Scan = {
  id: string;
  date: string; // ISO
  thumb: string; // small JPEG data URL
  photoThumbs?: { thumb: string; shot: Shot }[]; // all photos, small JPEGs (for the doctor PDF / history)
  heatmapThumb?: string; // close-up with the Grad-CAM++ overlay, small JPEG
  answers: Answers;
  result: AnalyzeResult;
};

// ---------------------------------------------------------------- spot tracker
export type SpotKind = "spot" | "rash";
export type SpotMetrics = {
  ok: boolean; reason?: string; coin_found: boolean; coin: number[] | null;
  area_mm2: number | null; diameter_mm: number | null; eq_diameter_mm: number | null; area_pct_of_photo: number;
  colours: number; irregularity: number; asymmetry: number; lightness_vs_skin: number; outline: number[][];
};
export type SpotComparison = {
  verdict: "no_change" | "changed_see_doctor" | "check_same_spot" | "smaller" | "about_same" | "bigger" | "bigger_see_doctor";
  changes: { what: string; before: string; now: string; delta: string }[];
  alerts: string[]; similarity: number | null;
};
export type SpotConcern = {
  score: number; level: "low" | "medium" | "high"; reasons: string[]; note: string;
  checklist?: { letter: string; label: string; warn: boolean; detail: string }[];
};
export type SpotCheck = {
  date: string; overlay: string; photo: string; metrics: SpotMetrics; embedding: string | null; comparison: SpotComparison | null;
  concern?: SpotConcern | null;
};
export type Spot = {
  id: string; name: string; kind: SpotKind; location: string; coin: string; created: string; nextDue: string; checks: SpotCheck[];
};
