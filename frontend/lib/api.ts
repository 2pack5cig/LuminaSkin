import type { AnalyzeResult, Answers, Hints, Photo } from "./types";
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

export async function getHints(topLabels: string[], answers: Record<string, string>): Promise<Hints> {
  const res = await fetch("/api/hints", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ top_labels: topLabels, answers }),
  });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

export type MeasureResponse = {
  ok: boolean; reason?: string; metrics?: import("./types").SpotMetrics; overlay_jpg_b64?: string;
  embedding?: string | null; comparison?: import("./types").SpotComparison | null;
  concern?: import("./types").SpotConcern | null;
};

/** Measure a tracked spot (tap = fractions 0-1 of the image). prev = previous check for comparison. */
export async function measureSpot(image: Blob, tap: { x: number; y: number }, opts: {
  coin: string; kind: string; location: string; coinEdges?: number[]; prev?: { metrics: unknown; embedding: string | null } | null;
  symptoms?: Record<string, boolean>;
}): Promise<MeasureResponse> {
  const fd = new FormData();
  fd.append("image", image, "spot.jpg");
  fd.append("tap_x", String(tap.x)); fd.append("tap_y", String(tap.y));
  fd.append("coin", opts.coin); fd.append("kind", opts.kind); fd.append("location", opts.location);
  if (opts.coinEdges) fd.append("coin_edges", opts.coinEdges.join(","));
  if (opts.prev) fd.append("prev", JSON.stringify(opts.prev));
  fd.append("symptoms", JSON.stringify(opts.symptoms ?? {}));
  const res = await fetch("/api/spot/measure", { method: "POST", body: fd });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}
