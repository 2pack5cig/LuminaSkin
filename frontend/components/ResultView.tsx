"use client";
import type { AnalyzeResult, Ranked } from "@/lib/types";

const OOD_MSG: Record<string, string> = {
  NOT_SKIN: "We couldn't find skin in this photo. Retake it with the rash filling the square.",
  OUT_OF_DISTRIBUTION: "This doesn't look like a rash we can assess. Please see a doctor.",
};

function ScabiesCard({ s }: { s: NonNullable<AnalyzeResult["scabies"]> }) {
  if (!s.positive) return null;
  if (!s.prominent) {
    return (
      <div className="rounded-2xl bg-amber-50 border border-amber-200 p-3 text-sm">
        <p className="font-semibold">Also consider scabies</p>
        <p>Your answers ({s.reasons.slice(1).join(", ")}) match common scabies signs. Scabies can look like eczema.{" "}
          <b>Don&apos;t use steroid creams until a doctor has ruled it out.</b></p>
        <p className="text-xs text-black/50 mt-1">{s.basis}</p>
      </div>
    );
  }
  return (
    <div className="rounded-2xl bg-orange-50 border border-orange-300 p-4 text-sm space-y-2">
      <p className="font-semibold text-base">Signs suggest possible scabies</p>
      <p>Matched: {s.reasons.join(", ")}.</p>
      {s.contagious && <p><b>Contagious:</b> {s.contagious}</p>}
      {s.steroid_warning && <p><b>Steroid cream warning:</b> {s.steroid_warning}</p>}
      {s.soothing_care && s.soothing_care.length > 0 && (
        <ul className="list-disc pl-5 space-y-1">
          {s.soothing_care.map((c) => <li key={c.tip}>{c.tip}{c.caution && <span className="text-black/50"> ({c.caution})</span>}</li>)}
        </ul>
      )}
      {s.see_doctor_when && <p><b>See a doctor:</b> {s.see_doctor_when[0]}</p>}
      <p className="text-xs text-black/50">{s.basis}</p>
    </div>
  );
}

export default function ResultView({ r, photo }: { r: AnalyzeResult; photo: string }) {
  const flag = r.red_flags;
  const flagStyle = flag.level === "emergency" ? "bg-red-700 text-white"
    : flag.level === "urgent" ? "bg-red-100 text-red-900 border border-red-300"
    : "bg-amber-50 text-amber-900 border border-amber-200";

  return (
    <div className="space-y-4">
      {r.mock && <p className="text-xs text-center text-black/40">Demo mode: sample results</p>}

      {flag.reasons.length > 0 && (
        <div className={`rounded-2xl p-4 ${flagStyle}`}>
          <p className="font-semibold">
            {flag.level === "emergency" ? "Seek emergency care now" : flag.level === "urgent" ? "See a doctor today" : "See a doctor soon"}
          </p>
          <ul className="mt-1 text-sm list-disc pl-5 space-y-1">{flag.reasons.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
      )}

      {r.scabies?.positive && r.scabies.prominent && <ScabiesCard s={r.scabies} />}

      {!r.quality.ok && (
        <div className="rounded-2xl bg-white p-4 border">
          <p className="font-semibold">Let&apos;s retake the photo</p>
          <ul className="mt-1 text-sm list-disc pl-5">{r.quality.issues.map((i) => <li key={i.code}>{i.message}</li>)}</ul>
        </div>
      )}

      {r.ood.rejected && r.ood.reason && (
        <div className="rounded-2xl bg-white p-4 border"><p>{OOD_MSG[r.ood.reason]}</p></div>
      )}

      {r.uncertain && (
        <div className="rounded-2xl bg-white p-4 border">
          <p className="font-semibold">Not confident</p>
          <p className="text-sm text-black/70">The AI couldn&apos;t match this to a condition with enough confidence. Please see a doctor.</p>
        </div>
      )}

      {r.top3 && (
        <div className={`rounded-2xl bg-white p-4 border space-y-3 ${r.uncertain ? "opacity-70" : ""}`}>
          <p className="font-semibold">{r.uncertain ? "Possibilities to discuss with a doctor" : "Possible conditions"}</p>
          {((r.display ?? r.top3) as Ranked[]).map((t, i) => (
            <div key={t.label}>
              <div className="flex justify-between text-sm"><span className={i === 0 ? "font-medium" : ""}>{t.label}</span><span>{Math.round(t.prob * 100)}%</span></div>
              <div className="h-2 rounded-full bg-black/5 mt-1"><div className="h-2 rounded-full bg-brand" style={{ width: `${t.prob * 100}%`, opacity: 1 - i * 0.25 }} /></div>
              {t.members && (
                <div className="mt-2 ml-3 pl-3 border-l-2 border-brand/30 space-y-1">
                  {t.members.map((m) => (
                    <div key={m.label} className="flex justify-between text-xs text-black/60"><span>{m.label}</span><span>{Math.round(m.prob * 100)}%</span></div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {r.contributions && (
            <p className="text-xs text-black/50">Approximate influence: photo {Math.round(r.contributions.image * 100)}% · symptoms {Math.round(r.contributions.symptoms * 100)}%</p>
          )}
          {!r.symptoms_used && <p className="text-xs text-black/50">Based on the photo only.</p>}
        </div>
      )}

      {r.scabies?.positive && !r.scabies.prominent && <ScabiesCard s={r.scabies} />}

      {r.top3 && (
        <div className="rounded-2xl bg-white p-4 border">
          <p className="font-semibold mb-2">Where the AI looked</p>
          <div className="relative w-full aspect-square rounded-xl overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={photo} alt="Your photo" className="absolute inset-0 w-full h-full object-cover" />
            {r.heatmap_png_b64 && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={`data:image/png;base64,${r.heatmap_png_b64}`} alt="Heatmap" className="absolute inset-0 w-full h-full object-cover opacity-50" />
            )}
          </div>
          {!r.heatmap_png_b64 && <p className="text-xs text-black/50 mt-2">Heatmap will appear here once the image model is connected.</p>}
        </div>
      )}

      {r.triage && (
        <div className="rounded-2xl bg-white p-4 border space-y-3 text-sm">
          <p>{r.triage.summary}</p>
          {r.triage.contagious && <p><b>Contagious:</b> {r.triage.contagious}</p>}
          {r.triage.steroid_warning && (
            <div className="rounded-xl bg-amber-50 border border-amber-200 p-3"><b>Steroid cream warning:</b> {r.triage.steroid_warning}</div>
          )}
          {r.triage.soothing_care.length > 0 && (
            <div>
              <p className="font-semibold">Soothing Care</p>
              <ul className="list-disc pl-5 space-y-1">
                {r.triage.soothing_care.map((c) => (
                  <li key={c.tip}>{c.tip}{c.caution && <span className="text-black/50"> ({c.caution})</span>}</li>
                ))}
              </ul>
            </div>
          )}
          {r.triage.see_doctor_when.length > 0 && (
            <div>
              <p className="font-semibold">See a doctor if</p>
              <ul className="list-disc pl-5 space-y-1">{r.triage.see_doctor_when.map((t) => <li key={t}>{t}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-black/50">{r.disclaimer}</p>
    </div>
  );
}
