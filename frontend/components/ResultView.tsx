"use client";
import type { AlsoConsider, AnalyzeResult, Care, MedicineWarning, Ranked } from "@/lib/types";

const OOD_MSG: Record<string, string> = {
  NOT_SKIN: "We couldn't find skin in this photo. Retake it with the rash filling the square.",
  OUT_OF_DISTRIBUTION: "This doesn't look like a skin rash we can assess. If you're worried, please see a doctor.",
};
const pct = (p: number) => (p < 0.01 ? "<1%" : `${Math.round(p * 100)}%`);

/** A labelled block with a thin top rule, like the landing page sections. */
function Block({ label, children, tone }: { label: string; children: React.ReactNode; tone?: "warn" | "danger" | "info" }) {
  const border = tone === "danger" ? "border-[#B01C1C]" : tone === "warn" ? "border-[#B5651D]" : "border-foreground";
  return (
    <section className={`border-t ${border} pt-4`}>
      <p className={`eyebrow ${tone === "danger" ? "!text-[#B01C1C]" : tone === "warn" ? "!text-[#9A5212]" : ""}`}>{label}</p>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function CareList({ items }: { items: Care[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((c) => (
        <li key={c.tip} className="grid grid-cols-[18px_1fr]"><span className="text-muted">—</span>
          <span>{c.tip}{c.caution && <span className="text-muted"> ({c.caution})</span>}</span></li>
      ))}
    </ul>
  );
}

function AlsoCard({ a }: { a: AlsoConsider }) {
  return (
    <details className="group border-b border-rule py-3">
      <summary className="flex cursor-pointer list-none items-baseline justify-between gap-4">
        <span>
          <span className="font-serif text-[1.1rem]">Could also be: {a.name}</span>
          <span className="block text-sm text-muted">
            {a.covered_by_ai ? "The AI ranked this lower" : "Not assessed by LuminaSkin's AI"} · because {a.reasons.join(", ")}
          </span>
        </span>
        <span className="num group-open:rotate-45 transition-transform">+</span>
      </summary>
      <div className="mt-3 space-y-3 text-[0.95rem]">
        {a.summary && <p>{a.summary}</p>}
        {a.contagious && <p><b>Contagious:</b> {a.contagious}</p>}
        {a.soothing_care && a.soothing_care.length > 0 && <div><p className="eyebrow mb-1">Soothing Care</p><CareList items={a.soothing_care} /></div>}
        {a.see_doctor_when && a.see_doctor_when.length > 0 && (
          <div><p className="eyebrow mb-1">See a doctor if</p>
            <ul className="space-y-1">{a.see_doctor_when.map((t) => <li key={t} className="grid grid-cols-[18px_1fr]"><span className="text-muted">—</span><span>{t}</span></li>)}</ul>
          </div>
        )}
      </div>
    </details>
  );
}

function Scabies({ s }: { s: NonNullable<AnalyzeResult["scabies"]> }) {
  if (!s.positive) return null;
  return (
    <Block label={s.prominent ? "Scabies screen · positive" : "Also consider scabies"} tone="warn">
      <p className="font-serif text-[1.2rem] leading-snug">{s.prominent ? "Signs suggest possible scabies." : "Your answers match common scabies signs."}</p>
      <p className="mt-1 text-[0.95rem]">Matched: {s.reasons.join(", ")}. Scabies can look like eczema: <b>don&apos;t use steroid creams until a doctor has ruled it out.</b></p>
      {s.prominent && (
        <div className="mt-3 space-y-3 text-[0.95rem]">
          {s.contagious && <p><b>Contagious:</b> {s.contagious}</p>}
          {s.soothing_care && <CareList items={s.soothing_care} />}
          {s.see_doctor_when?.[0] && <p><b>See a doctor:</b> {s.see_doctor_when[0]}</p>}
        </div>
      )}
      <p className="num mt-2">{s.basis.toUpperCase()}</p>
    </Block>
  );
}

/** Red "don't self-medicate" banner. Fixed rule, not AI. */
function MedicineBanner({ w }: { w: MedicineWarning }) {
  const solid = w.level === "danger";
  return (
    <section className={`rounded-[4px] p-5 sm:p-6 ${solid ? "bg-[#B01C1C] text-white" : "border-2 border-[#B01C1C] bg-[#B01C1C]/5"}`}>
      <p className={`font-mono text-[0.72rem] uppercase tracking-[0.08em] ${solid ? "text-white/80" : "text-[#B01C1C]"}`}>
        Strict warning · self-medication
      </p>
      <p className="mt-1 font-serif text-[1.4rem] leading-snug">{w.title}.</p>
      {w.used_text && <p className={`mt-2 font-semibold ${solid ? "" : "text-[#B01C1C]"}`}>{w.used_text}</p>}
      <ul className={`mt-3 divide-y ${solid ? "divide-white/25 border-y border-white/25" : "divide-[#B01C1C]/20 border-y border-[#B01C1C]/20"}`}>
        {w.medicines.map((m) => (
          <li key={m.name} className="grid gap-0.5 py-2 sm:grid-cols-[210px_1fr] sm:gap-4">
            <span className="font-semibold">✕ {m.name}</span>
            <span className={solid ? "text-white/85" : "text-muted"}>{m.examples}</span>
          </li>
        ))}
      </ul>
      {w.reasons.length > 0 && (
        <ul className="mt-3 space-y-1 text-[0.95rem]">{w.reasons.map((t) => <li key={t}>— {t}</li>)}</ul>
      )}
      <p className={`mt-3 text-[0.95rem] ${solid ? "text-white/90" : ""}`}>{w.why}</p>
      <p className="mt-2 text-[0.95rem] font-semibold">{w.do_instead}</p>
    </section>
  );
}

/** Results: visual column (photo + heatmap) and reading column. */
export default function ResultView({ r, photo, actions, meta }:
  { r: AnalyzeResult; photo: string; actions?: React.ReactNode; meta?: React.ReactNode }) {
  const flag = r.red_flags;
  const ranked = (r.display ?? r.top3 ?? []) as Ranked[];
  const headline = !r.quality.ok ? <>Let&apos;s <em>retake</em> the photo.</>
    : r.ood.rejected ? <>We can&apos;t <em>assess</em> this photo.</>
    : r.uncertain ? <>Not confident. <em>See a doctor.</em></>
    : <>Most likely <em>{ranked[0]?.label}.</em></>;

  return (
    <div className="grid gap-10 pt-10 md:grid-cols-[minmax(0,4fr)_minmax(0,5fr)] md:gap-14 md:pt-16">
      {/* ---------- visual column ---------- */}
      <aside className="md:sticky md:top-24 md:self-start">
        <div className="relative aspect-square w-full overflow-hidden rounded-[4px] border border-rule bg-surface">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photo} alt="Your photo" className="absolute inset-0 h-full w-full object-cover" />
          {r.heatmap_png_b64 && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`data:image/png;base64,${r.heatmap_png_b64}`} alt="Heatmap of where the AI looked" className="absolute inset-0 h-full w-full object-cover opacity-50" />
          )}
        </div>
        <div className="mt-3 flex items-baseline justify-between gap-4">
          <p className="eyebrow">{r.heatmap_png_b64 ? "Where the AI looked · Grad-CAM++" : "Your photo"}</p>
          {r.photos_used && r.photos_used > 1 && <p className="num">{r.photos_used} PHOTOS COMBINED</p>}
        </div>
        {meta}
      </aside>

      {/* ---------- reading column ---------- */}
      <div className="space-y-8">
        <div>
          <p className="eyebrow">Your result{r.mock ? " · demo mode" : ""}</p>
          <h1 className="display mt-5">{headline}</h1>
        </div>

        {flag.reasons.length > 0 && (
          <div className={`rounded-[4px] p-5 ${flag.level === "emergency" ? "bg-[#B01C1C] text-white" : flag.level === "urgent" ? "border border-[#B01C1C] bg-[#B01C1C]/5" : "border border-[#B5651D] bg-[#B5651D]/5"}`}>
            <p className={`font-mono text-[0.72rem] uppercase tracking-[0.08em] ${flag.level === "emergency" ? "text-white/80" : ""}`}>
              {flag.level === "emergency" ? "Emergency" : flag.level === "urgent" ? "Urgent" : "See soon"} · fixed safety rule, not AI
            </p>
            <p className="mt-1 font-serif text-[1.35rem] leading-snug">
              {flag.level === "emergency" ? "Seek emergency care now." : flag.level === "urgent" ? "See a doctor today." : "See a doctor soon."}
            </p>
            <ul className="mt-2 space-y-1 text-[0.95rem]">{flag.reasons.map((t) => <li key={t}>{t}</li>)}</ul>
          </div>
        )}

        {r.medicine_warning?.show && <MedicineBanner w={r.medicine_warning} />}

        {(r.alerts ?? []).filter((a) => a.level !== "info").map((a) => (
          <Block key={a.kind} label={a.level === "urgent" ? "Urgent" : "Please note"} tone="warn">
            <p className="font-semibold">{a.title}</p><p className="text-[0.95rem]">{a.text}</p>
          </Block>
        ))}
        {(r.hints?.alerts ?? []).map((t) => <Block key={t} label="Please note" tone="warn"><p className="text-[0.95rem]">{t}</p></Block>)}

        {r.scabies?.positive && r.scabies.prominent && <Scabies s={r.scabies} />}

        {!r.quality.ok && (
          <Block label="Photo quality">
            <ul className="space-y-1">{r.quality.issues.map((i) => <li key={i.code}>{i.message}</li>)}</ul>
          </Block>
        )}
        {r.ood.rejected && r.ood.reason && <Block label="Photo check"><p>{OOD_MSG[r.ood.reason]}</p></Block>}
        {r.uncertain && (
          <p className="text-muted">
            {r.ood.unusual
              ? "This photo looks different from the photos the AI learned from, so treat the possibilities below with caution."
              : "The AI couldn't match this to one condition with enough confidence. The possibilities below are for discussing with a doctor."}
          </p>
        )}

        {ranked.length > 0 && (
          <section className="rule-top">
            {ranked.map((t, i) => (
              <div key={t.label} className={`border-b border-rule py-4 ${r.uncertain ? "opacity-80" : ""}`}>
                <div className="grid grid-cols-[34px_1fr_auto] items-baseline gap-2">
                  <span className="num">{String(i + 1).padStart(2, "0")}</span>
                  <span className={`font-serif text-[1.2rem] leading-tight ${i === 0 ? "font-semibold" : ""}`}>{t.label}</span>
                  <span className="font-mono text-[0.95rem]">{pct(t.prob)}</span>
                </div>
                <div className="bar mt-2 ml-[34px] w-[calc(100%-34px)]"><span style={{ width: `${Math.max(1, t.prob * 100)}%`, opacity: 1 - i * 0.25 }} /></div>
                {t.members && (
                  <div className="ml-[34px] mt-2 space-y-0.5">
                    {t.members.map((m) => (
                      <div key={m.label} className="flex justify-between text-sm text-muted"><span>— {m.label}</span><span className="font-mono">{pct(m.prob)}</span></div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <p className="num mt-3">
              {r.symptoms_used ? "PHOTO + YOUR ANSWERS" : "PHOTO ONLY"}
              {r.contributions ? ` · APPROX. INFLUENCE PHOTO ${Math.round(r.contributions.image * 100)}% / ANSWERS ${Math.round(r.contributions.symptoms * 100)}%` : ""}
            </p>
          </section>
        )}

        {r.hints && (r.hints.fits.length > 0 || r.hints.also_consider.length > 0) && (
          <Block label="Hints from your answers">
            {r.hints.fits.map((f) => (
              <p key={f.label} className="py-1"><b>Your answers fit {f.label}</b>, one of the possibilities above <span className="text-muted">({f.reasons.join(", ")})</span>.</p>
            ))}
            {r.hints.also_consider.map((a) => <AlsoCard key={a.name} a={a} />)}
            <p className="num mt-3">{r.hints.note.toUpperCase()}</p>
          </Block>
        )}

        {r.scabies?.positive && !r.scabies.prominent && <Scabies s={r.scabies} />}

        {r.triage && (
          <>
            <Block label={`About ${ranked[0]?.label ?? "this condition"}`}>
              <p className="text-[1.02rem]">{r.triage.summary}</p>
              {r.triage.contagious && <p className="mt-2"><b>Contagious:</b> {r.triage.contagious}</p>}
            </Block>
            {r.triage.steroid_warning && (
              <Block label="Steroid cream warning" tone="warn"><p>{r.triage.steroid_warning}</p></Block>
            )}
            {r.triage.soothing_care.length > 0 && <Block label="Soothing Care"><CareList items={r.triage.soothing_care} /></Block>}
            {r.triage.see_doctor_when.length > 0 && (
              <Block label="See a doctor if">
                <ul className="space-y-1.5">{r.triage.see_doctor_when.map((t) => <li key={t} className="grid grid-cols-[18px_1fr]"><span className="text-muted">—</span><span>{t}</span></li>)}</ul>
              </Block>
            )}
          </>
        )}

        {(r.alerts ?? []).filter((a) => a.level === "info").map((a) => (
          <Block key={a.kind} label="Good to know"><p className="font-semibold">{a.title}</p><p className="text-[0.95rem] text-muted">{a.text}</p></Block>
        ))}

        {actions}
        <p className="text-sm text-muted">{r.disclaimer}</p>
      </div>
    </div>
  );
}
