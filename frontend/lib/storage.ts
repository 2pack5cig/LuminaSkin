// Scan history lives only on this device (IndexedDB). Nothing is stored on a server.
import { get, set } from "idb-keyval";
import type { Scan } from "./types";

const KEY = "scans-v1";

export async function listScans(): Promise<Scan[]> {
  try {
    return ((await get<Scan[]>(KEY)) ?? []).sort((a, b) => b.date.localeCompare(a.date));
  } catch {
    return [];
  }
}

export async function saveScan(scan: Scan) {
  const all = await listScans();
  await set(KEY, [scan, ...all.filter((s) => s.id !== scan.id)]);
}

export async function deleteScan(id: string) {
  await set(KEY, (await listScans()).filter((s) => s.id !== id));
}
