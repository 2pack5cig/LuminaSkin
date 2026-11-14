"use client";
import { useState } from "react";
import { DURATIONS, GROUPS } from "@/lib/questions";
import type { Answers } from "@/lib/types";

const chip = (on: boolean) =>
  `px-3 py-2 rounded-full text-sm border transition ${on ? "bg-brand text-white border-brand" : "bg-white border-black/10"}`;

export default function QuestionsStep({ preview, onSubmit, busy }:
  { preview: string; onSubmit: (a: Answers) => void; busy: boolean }) {
  const [bools, setBools] = useState<Record<string, boolean>>({});
  const [duration, setDuration] = useState<string | null>(null);
  const [itch, setItch] = useState(0);
  const [pain, setPain] = useState(0);
  const toggle = (k: string) => setBools((b) => ({ ...b, [k]: !b[k] }));

  const submit = (skipped: boolean) =>
    onSubmit({ skipped, bools: skipped ? {} : bools, condition_duration: skipped ? null : duration, itch, pain });

  return (
    <div className="pt-4 space-y-6">
      <div className="flex items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={preview} alt="Your photo" className="w-16 h-16 rounded-xl object-cover" />
        <div>
          <p className="font-medium">A few quick questions</p>
          <p className="text-sm text-black/60">Tap all that apply. They make the result more accurate.</p>
        </div>
      </div>

      <section>
        <h2 className="font-medium mb-2">How long have you had it?</h2>
        <div className="flex flex-wrap gap-2">
          {DURATIONS.map(([k, l]) => (
            <button key={k} className={chip(duration === k)} onClick={() => setDuration(duration === k ? null : k)}>{l}</button>
          ))}
        </div>
      </section>

      {GROUPS.map((g) => (
        <section key={g.title}>
          <h2 className="font-medium mb-2">{g.title}</h2>
          <div className="flex flex-wrap gap-2">
            {g.items.map(([k, l]) => <button key={k} className={chip(!!bools[k])} onClick={() => toggle(k)}>{l}</button>)}
          </div>
        </section>
      ))}

      <section className="space-y-3">
        <h2 className="font-medium">How bad is it? (for your tracker)</h2>
        {([["Itch", itch, setItch], ["Pain / burning", pain, setPain]] as const).map(([l, v, set]) => (
          <label key={l} className="block text-sm">
            {l}: <b>{v}/5</b>
            <input type="range" min={0} max={5} value={v} onChange={(e) => set(Number(e.target.value))}
              className="w-full accent-[#0f766e]" />
          </label>
        ))}
      </section>

      <div className="space-y-3 pt-2">
        <button disabled={busy} onClick={() => submit(false)}
          className="w-full rounded-2xl bg-brand text-white py-4 font-medium disabled:opacity-60">
          {busy ? "Analysing…" : "Analyse"}
        </button>
        <button disabled={busy} onClick={() => submit(true)} className="w-full text-sm text-black/60 py-2">
          Skip questions (photo only)
        </button>
      </div>
    </div>
  );
}
