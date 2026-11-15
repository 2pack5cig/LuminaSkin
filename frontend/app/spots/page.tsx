"use client";
import { useEffect, useState } from "react";
import { CropView, PickButtons } from "@/components/CaptureStep";
import { measureSpot, type MeasureResponse } from "@/lib/api";
import { thumbnail } from "@/lib/image";
import { RECHECK_DAYS, addDays, calendarReminder, daysUntil, deleteSpot, listSpots, newId, saveSpot } from "@/lib/spots";
import type { Spot, SpotCheck, SpotComparison, SpotConcern, SpotKind } from "@/lib/types";

const LOCATIONS: [string, string][] = [
  ["face", "Face"], ["neck", "Neck"], ["chest", "Chest / belly"], ["back", "Back"], ["arm", "Arm"], ["hand", "Back of hand"],
  ["palm", "Palm"], ["leg", "Leg"], ["foot", "Foot (top)"], ["sole", "Sole of foot"], ["nail", "Under a nail"], ["other", "Other"],
];
// Coin sizes changed between series, so the user picks coin + series, or types the diameter.
const COINS: [string, string][] = [
  ["1", "₹1 · new (2019 onwards) · 20 mm"], ["1_old", "₹1 · older (before 2011) · 25 mm"],
  ["2", "₹2 · new (2019 onwards) · 23 mm"], ["5", "₹5 · new (2019 onwards) · 25 mm"], ["10", "₹10 · 27 mm"],
];
const coinLabel = (c: string) => COINS.find(([k]) => k === c)?.[1] ?? `${c} mm coin`;
const RED = "#8E2A2A";

const VERDICT: Record<string, { title: string; tone: "warn" | "ok" | "info" }> = {
  changed_see_doctor: { title: "This spot has changed. See a doctor.", tone: "warn" },
  bigger_see_doctor: { title: "Bigger than last time: show your doctor.", tone: "warn" },
  check_same_spot: { title: "Is this the same spot?", tone: "info" },
  bigger: { title: "Slightly bigger than last time.", tone: "info" },
  smaller: { title: "Smaller than last time.", tone: "ok" },
  about_same: { title: "About the same as last time.", tone: "ok" },
  no_change: { title: "No change measured. Keep watching.", tone: "ok" },
};
const fmtDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const size = (c: SpotCheck) => c.metrics.eq_diameter_mm != null
  ? `${c.metrics.eq_diameter_mm} mm · ${c.metrics.area_mm2} mm²` : `${c.metrics.area_pct_of_photo}% of photo (no coin)`;

/** "Get it checked" bar from warning signs (not a cancer probability). Calm colours, three bands. */
function ConcernBar({ c }: { c: SpotConcern }) {
  const LV = { low: ["Low", "Keep watching", "#0B5F58"], medium: ["Medium", "Get it checked by a doctor", "#9A5212"], high: ["High", "See a doctor soon (within 2 weeks)", RED] } as const;
  const [label, action, color] = LV[c.level];
  return (
    <section className="card p-5">
      <div className="flex items-baseline justify-between gap-4">
        <p className="eyebrow">Concern level · warning signs</p>
        <p className="font-mono text-[0.8rem]" style={{ color }}>{c.score}/100</p>
      </div>
      <p className="mt-1 font-serif text-[1.3rem]" style={{ color }}>{label}: {action}.</p>
      <div className="relative mt-3 h-2 w-full overflow-hidden rounded-[1px]"
        style={{ background: "linear-gradient(90deg, #0B5F5833 0 30%, #9A521233 30% 60%, #8E2A2A33 60% 100%)" }}>
        <span className="absolute top-0 left-0 h-full" style={{ width: `${Math.max(2, c.score)}%`, background: color }} />
      </div>
      <div className="mt-1 flex justify-between font-mono text-[0.68rem] uppercase tracking-[0.06em] text-muted"><span>Low</span><span>Medium</span><span>High</span></div>
      {c.checklist && (
        <ul className="mt-4 divide-y divide-rule border-y border-rule">
          {c.checklist.map((x) => (
            <li key={x.letter} className="grid grid-cols-[24px_1fr_auto] items-baseline gap-2 py-1.5 text-[0.93rem]">
              <span className="font-serif text-[1.1rem]" style={{ color: x.warn ? RED : undefined }}>{x.letter}</span>
              <span><span className="text-muted">{x.label} · </span>{x.detail}</span>
              <span className="font-mono text-[0.72rem]" style={{ color: x.warn ? RED : "#0B5F58" }}>{x.warn ? "SIGN" : "OK"}</span>
            </li>
          ))}
        </ul>
      )}
      {!c.checklist && (c.reasons.length > 0
        ? <ul className="mt-3 space-y-1 text-[0.95rem]">{c.reasons.map((r) => <li key={r}>— {r}</li>)}</ul>
        : <p className="mt-3 text-[0.95rem] text-muted">No warning signs measured.</p>)}
      <p className="mt-2 text-sm text-muted">{c.note}</p>
    </section>
  );
}

