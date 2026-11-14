"use client";
import { useState } from "react";
import CaptureStep from "@/components/CaptureStep";
import QuestionsStep from "@/components/QuestionsStep";
import ResultView from "@/components/ResultView";
import { analyze } from "@/lib/api";
import { thumbnail } from "@/lib/image";
import { doctorPdf } from "@/lib/pdf";
import { saveScan } from "@/lib/storage";
import type { Photo, Scan } from "@/lib/types";

export default function Home() {
  const [photos, setPhotos] = useState<Photo[] | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const reset = () => { setPhotos(null); setScan(null); setError(null); setSaved(false); };

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
            setScan({ id, date: new Date().toISOString(), thumb: await thumbnail(photos[0].dataUrl), answers, result });
          } catch {
            setError("Couldn't reach the analysis server. Check the laptop is running and try again.");
          } finally { setBusy(false); }
        }} />
        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
      </>
    );
  }

  const usable = scan.result.quality.ok && !scan.result.ood.rejected;
  return (
    <div className="pt-4 space-y-4">
      {(scan.result.photos_used ?? 1) > 1 && (
        <p className="text-xs text-black/50">Result combines {scan.result.photos_used} photos of the same rash.</p>
      )}
      {(scan.result.quality.skipped_photos?.length ?? 0) > 0 && (
        <p className="text-xs text-amber-800">{scan.result.quality.skipped_photos!.length} photo(s) were too blurry, dark or glary and were not used.</p>
      )}
      <ResultView r={scan.result} photo={photos[scan.result.heatmap_photo ?? 0].dataUrl} />
      <div className="grid grid-cols-2 gap-3">
        {usable && (
          <button disabled={saved} onClick={async () => { await saveScan(scan); setSaved(true); }}
            className="rounded-2xl border border-brand text-brand py-3 disabled:opacity-60">
            {saved ? "Saved ✓" : "Save to my scans"}
          </button>
        )}
        {usable && <button onClick={() => doctorPdf(scan)} className="rounded-2xl bg-brand text-white py-3">Doctor PDF</button>}
        <button onClick={reset} className="col-span-2 rounded-2xl border py-3">New scan</button>
      </div>
    </div>
  );
}
