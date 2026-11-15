import { jsPDF } from "jspdf";
import type { Ranked, Scan, Shot } from "./types";
import { DURATIONS, GROUPS } from "./questions";
import { nice } from "./questions";

// Palette shared with the website
const INK: [number, number, number] = [22, 19, 15];
const MUTED: [number, number, number] = [104, 99, 92];
const RULE: [number, number, number] = [205, 199, 188];
const PAPER: [number, number, number] = [243, 239, 230];
const ACCENT: [number, number, number] = [11, 95, 88];
const LEVEL: Record<string, { label: string; color: [number, number, number] }> = {
  emergency: { label: "EMERGENCY - seek emergency care now", color: [176, 28, 28] },
  urgent: { label: "URGENT - see a doctor today", color: [190, 72, 18] },
  soon: { label: "SEE SOON - within 24-48 hours", color: [170, 112, 0] },
  routine: { label: "ROUTINE - no red-flag answers", color: ACCENT },
};
const SHOT_LABEL: Record<Shot, string> = { close_up: "Close-up", angle: "Angle", distance: "Distance", extra_close_up: "Extra close-up" };
const CLINICAL: Record<string, string> = {
  "Safety check (tap any that apply)": "Red-flag screen",
  "About you": "Background",
  "What does the rash feel like?": "Symptoms",
  "What does it look like?": "Morphology (patient)",
  "About the itch": "Itch / contact history",
  "Any of these?": "Systemic symptoms",
  "Where on the body?": "Distribution",
};
const pct = (p: number) => (p < 0.01 ? "<1%" : `${Math.round(p * 100)}%`);

