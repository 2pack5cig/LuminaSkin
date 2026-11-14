"use client";
import { useEffect, useState } from "react";
import { deleteScan, listScans } from "@/lib/storage";
import { doctorPdf } from "@/lib/pdf";
import type { Scan } from "@/lib/types";

export default function History() {
  const [scans, setScans] = useState<Scan[] | null>(null);
  useEffect(() => { listScans().then(setScans); }, []);

  if (!scans) return null;
  return (
    <div className="pt-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">My scans</h1>
        <p className="text-sm text-black/60">Saved only on this phone. Compare how the rash changes over time.</p>
      </div>
      {scans.length === 0 && <p className="text-black/60">No saved scans yet.</p>}
      {scans.map((s, i) => {
        const top = (s.result.display ?? s.result.top3)?.[0];
        const prev = scans[i + 1];
        return (
          <div key={s.id} className="rounded-2xl bg-white border p-3 flex gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={s.thumb} alt="" className="w-20 h-20 rounded-xl object-cover" />
            <div className="flex-1 text-sm">
              <p className="font-medium">{new Date(s.date).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</p>
              <p>{s.result.uncertain ? "Not confident" : top ? `${top.label} (${Math.round(top.prob * 100)}%)` : "-"}</p>
              <p className="text-black/60">Itch {s.answers.itch}/5 · Pain {s.answers.pain}/5
                {prev && ` (was ${prev.answers.itch}/5 · ${prev.answers.pain}/5)`}</p>
              {s.result.red_flags.urgent && <p className="text-red-700">Red flag noted</p>}
              <div className="flex gap-4 mt-1">
                <button className="text-brand" onClick={() => doctorPdf(s)}>PDF</button>
                <button className="text-black/40" onClick={async () => { await deleteScan(s.id); setScans(await listScans()); }}>Delete</button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
