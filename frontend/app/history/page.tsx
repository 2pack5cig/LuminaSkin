"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { deleteScan, listScans } from "@/lib/storage";
import { doctorPdf } from "@/lib/pdf";
import type { Scan } from "@/lib/types";
import { nice } from "@/lib/questions";

const pct = (p: number) => (p < 0.01 ? "<1%" : `${Math.round(p * 100)}%`);
const trend = (now: number, before?: number) =>
  before === undefined ? "" : now < before ? "↓ better" : now > before ? "↑ worse" : "= same";

export default function History() {
  const [scans, setScans] = useState<Scan[] | null>(null);
  useEffect(() => { listScans().then(setScans); }, []);
  if (!scans) return null;

  return (
    <div className="pt-10 md:pt-16">
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div>
          <p className="eyebrow">My scans · stored only on this device</p>
          <h1 className="display mt-5">How your skin <em>is changing.</em></h1>
          <p className="lede mt-5 text-muted">Each saved scan keeps the photos, your answers and the result. Nothing is uploaded or stored on a server.</p>
        </div>
        <Link href="/scan" className="btn btn-ink">New scan <span className="font-mono font-normal">→</span></Link>
      </div>

      <div className="mt-10 rule-top">
        {scans.length === 0 && (
          <div className="py-16 text-center">
            <p className="font-serif text-[1.4rem]">No saved scans yet.</p>
            <p className="mt-2 text-muted">After a scan, tap <b>Save to my scans</b> to track it over time.</p>
          </div>
        )}
        {scans.map((s, i) => {
          const top = (s.result.display ?? s.result.top3)?.[0];
          const prev = scans[i + 1];
          const thumbs = s.photoThumbs?.length ? s.photoThumbs.map((p) => p.thumb) : [s.thumb];
          return (
            <article key={s.id} className="grid gap-4 border-b border-rule py-6 sm:grid-cols-[150px_minmax(0,1fr)_auto] sm:items-center sm:gap-8">
              <div className="flex gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.heatmapThumb ?? thumbs[0]} alt="" className="h-24 w-24 rounded-[2px] object-cover sm:h-[110px] sm:w-[110px]" />
                <div className="flex flex-col gap-2 sm:hidden">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {thumbs.slice(1, 3).map((t, j) => <img key={j} src={t} alt="" className="h-11 w-11 rounded-[2px] object-cover" />)}
                </div>
              </div>
              <div>
                <p className="num">{new Date(s.date).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }).toUpperCase()}
                  {" · "}{new Date(s.date).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</p>
                <p className="mt-1 font-serif text-[1.35rem] leading-tight">
                  {s.result.uncertain ? "Not confident" : top ? nice(top.label) : "No result"}
                  {top && !s.result.uncertain && <span className="ml-2 font-mono text-[0.9rem] text-muted">{pct(top.prob)}</span>}
                </p>
                <p className="mt-1 text-[0.95rem] text-muted">
                  Itch {s.answers.itch}/5 <span className="font-mono text-[0.8rem]">{trend(s.answers.itch, prev?.answers.itch)}</span>
                  {"  ·  "}Pain {s.answers.pain}/5 <span className="font-mono text-[0.8rem]">{trend(s.answers.pain, prev?.answers.pain)}</span>
                </p>
                {s.result.red_flags.urgent && <p className="mt-1 font-mono text-[0.75rem] uppercase tracking-[0.08em] text-[#B01C1C]">Red flag noted</p>}
              </div>
              <div className="flex gap-3 sm:flex-col sm:items-stretch">
                <button className="btn btn-ghost btn-sm" onClick={() => doctorPdf(s)}>Doctor PDF</button>
                <button className="btn btn-sm border-rule text-muted hover:border-foreground hover:text-foreground"
                  onClick={async () => { await deleteScan(s.id); setScans(await listScans()); }}>Delete</button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