export function doctorPdf(scan: Scan) {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const W = 210, H = 297, M = 14, CW = W - 2 * M, BOTTOM = H - 22;
  const r = scan.result, a = scan.answers;
  let y = 0;

  const font = (size: number, style: "normal" | "bold" = "normal", color = INK) => {
    doc.setFont("helvetica", style); doc.setFontSize(size); doc.setTextColor(...color);
  };
  const ensure = (h: number) => { if (y + h > BOTTOM) { doc.addPage(); y = 16; } };
  const text = (t: string, x: number, w: number, size = 9.5, style: "normal" | "bold" = "normal", color = INK, lh = 4.4) => {
    font(size, style, color);
    const lines = doc.splitTextToSize(t, w) as string[];
    lines.forEach((l, i) => doc.text(l, x, y + i * lh));
    return lines.length * lh;
  };
  const section = (title: string) => {
    ensure(14); y += 4;
    font(8, "bold", ACCENT); doc.text(title.toUpperCase(), M, y);
    doc.setDrawColor(...RULE); doc.setLineWidth(0.3); doc.line(M, y + 1.6, W - M, y + 1.6);
    y += 6;
  };
  const row = (label: string, value: string, labelW = 46) => {
    font(9.5); const lines = doc.splitTextToSize(value, CW - labelW) as string[];
    ensure(lines.length * 4.4 + 1.5);
    font(9, "bold", MUTED); doc.text(label, M, y);
    font(9.5, "normal", INK); lines.forEach((l, i) => doc.text(l, M + labelW, y + i * 4.4));
    y += lines.length * 4.4 + 1.5;
  };

  // ---------- header band ----------
  doc.setFillColor(...PAPER); doc.rect(0, 0, W, 30, "F");
  doc.setDrawColor(...INK); doc.setLineWidth(0.5); doc.line(0, 30, W, 30);
  font(18, "bold"); doc.text("Lumina Skin", M, 13);
  font(9.5, "normal", MUTED); doc.text("Skin triage summary for clinician review", M, 19.5);
  font(8, "normal", MUTED); doc.text("Patient-generated report. AI triage aid, not a diagnosis.", M, 24.5);
  const when = new Date(scan.date);
  font(8.5, "bold"); doc.text(`Report ${scan.id.replace(/-/g, "").slice(0, 8).toUpperCase()}`, W - M, 12, { align: "right" });
  font(8.5, "normal", MUTED);
  doc.text(when.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }), W - M, 17, { align: "right" });
  doc.text(`Model v3 · 15 conditions · ${r.photos_used ?? 1} photo(s) analysed`, W - M, 22, { align: "right" });
  y = 38;

  // ---------- triage level ----------
  const lvl = LEVEL[r.red_flags.level ?? "routine"] ?? LEVEL.routine;
  const reasons = r.red_flags.reasons.length ? r.red_flags.reasons : ["No emergency, urgent or 'see soon' answers were given."];
  font(9); const rl = reasons.flatMap((t) => doc.splitTextToSize(`• ${t}`, CW - 10) as string[]);
  const boxH = 10 + rl.length * 4.3;
  doc.setFillColor(...lvl.color); doc.rect(M, y, 2.2, boxH, "F");
  doc.setDrawColor(...RULE); doc.rect(M, y, CW, boxH);
  font(10.5, "bold", lvl.color); doc.text(`TRIAGE LEVEL: ${lvl.label}`, M + 6, y + 6);
  font(9, "normal", INK); rl.forEach((l, i) => doc.text(l, M + 6, y + 11 + i * 4.3));
  y += boxH + 2;

  // ---------- self-medication warning (fixed rule) ----------
  const mw = r.medicine_warning;
  if (mw?.show) {
    const RED: [number, number, number] = [176, 28, 28];
    const body = [
      ...(mw.used_text ? [mw.used_text] : []),
      ...mw.medicines.map((m) => `x ${m.name}: ${m.examples}`),
      ...mw.reasons,
    ];
    font(8.8); const bl = body.flatMap((t) => doc.splitTextToSize(t, CW - 10) as string[]);
    const h = 10 + bl.length * 4.1;
    ensure(h + 2);
    doc.setFillColor(...RED); doc.rect(M, y, 2.2, h, "F");
    doc.setDrawColor(...RED); doc.rect(M, y, CW, h);
    font(10, "bold", RED); doc.text("DO NOT USE WITHOUT A DOCTOR'S PRESCRIPTION (patient warned)", M + 6, y + 6);
    font(8.8, "normal", INK); bl.forEach((l, i) => doc.text(l, M + 6, y + 11 + i * 4.1));
    y += h + 2;
  }

  // ---------- photos ----------
  section("Photos");
  const photos = scan.photoThumbs?.length ? scan.photoThumbs : [{ thumb: scan.thumb, shot: "close_up" as Shot }];
  const tiles = [...photos.map((p) => ({ img: p.thumb, cap: SHOT_LABEL[p.shot] ?? "Photo" })),
    ...(scan.heatmapThumb ? [{ img: scan.heatmapThumb, cap: "Heatmap (Grad-CAM++)" }] : [])].slice(0, 5);
  const S = 33, G = 3.5;
  ensure(S + 8);
  tiles.forEach((t, i) => {
    const x = M + i * (S + G);
    doc.addImage(t.img, "JPEG", x, y, S, S);
    doc.setDrawColor(...RULE); doc.rect(x, y, S, S);
    font(7.5, "normal", MUTED); doc.text(t.cap, x, y + S + 3.8);
  });
  y += S + 7;
  const skipped = r.quality.skipped_photos?.length ?? 0;
  const qnotes = [
    skipped ? `${skipped} photo(s) excluded for poor quality (blur/darkness).` : "",
    ...(r.quality.warnings ?? []).map((w) => w.message),
    r.ood.unusual ? "Photo flagged as unusual compared with the training photos." : "",
  ].filter(Boolean);
  if (qnotes.length) { y += text(`Photo quality: ${qnotes.join(" ")}`, M, CW, 8.5, "normal", MUTED); y += 1; }

  // ---------- AI differential ----------
  section("AI differential (ranked)");
  if (!r.top3) {
    y += text(r.ood.rejected ? "Not analysed: the photo did not appear to show skin." : "Not analysed: photo quality too poor.", M, CW);
    y += 2;
  } else {
    const cols = [M, M + 10, M + 100, M + 128];
    font(8, "bold", MUTED); ["#", "Condition", "Probability", "Note"].forEach((h, i) => doc.text(h, cols[i], y));
    y += 2; doc.setDrawColor(...RULE); doc.line(M, y, W - M, y); y += 4.5;
    ((r.display ?? r.top3) as Ranked[]).forEach((t, i) => {
      ensure(10);
      font(9.5, i === 0 ? "bold" : "normal"); doc.text(String(i + 1), cols[0], y); doc.text(nice(t.label), cols[1], y);
      doc.text(pct(t.prob), cols[2], y);
      font(8.5, "normal", MUTED);
      doc.text(t.members ? "grouped: eczema family" : i === 0 ? (r.uncertain ? "below confidence threshold" : "top suggestion") : "", cols[3], y);
      // probability bar
      doc.setFillColor(...RULE); doc.rect(cols[2] + 13, y - 2.6, 12, 2.2, "F");
      doc.setFillColor(...ACCENT); doc.rect(cols[2] + 13, y - 2.6, Math.max(0.3, 12 * t.prob), 2.2, "F");
      y += 5;
      (t.members ?? []).forEach((m) => {
        font(8.5, "normal", MUTED); doc.text(`- ${nice(m.label)}`, cols[1] + 3, y); doc.text(pct(m.prob), cols[2], y); y += 4.3;
      });
    });
    y += 1;
    row("Model confidence", r.uncertain
      ? "NOT CONFIDENT: top probability below the model's confidence threshold. Treat as a differential to assess clinically."
      : "Confident (top probability above the model's confidence threshold).");
    row("Inputs used", `${r.photos_used ?? 1} photo(s)${r.symptoms_used ? " + patient symptom answers" : " only (symptom questions skipped)"}${r.contributions ? `; approx. influence photo ${Math.round(r.contributions.image * 100)}% / symptoms ${Math.round(r.contributions.symptoms * 100)}%` : ""}.`);
    y += text("Fused model: Google Derm Foundation embeddings + EfficientNet-B0 + symptom model. Held-out test (612 cases): top-3 accuracy 89.1% overall, 90.6% on Indian patients, 89.1% on Fitzpatrick IV-VI. Not clinically validated.", M, CW, 8, "normal", MUTED, 3.8);
    y += 2;
  }

  // ---------- patient-reported history ----------
  section("Patient-reported history");
  if (a.skipped) row("Questions", "Skipped by the patient (photo-only analysis).");
  else row("Duration", DURATIONS.find(([k]) => k === a.condition_duration)?.[1] ?? "Not given");
  row("Severity (patient)", `Itch ${a.itch}/5 · Pain/burning ${a.pain}/5`);
  GROUPS.forEach((g) => {
    const sel = g.items.filter(([k]) => a.bools[k]).map(([, l]) => l);
    if (!a.skipped || sel.length) row(CLINICAL[g.title] ?? g.title, sel.length ? sel.join("; ") : "None reported");
  });

  // ---------- follow-up questions ----------
  const fa = r.followup_answers ?? {};
  if ((r.followups ?? []).length) {
    section("Targeted follow-up questions (asked after the AI result)");
    (r.followups ?? []).forEach((q) => {
      const ans = fa[q.id] ? { yes: "Yes", no: "No", unsure: "Not sure" }[fa[q.id]] ?? fa[q.id] : "Not answered";
      font(9.5); const lines = doc.splitTextToSize(q.text, CW - 26) as string[];
      ensure(lines.length * 4.4 + 1.5);
      font(9.5, "normal", INK); lines.forEach((l, i) => doc.text(l, M, y + i * 4.4));
      font(9.5, "bold", fa[q.id] === "yes" ? ACCENT : MUTED); doc.text(ans, W - M, y, { align: "right" });
      y += lines.length * 4.4 + 1.5;
    });
  }

  // ---------- decision-support flags ----------
  const flags: [string, string][] = [];
  (r.alerts ?? []).forEach((al) => flags.push([al.title, al.text]));
  if (r.scabies) flags.push(["Scabies screen (clinical criteria)", r.scabies.positive ? `POSITIVE: ${r.scabies.reasons.join(", ")}.` : "Negative."]);
  (r.hints?.fits ?? []).forEach((f) => flags.push([`Answers support: ${nice(f.label)}`, f.reasons.join(", ")]));
  (r.hints?.also_consider ?? []).forEach((c) => flags.push([`Also consider: ${c.name}`, `${c.covered_by_ai ? "Ranked low by the AI" : "Not assessed by the AI"}; patient reported ${c.reasons.join(", ")}.`]));
  (r.hints?.alerts ?? []).forEach((t) => flags.push(["Follow-up alert", t]));
  if (flags.length) {
    section("Decision-support flags (rule-based, not the AI)");
    flags.forEach(([t, d]) => {
      font(9.5); const lines = doc.splitTextToSize(d, CW - 4) as string[];
      ensure(5 + lines.length * 4.2);
      font(9.5, "bold"); doc.text(t, M, y); y += 4.4;
      font(9, "normal", MUTED); lines.forEach((l, i) => doc.text(l, M + 2, y + i * 4.2)); y += lines.length * 4.2 + 1.8;
    });
  }

  // ---------- advice shown to the patient ----------
  if (r.triage) {
    section("Advice shown to the patient");
    if (r.triage.steroid_warning) row("Steroid warning", r.triage.steroid_warning);
    if (r.triage.soothing_care.length) row("Self-care shown", r.triage.soothing_care.map((c) => c.tip).join(" "));
  }

  // ---------- clinician notes ----------
  section("Clinician notes");
  ensure(40);
  doc.setDrawColor(...RULE);
  for (let i = 0; i < 6; i++) doc.line(M, y + 6 + i * 6.5, W - M, y + 6 + i * 6.5);
  y += 44;

  // ---------- footer on every page ----------
  const n = doc.getNumberOfPages();
  for (let p = 1; p <= n; p++) {
    doc.setPage(p);
    doc.setDrawColor(...RULE); doc.line(M, H - 15, W - M, H - 15);
    font(7.5, "normal", MUTED);
    doc.text(doc.splitTextToSize(`${r.disclaimer} Generated by LuminaSkin from patient-taken photos and self-reported answers.`, CW - 22) as string[], M, H - 11);
    doc.text(`Page ${p} of ${n}`, W - M, H - 11, { align: "right" });
  }

  doc.save(`luminaskin-report-${scan.date.slice(0, 10)}.pdf`);
}
