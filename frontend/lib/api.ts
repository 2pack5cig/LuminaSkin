import type { AnalyzeResult, Answers, Photo } from "./types";
import { ALL_KEYS } from "./questions";

// Model input: if the user skipped, send {} so the backend uses image-only mode.
// Otherwise every question is answered (unselected chip = false).
export function symptomsPayload(a: Answers): Record<string, unknown> {
  if (a.skipped) return {};
  const out: Record<string, unknown> = {};
  for (const k of ALL_KEYS) out[k] = !!a.bools[k];
  if (a.condition_duration) out.condition_duration = a.condition_duration;
  return out;
}

export async function analyze(photos: Photo[], a: Answers): Promise<AnalyzeResult> {
  const fd = new FormData();
  photos.forEach((p, i) => fd.append("images", p.blob, `rash-${i}.jpg`));
  fd.append("shots", JSON.stringify(photos.map((p) => p.shot)));
  fd.append("symptoms", JSON.stringify(symptomsPayload(a)));
  const res = await fetch("/api/analyze", { method: "POST", body: fd });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}
