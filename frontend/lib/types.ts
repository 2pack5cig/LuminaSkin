export type Issue = { code: string; message: string };
export type Care = { tip: string; caution: string | null };
export type Shot = "close_up" | "angle" | "distance" | "extra_close_up";
export type Photo = { blob: Blob; dataUrl: string; shot: Shot };
export type Ranked = { label: string; prob: number; members?: { label: string; prob: number }[] };

export type AnalyzeResult = {
  quality: { ok: boolean; issues: Issue[]; metrics: Record<string, number>; skipped_photos?: { index: number; shot: Shot | null; issues: Issue[] }[] };
  ood: { rejected: boolean; reason: "NOT_SKIN" | "OUT_OF_DISTRIBUTION" | null };
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
  answers: Answers;
  result: AnalyzeResult;
};