function Verdict({ c, kind }: { c: SpotComparison | null; kind: SpotKind }) {
  if (!c) return (
    <section className="border-t border-foreground pt-4">
      <p className="eyebrow">First check</p>
      <p className="mt-1 font-serif text-[1.3rem]">Baseline saved.</p>
      <p className="mt-1 text-muted">Recheck in {RECHECK_DAYS[kind] / 7} weeks{kind === "spot" ? ", or sooner if you notice a change" : ""}. Use the same coin, distance and daylight.</p>
    </section>
  );
  const v = VERDICT[c.verdict] ?? VERDICT.no_change;
  const warn = v.tone === "warn";
  return (
    <section className="rounded-[4px] border border-rule p-5"
      style={warn ? { borderLeft: `4px solid ${RED}`, background: `color-mix(in srgb, ${RED} 6%, var(--surface))` } : { background: "var(--surface)" }}>
      <p className="font-mono text-[0.72rem] uppercase tracking-[0.08em]" style={{ color: warn ? RED : undefined }}>Compared with last check</p>
      <p className="mt-1 font-serif text-[1.35rem] leading-snug">{v.title}</p>
      {c.alerts.length > 0 && <ul className="mt-2 space-y-1 text-[0.95rem]">{c.alerts.map((a) => <li key={a}>— {a}</li>)}</ul>}
      {kind === "spot" && c.verdict === "no_change" && (
        <p className="mt-2 text-[0.95rem] text-muted">No change doesn&apos;t rule out skin cancer. See a doctor if it bleeds, itches, or looks different to you.</p>
      )}
      <table className="mt-4 w-full text-[0.92rem]">
        <tbody>
          {c.changes.map((x) => (
            <tr key={x.what} className="border-t border-rule">
              <td className="py-2 pr-2 text-muted">{x.what}</td>
              <td className="py-2 pr-2 font-mono text-[0.85rem]">{x.before} → {x.now}</td>
              <td className="py-2 text-right font-mono text-[0.85rem]">{x.delta}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/* ------------------------------------------------------------ photo + tap + measure */
function CheckFlow({ spot, onSaved, onCancel }: { spot: Spot; onSaved: (s: Spot) => void; onCancel: () => void }) {
  const prev = spot.checks[spot.checks.length - 1];
  const [src, setSrc] = useState<string | null>(null);
  const [photo, setPhoto] = useState<{ blob: Blob; dataUrl: string } | null>(null);
  const [mode, setMode] = useState<"spot" | "coin">("spot");
  const [tap, setTap] = useState<{ x: number; y: number } | null>(null);
  const [coinTaps, setCoinTaps] = useState<number[]>([]);
  const [res, setRes] = useState<MeasureResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [sym, setSym] = useState<Record<string, boolean>>({});

  const run = async (t: { x: number; y: number }, edges?: number[], symptoms = sym) => {
    if (!photo) return;
    setBusy(true); setErr(null);
    try {
      const r = await measureSpot(photo.blob, t, {
        coin: spot.coin, kind: spot.kind, location: spot.location, coinEdges: edges,
        prev: prev ? { metrics: prev.metrics, embedding: prev.embedding } : null, symptoms,
      });
      if (!r.ok) setErr("Couldn't find a spot where you tapped. Tap right on the spot.");
      setRes(r.ok ? r : null);
    } catch { setErr("Couldn't reach the analysis server. Check the laptop is running."); }
    finally { setBusy(false); }
  };

  const onImageTap = (e: React.MouseEvent<HTMLDivElement>) => {
    const b = e.currentTarget.getBoundingClientRect();
    const p = { x: (e.clientX - b.left) / b.width, y: (e.clientY - b.top) / b.height };
    if (mode === "spot") { setTap(p); run(p, coinTaps.length === 4 ? coinTaps : undefined); }
    else {
      const next = [...coinTaps, p.x, p.y].slice(-4);
      setCoinTaps(next);
      if (next.length === 4) { setMode("spot"); if (tap) run(tap, next); }
    }
  };

  const save = async () => {
    if (!res?.metrics || !photo) return;
    const date = new Date().toISOString();
    const check: SpotCheck = {
      date, overlay: `data:image/jpeg;base64,${res.overlay_jpg_b64}`, photo: await thumbnail(photo.dataUrl, 320),
      metrics: res.metrics, embedding: res.embedding ?? null, comparison: res.comparison ?? null, concern: res.concern ?? null,
    };
    const s: Spot = { ...spot, checks: [...spot.checks, check], nextDue: addDays(date, RECHECK_DAYS[spot.kind]) };
    await saveSpot(s); onSaved(s);
  };

  if (src && !photo) return <div className="pt-10 md:max-w-[560px]"><CropView src={src} onCancel={() => setSrc(null)} onDone={(p) => setPhoto(p)} /></div>;

  return (
    <div className="grid gap-10 pt-10 md:grid-cols-[minmax(0,4fr)_minmax(0,5fr)] md:gap-14 md:pt-16">
      <section>
        <p className="eyebrow">{spot.name} · {prev ? `check ${spot.checks.length + 1}` : "first check"}</p>
        <h1 className="display mt-5">{photo ? <>Tap the <em>spot.</em></> : <>Photo with a <em>coin.</em></>}</h1>
        <ol className="mt-8 rule-top">
          {[`Put the same coin (${coinLabel(spot.coin)}) flat on the skin, right next to the spot.`,
            "Daylight, no flash. Hold the phone about 15 cm away, straight above.",
            "Fit both the spot and the coin inside the square.",
            "Then tap on the spot so we measure the right one."].map((t, i) => (
            <li key={t} className="grid grid-cols-[34px_1fr] border-b border-rule py-3"><span className="num pt-1">{String(i + 1).padStart(2, "0")}</span><span>{t}</span></li>
          ))}
        </ol>
        {prev && (
          <div className="mt-6">
            <p className="eyebrow mb-2">Last time · {fmtDate(prev.date)} · use as a guide</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={prev.overlay} alt="Previous check" className="w-40 rounded-[2px] border border-rule" />
          </div>
        )}
      </section>

      <section>
        {!photo ? (
          <div className="card space-y-4 p-6"><p className="title">Take the photo</p><PickButtons onPick={setSrc} />
            <button onClick={onCancel} className="w-full text-sm text-muted underline underline-offset-4">Cancel</button></div>
        ) : (
          <div className="space-y-4">
            <div className="relative aspect-square w-full cursor-crosshair overflow-hidden rounded-[4px] border border-rule" onClick={onImageTap}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={res?.overlay_jpg_b64 ? `data:image/jpeg;base64,${res.overlay_jpg_b64}` : photo.dataUrl} alt="Your spot" className="absolute inset-0 h-full w-full object-cover" />
              {tap && <span className="absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-foreground" style={{ left: `${tap.x * 100}%`, top: `${tap.y * 100}%` }} />}
              {coinTaps.length >= 2 && Array.from({ length: coinTaps.length / 2 }).map((_, i) => (
                <span key={i} className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-foreground bg-white" style={{ left: `${coinTaps[i * 2] * 100}%`, top: `${coinTaps[i * 2 + 1] * 100}%` }} />
              ))}
            </div>
            <p className="eyebrow">{busy ? "Measuring…" : mode === "coin" ? `Tap two opposite edges of the coin (${coinTaps.length / 2}/2)` : res ? "Teal outline = measured spot · white ring = coin" : "Tap on the spot"}</p>
            {err && <p className="text-sm" style={{ color: RED }}>{err}</p>}

            {res?.metrics && (
              <div className="card p-5">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  {[["Size", res.metrics.eq_diameter_mm != null ? `${res.metrics.eq_diameter_mm} mm` : "—"],
                    ["Area", res.metrics.area_mm2 != null ? `${res.metrics.area_mm2} mm²` : `${res.metrics.area_pct_of_photo}%`],
                    ["Colours", String(res.metrics.colours)], ["Outline", res.metrics.irregularity < 1.3 ? "Even" : res.metrics.irregularity < 1.7 ? "Slightly uneven" : "Uneven"]]
                    .map(([k, v]) => <div key={k}><p className="num">{k.toUpperCase()}</p><p className="font-serif text-[1.25rem]">{v}</p></div>)}
                </div>
                {!res.metrics.coin_found && (
                  <p className="mt-3 text-sm" style={{ color: RED }}>
                    Coin not found, so sizes are approximate. <button className="underline" onClick={() => { setMode("coin"); setCoinTaps([]); }}>Tap the coin edges</button> or retake with the coin fully visible.
                  </p>
                )}
              </div>
            )}
            {spot.kind === "spot" && (
              <div className="card p-5">
                <p className="eyebrow">Anything a photo can&apos;t show? (tap all that apply)</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {([["bleeds", "Bleeds, crusts or doesn't heal"], ["itches", "Itchy or painful"],
                     ["ugly_duckling", "Looks different from my other moles"]] as const).map(([k, l]) => (
                    <button key={k} className={`chip ${sym[k] ? "chip-on" : ""}`}
                      onClick={() => { const n = { ...sym, [k]: !sym[k] }; setSym(n); if (tap) run(tap, coinTaps.length === 4 ? coinTaps : undefined, n); }}>{l}</button>
                  ))}
                </div>
              </div>
            )}
            {res?.concern && <ConcernBar c={res.concern} />}
            {res?.comparison && <Verdict c={res.comparison} kind={spot.kind} />}

            <div className="grid gap-3 sm:grid-cols-2">
              <button className="btn btn-ghost" onClick={() => { setPhoto(null); setSrc(null); setRes(null); setTap(null); setCoinTaps([]); }}>Retake</button>
              <button className="btn btn-accent" disabled={!res?.metrics || busy} onClick={save}>Save check <span className="font-mono font-normal">→</span></button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

/* ------------------------------------------------------------ new spot form */
function NewSpot({ onCreate, onCancel }: { onCreate: (s: Spot) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<SpotKind>("spot");
  const [loc, setLoc] = useState("arm");
  const [coin, setCoin] = useState("1");
  const [custom, setCustom] = useState("");
  return (
    <div className="grid gap-10 pt-10 md:grid-cols-[minmax(0,4fr)_minmax(0,5fr)] md:gap-14 md:pt-16">
      <section>
        <p className="eyebrow">Spot tracker · new spot</p>
        <h1 className="display mt-5">What are we <em>watching?</em></h1>
        <p className="lede mt-5 text-muted">A mole or dark spot, or a rash patch you&apos;re treating. LuminaSkin measures it with a coin for scale and compares it each time.</p>
      </section>
      <section className="rule-top">
        <div className="border-b border-rule py-5">
          <p className="num">01</p><label className="font-serif text-[1.15rem]">Name it</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Mole on left forearm"
            className="mt-2 w-full rounded-[2px] border border-rule bg-surface px-3 py-2.5 outline-none focus:border-foreground" />
        </div>
        <div className="border-b border-rule py-5">
          <p className="num">02</p><p className="font-serif text-[1.15rem]">What is it?</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {([["spot", "Mole / dark spot", "Recheck every 3 months"], ["rash", "Rash / patch", "Track treatment, every 2 weeks"]] as const).map(([k, l, d]) => (
              <button key={k} onClick={() => setKind(k)} className={`chip ${kind === k ? "chip-on" : ""}`}><b>{l}</b><br /><span className="text-sm opacity-80">{d}</span></button>
            ))}
          </div>
        </div>
        <div className="border-b border-rule py-5">
          <p className="num">03</p><p className="font-serif text-[1.15rem]">Where on the body?</p>
          <div className="mt-2 flex flex-wrap gap-2">{LOCATIONS.map(([k, l]) => <button key={k} onClick={() => setLoc(k)} className={`chip ${loc === k ? "chip-on" : ""}`}>{l}</button>)}</div>
          {["palm", "sole", "nail"].includes(loc) && kind === "spot" && (
            <p className="mt-2 text-sm" style={{ color: RED }}>A new or changing dark spot on the palm, sole or under a nail should be seen by a doctor, even before tracking.</p>
          )}
        </div>
        <div className="border-b border-rule py-5">
          <p className="num">04</p><p className="font-serif text-[1.15rem]">Which coin will you use every time?</p>
          <p className="text-sm text-muted">Coin sizes changed over the years: check the year on your coin. Use the same coin for every check.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {COINS.map(([k, l]) => <button key={k} onClick={() => setCoin(k)} className={`chip ${coin === k ? "chip-on" : ""}`}>{l}</button>)}
            <button onClick={() => setCoin(custom || "other")} className={`chip ${!COINS.some(([k]) => k === coin) ? "chip-on" : ""}`}>Other coin</button>
          </div>
          {!COINS.some(([k]) => k === coin) && (
            <label className="mt-3 flex items-center gap-3 text-[0.95rem]">
              Diameter
              <input inputMode="decimal" value={custom} placeholder="e.g. 25"
                onChange={(e) => { const v = e.target.value.replace(/[^0-9.]/g, ""); setCustom(v); setCoin(v || "other"); }}
                className="w-24 rounded-[2px] border border-rule bg-surface px-3 py-2 outline-none focus:border-foreground" /> mm
              <span className="text-sm text-muted">(measure it once with a ruler)</span>
            </label>
          )}
        </div>
        <div className="mt-6 flex flex-col-reverse gap-3 md:flex-row md:items-center md:justify-between">
          <button onClick={onCancel} className="text-sm text-muted underline underline-offset-4">Cancel</button>
          <button className="btn btn-accent md:min-w-[220px]" disabled={coin === "other" || (!COINS.some(([k]) => k === coin) && !(Number(coin) >= 10 && Number(coin) <= 40))} onClick={() => {
            const now = new Date().toISOString();
            onCreate({ id: newId(), name: name.trim() || (kind === "spot" ? "My spot" : "My rash"), kind, location: loc, coin, created: now, nextDue: now, checks: [] });
          }}>Continue to photo <span className="font-mono font-normal">→</span></button>
        </div>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------ one spot's history */
function SpotDetail({ spot, onRecheck, onBack, onDeleted }: { spot: Spot; onRecheck: () => void; onBack: () => void; onDeleted: () => void }) {
  const last = spot.checks[spot.checks.length - 1];
  const first = spot.checks[0];
  const due = daysUntil(spot.nextDue);
  return (
    <div className="pt-10 md:pt-16">
      <button onClick={onBack} className="text-sm text-muted underline underline-offset-4">← All spots</button>
      <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div>
          <p className="eyebrow">{spot.kind === "spot" ? "Mole / spot" : "Rash / patch"} · {LOCATIONS.find(([k]) => k === spot.location)?.[1]} · {spot.checks.length} check{spot.checks.length === 1 ? "" : "s"}</p>
          <h1 className="display mt-4">{spot.name}</h1>
        </div>
        <div className="flex flex-wrap gap-3">
          <button className="btn btn-ink" onClick={onRecheck}>Recheck now <span className="font-mono font-normal">→</span></button>
          <button className="btn btn-ghost" onClick={() => calendarReminder(spot)}>Add reminder to calendar</button>
        </div>
      </div>
      <p className="num mt-4">{due <= 0 ? "RECHECK DUE NOW" : `NEXT CHECK IN ${due} DAY${due === 1 ? "" : "S"} · ${fmtDate(spot.nextDue).toUpperCase()}`}</p>

      <div className="mt-8 grid gap-10 md:grid-cols-[minmax(0,4fr)_minmax(0,5fr)] md:gap-14">
        <section>
          <div className="grid grid-cols-2 gap-3">
            {[[first, "First"], [last, "Latest"]].map(([c, l]) => (
              <figure key={l as string}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={(c as SpotCheck).overlay} alt={l as string} className="aspect-square w-full rounded-[2px] border border-rule object-cover" />
                <figcaption className="mt-1 num">{(l as string).toUpperCase()} · {fmtDate((c as SpotCheck).date).toUpperCase()}</figcaption>
                <p className="text-sm">{size(c as SpotCheck)}</p>
              </figure>
            ))}
          </div>
        </section>
        <section className="space-y-6">
          {last.concern && <ConcernBar c={last.concern} />}
          <Verdict c={last.comparison} kind={spot.kind} />
          <div className="rule-top">
            <p className="eyebrow pt-3">History</p>
            {[...spot.checks].reverse().map((c) => (
              <div key={c.date} className="grid grid-cols-[56px_1fr_auto] items-center gap-3 border-b border-rule py-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={c.overlay} alt="" className="h-14 w-14 rounded-[2px] object-cover" />
                <div><p className="num">{fmtDate(c.date).toUpperCase()}</p><p className="text-[0.95rem]">{size(c)} · {c.metrics.colours} colour{c.metrics.colours > 1 ? "s" : ""}</p></div>
                <span className="font-mono text-[0.75rem] text-muted">{c.comparison ? (VERDICT[c.comparison.verdict]?.title.split(".")[0] ?? "") : "Baseline"}</span>
              </div>
            ))}
          </div>
          <p className="text-sm text-muted">Measurements are approximate (within about 1 mm with the coin). This tracker doesn&apos;t diagnose skin cancer; it helps you notice change. If you&apos;re worried, see a doctor.</p>
          <button className="text-sm text-muted underline underline-offset-4" onClick={async () => { await deleteSpot(spot.id); onDeleted(); }}>Delete this spot</button>
        </section>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ page */
export default function SpotsPage() {
  const [spots, setSpots] = useState<Spot[] | null>(null);
  const [view, setView] = useState<{ v: "list" } | { v: "new" } | { v: "check"; spot: Spot } | { v: "detail"; id: string }>({ v: "list" });
  const reload = async () => setSpots(await listSpots());
  useEffect(() => {
    reload();
    const id = new URLSearchParams(window.location.search).get("id");   // deep link: /spots?id=<spot>
    if (id) setView({ v: "detail", id });
  }, []);
  if (!spots) return null;

  if (view.v === "new") return <NewSpot onCancel={() => setView({ v: "list" })} onCreate={(s) => setView({ v: "check", spot: s })} />;
  if (view.v === "check") return <CheckFlow spot={view.spot} onCancel={() => setView(view.spot.checks.length ? { v: "detail", id: view.spot.id } : { v: "list" })}
    onSaved={async (s) => { await reload(); setView({ v: "detail", id: s.id }); }} />;
  if (view.v === "detail") {
    const s = spots.find((x) => x.id === view.id);
    if (s) return <SpotDetail spot={s} onBack={() => setView({ v: "list" })} onRecheck={() => setView({ v: "check", spot: s })}
      onDeleted={async () => { await reload(); setView({ v: "list" }); }} />;
  }

  return (
    <div className="pt-10 md:pt-16">
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div>
          <p className="eyebrow">Spot tracker · stored only on this device</p>
          <h1 className="display mt-5">Watch how a spot <em>changes.</em></h1>
          <p className="lede mt-5 text-muted">Measure a mole or a rash patch with a coin for scale, then recheck it over time. Growth, new colours or a more uneven outline are flagged.</p>
        </div>
        <button className="btn btn-ink" onClick={() => setView({ v: "new" })}>Track a new spot <span className="font-mono font-normal">→</span></button>
      </div>
      <div className="mt-10 rule-top">
        {spots.length === 0 && (
          <div className="py-16 text-center">
            <p className="font-serif text-[1.4rem]">No spots tracked yet.</p>
            <p className="mt-2 text-muted">Start with a mole you want to keep an eye on, or a patch you&apos;re treating.</p>
          </div>
        )}
        {spots.map((s) => {
          const last = s.checks[s.checks.length - 1];
          const due = daysUntil(s.nextDue);
          const warn = last?.comparison && ["changed_see_doctor", "bigger_see_doctor"].includes(last.comparison.verdict);
          return (
            <button key={s.id} onClick={() => setView({ v: "detail", id: s.id })}
              className="grid w-full grid-cols-[72px_1fr_auto] items-center gap-4 border-b border-rule py-5 text-left hover:bg-surface/60 sm:grid-cols-[96px_1fr_auto]">
              {last ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={last.overlay} alt="" className="h-[72px] w-[72px] rounded-[2px] object-cover sm:h-24 sm:w-24" />
              ) : <span className="h-[72px] w-[72px] rounded-[2px] border border-dashed border-rule sm:h-24 sm:w-24" />}
              <div>
                <p className="font-serif text-[1.3rem] leading-tight">{s.name}</p>
                <p className="text-[0.95rem] text-muted">{LOCATIONS.find(([k]) => k === s.location)?.[1]} · {last ? size(last) : "no checks yet"}</p>
                {warn && <p className="mt-1 font-mono text-[0.72rem] uppercase tracking-[0.08em]" style={{ color: RED }}>Changed · see a doctor</p>}
                {!warn && last?.concern && last.concern.level !== "low" && (
                  <p className="mt-1 font-mono text-[0.72rem] uppercase tracking-[0.08em]" style={{ color: last.concern.level === "high" ? RED : "#9A5212" }}>
                    Concern {last.concern.level} · get it checked
                  </p>
                )}
              </div>
              <span className={`font-mono text-[0.72rem] uppercase tracking-[0.08em] ${due <= 0 ? "" : "text-muted"}`}>
                {due <= 0 ? "Recheck due" : `In ${due} d`}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
