// Spot tracker storage: only on this device (IndexedDB). No account, no server copy.
import { get, set } from "idb-keyval";
import type { Spot } from "./types";

const KEY = "spots-v1";
export const RECHECK_DAYS: Record<string, number> = { spot: 84, rash: 14 };   // moles ~3 months; rashes ~2 weeks

export async function listSpots(): Promise<Spot[]> {
  try { return ((await get<Spot[]>(KEY)) ?? []).sort((a, b) => a.nextDue.localeCompare(b.nextDue)); } catch { return []; }
}
export async function saveSpot(s: Spot) {
  const all = await listSpots();
  await set(KEY, [s, ...all.filter((x) => x.id !== s.id)]);
}
export async function deleteSpot(id: string) {
  await set(KEY, (await listSpots()).filter((s) => s.id !== id));
}
export const newId = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
export const addDays = (iso: string, d: number) => new Date(new Date(iso).getTime() + d * 864e5).toISOString();
export const daysUntil = (iso: string) => Math.ceil((new Date(iso).getTime() - Date.now()) / 864e5);

/** Calendar reminder (.ics) - works on iPhone and Android without any server. */
export function calendarReminder(spot: Spot) {
  const d = new Date(spot.nextDue);
  const ymd = (x: Date) => x.toISOString().slice(0, 10).replace(/-/g, "");
  const end = new Date(d.getTime() + 864e5);
  const ics = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//LuminaSkin//Spot tracker//EN", "BEGIN:VEVENT",
    `UID:${spot.id}-${ymd(d)}@luminaskin`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
    `DTSTART;VALUE=DATE:${ymd(d)}`, `DTEND;VALUE=DATE:${ymd(end)}`,
    `SUMMARY:LuminaSkin: recheck "${spot.name}"`,
    "DESCRIPTION:Open LuminaSkin > Spots and recheck this spot with the same coin\\, in daylight.",
    "BEGIN:VALARM", "TRIGGER:PT9H", "ACTION:DISPLAY", "DESCRIPTION:Recheck your spot in LuminaSkin", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
  const a = document.createElement("a");
  a.href = url; a.download = `luminaskin-recheck-${spot.name.replace(/\W+/g, "-").toLowerCase()}.ics`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
