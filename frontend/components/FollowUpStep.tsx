"use client";
import { useState } from "react";
import type { FollowUp } from "@/lib/types";

const OPTIONS: [string, string][] = [["yes", "Yes"], ["no", "No"], ["unsure", "Not sure"]];

/** Step 3: 2-4 questions chosen from the AI's top 3. Answers only add hints; they never change the ranking. */
export default function FollowUpStep({ questions, busy, onDone }:
  { questions: FollowUp[]; busy: boolean; onDone: (answers: Record<string, string>) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  return (
    <div className="grid gap-10 pt-10 md:grid-cols-[minmax(0,4fr)_minmax(0,5fr)] md:gap-14 md:pt-16">
      <section>
        <p className="eyebrow">Step 3 of 3 · Narrow it down</p>
        <h1 className="display mt-5">Some rashes <em>look alike.</em></h1>
        <p className="lede mt-6 text-muted">
          These questions were chosen from your result. They add hints for you and your doctor. They don&apos;t change the AI&apos;s ranking.
        </p>
      </section>
      <section className="rule-top">
        {questions.map((q, i) => (
          <div key={q.id} className="border-b border-rule py-6">
            <div className="flex gap-4">
              <span className="num pt-1">{String(i + 1).padStart(2, "0")}</span>
              <p className="font-serif text-[1.15rem] leading-snug">{q.text}</p>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 pl-9">
              {OPTIONS.map(([v, l]) => (
                <button key={v} onClick={() => setAnswers({ ...answers, [q.id]: v })}
                  className={`chip justify-center text-center ${answers[q.id] === v ? "chip-on" : ""}`}>{l}</button>
              ))}
            </div>
          </div>
        ))}
        <div className="mt-8 flex flex-col-reverse gap-3 md:flex-row md:items-center md:justify-between">
          <button disabled={busy} onClick={() => onDone({})} className="text-sm text-muted underline underline-offset-4 hover:text-foreground">
            Skip these questions
          </button>
          <button disabled={busy} onClick={() => onDone(answers)} className="btn btn-accent w-full md:w-auto md:min-w-[220px]">
            {busy ? "Preparing…" : <>See my result <span className="font-mono font-normal">→</span></>}
          </button>
        </div>
      </section>
    </div>
  );
}
