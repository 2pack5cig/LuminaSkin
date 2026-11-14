"use client";
import { useState } from "react";
import { DURATIONS, EXCLUSIVE, GROUPS } from "@/lib/questions";
import type { Answers } from "@/lib/types";

const SCALE = ["None", "Mild", "", "Moderate", "", "Severe"];

/** Step 2: yes/no taps (SCIN-aligned for the AI) + safety / background questions (rules only). */
export default function QuestionsStep({ preview, onSubmit, busy }:
  { preview: string; onSubmit: (a: Answers) => void; busy: boolean }) {
  const [bools, setBools] = useState<Record<string, boolean>>({});
  const [duration, setDuration] = useState<string | null>(null);
  const [itch, setItch] = useState(0);
  const [pain, setPain] = useState(0);
  const toggle = (k: string) => setBools((b) => ({ ...b, [k]: !b[k], ...(EXCLUSIVE[k] && !b[k] ? { [EXCLUSIVE[k]]: false } : {}) }));
  const submit = (skipped: boolean) =>
    onSubmit({ skipped, bools: skipped ? {} : bools, condition_duration: skipped ? null : duration, itch, pain });
  const count = Object.values(bools).filter(Boolean).length + (duration ? 1 : 0);

  const Section = ({ n, title, children }: { n: number; title: string; children: React.ReactNode }) => (
    <section className="grid gap-3 border-b border-rule py-6 md:grid-cols-[220px_1fr] md:gap-8">
      <div className="flex items-baseline gap-3 md:block">
        <span className="num">{String(n).padStart(2, "0")}</span>
        <h2 className="font-serif text-[1.15rem] leading-snug md:mt-1">{title}</h2>
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </section>
  );

  return (
    <div className="pt-10 md:pt-16">
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div>
          <p className="eyebrow">Step 2 of 3 · Questions</p>
          <h1 className="display mt-5">A few quick <em>taps.</em></h1>
          <p className="lede mt-5 text-muted">Tap everything that applies. Leave the rest. The safety check runs on every scan, separately from the AI.</p>
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={preview} alt="Your close-up" className="h-24 w-24 rounded-[4px] object-cover md:h-32 md:w-32" />
      </div>

      <div className="mt-10 rule-top">
        <Section n={1} title="How long have you had it?">
          {DURATIONS.map(([k, l]) => (
            <button key={k} className={`chip ${duration === k ? "chip-on" : ""}`} onClick={() => setDuration(duration === k ? null : k)}>{l}</button>
          ))}
        </Section>
        {GROUPS.map((g, i) => (
          <Section key={g.title} n={i + 2} title={g.title}>
            {g.items.map(([k, l]) => (
              <button key={k} className={`chip ${bools[k] ? "chip-on" : ""}`} onClick={() => toggle(k)}>{l}</button>
            ))}
          </Section>
        ))}
        <section className="grid gap-3 border-b border-rule py-6 md:grid-cols-[220px_1fr] md:gap-8">
          <div className="flex items-baseline gap-3 md:block">
            <span className="num">{String(GROUPS.length + 2).padStart(2, "0")}</span>
            <h2 className="font-serif text-[1.15rem] leading-snug md:mt-1">How bad is it? <span className="text-muted text-sm font-sans">(for your tracker)</span></h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            {([["Itch", itch, setItch], ["Pain / burning", pain, setPain]] as const).map(([l, v, set]) => (
              <label key={l} className="block">
                <span className="flex justify-between text-sm"><span>{l}</span><span className="num">{v}/5 {SCALE[v] && `· ${SCALE[v].toUpperCase()}`}</span></span>
                <input type="range" min={0} max={5} value={v} onChange={(e) => set(Number(e.target.value))} className="mt-2 w-full accent-[#16130F]" />
              </label>
            ))}
          </div>
        </section>
      </div>

      <div className="sticky bottom-0 z-[5] -mx-5 mt-8 border-t border-rule bg-background/95 px-5 py-4 backdrop-blur sm:-mx-8 sm:px-8 md:static md:mx-0 md:border-0 md:bg-transparent md:px-0">
        <div className="flex flex-col-reverse gap-3 md:flex-row md:items-center md:justify-between">
          <button disabled={busy} onClick={() => submit(true)} className="text-sm text-muted underline underline-offset-4 hover:text-foreground">
            Skip questions (photo only)
          </button>
          <button disabled={busy} onClick={() => submit(false)} className="btn btn-accent w-full md:w-auto md:min-w-[240px]">
            {busy ? "Analysing…" : <>Analyse{count ? ` · ${count} answer${count > 1 ? "s" : ""}` : ""} <span className="font-mono font-normal">→</span></>}
          </button>
        </div>
      </div>
    </div>
  );
}
