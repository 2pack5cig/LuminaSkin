import { jsPDF } from "jspdf";
import type { Ranked, Scan } from "./types";
import { DURATIONS, labelFor } from "./questions";

export function doctorPdf(scan: Scan) {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const W = 210, M = 15;
  let y = 18;
  const line = (text: string, size = 10, bold = false, gap = 5) => {
    doc.setFont("helvetica", bold ? "bold" : "normal");
    doc.setFontSize(size);
    for (const l of doc.splitTextToSize(text, W - 2 * M)) {
      if (y > 280) { doc.addPage(); y = 18; }
      doc.text(l, M, y);
      y += gap;
    }
  };

  const r = scan.result, a = scan.answers;
  line("LuminaSkin - Skin Triage Summary for Doctor", 16, true, 8);
  line(`Date: ${new Date(scan.date).toLocaleString()}   Photos analysed: ${scan.result.photos_used ?? 1}`, 9);
  y += 2;
  doc.addImage(scan.thumb, "JPEG", M, y, 50, 50);
  const yImg = y; y += 54;

  if (r.red_flags.reasons.length) {
    line(`Red flags (${r.red_flags.level ?? ""}):`, 11, true);
    r.red_flags.reasons.forEach((t) => line(`- ${t}`));
    y += 2;
  }

  if (r.scabies?.positive) {
    line(`Scabies screening (clinical criteria, not AI): POSITIVE - ${r.scabies.reasons.join(", ")}`, 10, true);
    y += 2;
  }

  line("AI suggestions (not a diagnosis):", 11, true);
  if (r.uncertain || !r.top3) line("Model was not confident - clinical assessment needed.");
  else ((r.display ?? r.top3) as Ranked[]).forEach((t, i) => {
    line(`${i + 1}. ${t.label} - ${Math.round(t.prob * 100)}%`);
    (t.members ?? []).forEach((m) => line(`     ${m.label} - ${Math.round(m.prob * 100)}%`));
  });
  y += 2;

  line("Patient-reported:", 11, true);
  if (a.skipped) line("Symptom questions skipped.");
  else {
    const dur = DURATIONS.find(([k]) => k === a.condition_duration)?.[1] ?? "not given";
    line(`Duration: ${dur}`);
    const yes = Object.entries(a.bools).filter(([, v]) => v).map(([k]) => labelFor(k));
    line(`Reported: ${yes.length ? yes.join(", ") : "none"}`);
  }
  line(`Itch severity: ${a.itch}/5    Pain/burning severity: ${a.pain}/5`);
  y += 4;
  doc.setFontSize(8);
  doc.text(doc.splitTextToSize(r.disclaimer, W - 2 * M), M, Math.max(y, yImg + 60));

  doc.save(`luminaskin-${scan.date.slice(0, 10)}.pdf`);
}
