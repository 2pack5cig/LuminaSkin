"use client";
import { useState } from "react";
import CaptureStep from "@/components/CaptureStep";
import QuestionsStep from "@/components/QuestionsStep";
import FollowUpStep from "@/components/FollowUpStep";
import ResultView from "@/components/ResultView";
import { analyze, getHints } from "@/lib/api";
import { heatmapOverlay, thumbnail } from "@/lib/image";
import { doctorPdf } from "@/lib/pdf";
import { saveScan } from "@/lib/storage";
import type { Photo, Scan } from "@/lib/types";

export default function Home() {
  const [photos, setPhotos] = useState<Photo[] | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [askFollowUps, setAskFollowUps] = useState(false);

  const reset = () => { setPhotos(null); setScan(null); setError(null); setSaved(false); setAskFollowUps(false); };

  if (!photos) return <CaptureStep onDone={setPhotos} />;

  if (!scan) {
    return (
      <>
        <QuestionsStep preview={photos[0].dataUrl} busy={busy} onSubmit={async (answers) => {
          setBusy(true); setError(null);
          try {
            const result = await analyze(photos, answers);
            // crypto.randomUUID only exists on HTTPS/localhost; phones on plain http://<laptop-ip> need a fallback
            const id = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
            const photoThumbs = await Promise.all(photos.map(async (p) => ({ thumb: await thumbnail(p.dataUrl), shot: p.shot })));
            const heatmapThumb = result.heatmap_png_b64
              ? await heatmapOverlay(photos[result.heatmap_photo ?? 0].dataUrl, result.heatmap_png_b64) : undefined;
            setScan({ id, date: new Date().toISOString(), thumb: photoThumbs[0].thumb, photoThumbs, heatmapThumb, answers, result });
            setAskFollowUps((result.followups?.length ?? 0) > 0);
          } catch {
            setError("Couldn't reach the analysis server. Check the laptop is running and try again.");
          } finally { setBusy(false); }
        }} />
        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
      </>
    );
  }

  if (askFollowUps && scan.result.followups) {
    return (
      <>
        <FollowUpStep questions={scan.result.followups} busy={busy} onDone={async (fa) => {
          setBusy(true); setError(null);
          try {
            const labels = (scan.result.top3 ?? []).map((t) => t.label);
            const hints = Object.keys(fa).length ? await getHints(labels, fa) : undefined;
            setScan({ ...scan, result: { ...scan.result, hints, followup_answers: fa } });
            setAskFollowUps(false);
          } catch {
            setError("Couldn't reach the analysis server. Check the laptop is running and try again.");
          } finally { setBusy(false); }
        }} />
        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
      </>
    );
  }

  const usable = scan.result.quality.ok && !scan.result.ood.rejected;
  const notes = [
    ...(scan.result.quality.ok ? (scan.result.quality.warnings ?? []).map((w) => w.message) : []),
    ...((scan.result.quality.skipped_photos?.length ?? 0) > 0
      ? [`${scan.result.quality.skipped_photos!.length} photo(s) were too blurry or dark and were not used.`] : []),
  ];
  return (
    <ResultView
      r={scan.result}
      photo={photos[scan.result.heatmap_photo ?? 0].dataUrl}
      meta={notes.length > 0 && <div className="mt-3 space-y-1">{notes.map((n) => <p key={n} className="text-sm text-[#9A5212]">{n}</p>)}</div>}
      actions={
        <div className="rule-top grid gap-3 pt-6 sm:grid-cols-2">
          {usable && (
            <button onClick={() => doctorPdf(scan)} className="btn btn-accent">
              Doctor PDF <span className="font-mono font-normal">↓</span>
            </button>
          )}
          {usable && (
            <button disabled={saved} onClick={async () => { await saveScan(scan); setSaved(true); }} className="btn btn-ghost">
              {saved ? "Saved to my scans ✓" : "Save to my scans"}
            </button>
          )}
          <button onClick={reset} className={`btn btn-ink ${usable ? "sm:col-span-2" : ""}`}>New scan <span className="font-mono font-normal">→</span></button>
        </div>
      }
    />
  );
}
