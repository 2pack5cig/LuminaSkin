"use client";
import { useCallback, useState } from "react";
import Cropper from "react-easy-crop";
import { cropSquare, type Area } from "@/lib/image";
import type { Photo, Shot } from "@/lib/types";

const MAX_PHOTOS = 5;

export const SHOT_INFO: Record<Shot, { title: string; how: string; required?: boolean }> = {
  close_up: {
    title: "Close-up",
    how: "Hold the phone about a hand-length (15 cm) from the rash so it fills the square. Use daylight, no flash, and tap to focus.",
    required: true,
  },
  angle: {
    title: "At an angle",
    how: "Same spot, but tilt the phone about 45° to the side so bumps, blisters and scales are visible.",
  },
  distance: {
    title: "From a distance",
    how: "Step back so we can see where on the body it is, for example the whole arm, leg or back.",
  },
  extra_close_up: {
    title: "Another close-up",
    how: "A close-up of a different spot of the same rash, a hand-length away.",
  },
};

function CropView({ src, onDone, onCancel }: { src: string; onDone: (p: { blob: Blob; dataUrl: string }) => void; onCancel: () => void }) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [area, setArea] = useState<Area | null>(null);
  const onCropComplete = useCallback((_: Area, px: Area) => setArea(px), []);
  return (
    <div className="space-y-4">
      <p className="font-medium">Fit the rash inside the square</p>
      <div className="relative w-full aspect-square rounded-2xl overflow-hidden bg-black">
        <Cropper image={src} crop={crop} zoom={zoom} aspect={1} onCropChange={setCrop}
          onZoomChange={setZoom} onCropComplete={onCropComplete} showGrid={false} />
      </div>
      <input type="range" min={1} max={4} step={0.05} value={zoom}
        onChange={(e) => setZoom(Number(e.target.value))} className="w-full accent-[#0f766e]" />
      <div className="flex gap-3">
        <button onClick={onCancel} className="flex-1 rounded-2xl border py-3">Retake</button>
        <button disabled={!area} className="flex-1 rounded-2xl bg-brand text-white py-3 disabled:opacity-50"
          onClick={async () => onDone(await cropSquare(src, area!))}>Use photo</button>
      </div>
    </div>
  );
}

function PickButtons({ onPick }: { onPick: (src: string) => void }) {
  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) onPick(URL.createObjectURL(f));
    e.target.value = "";
  };
  return (
    <div className="grid grid-cols-2 gap-3">
      <label className="rounded-2xl bg-brand text-white text-center py-3 font-medium">
        Take photo
        <input type="file" accept="image/*" capture="environment" className="hidden" onChange={pick} />
      </label>
      <label className="rounded-2xl border border-brand text-brand text-center py-3 font-medium">
        Gallery
        <input type="file" accept="image/*" className="hidden" onChange={pick} />
      </label>
    </div>
  );
}

/** Guided capture: close-up (required) -> angle (optional) -> distance (optional), plus extra close-ups. */
export default function CaptureStep({ onDone }: { onDone: (photos: Photo[]) => void }) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [skipped, setSkipped] = useState<Shot[]>([]);
  const [src, setSrc] = useState<string | null>(null);
  const [extra, setExtra] = useState(false);

  const has = (s: Shot) => photos.some((p) => p.shot === s) || skipped.includes(s);
  const next: Shot | null = extra ? "extra_close_up"
    : !has("close_up") ? "close_up" : !has("angle") ? "angle" : !has("distance") ? "distance" : null;

  if (src && next) {
    return (
      <div className="pt-4">
        <CropView src={src} onCancel={() => setSrc(null)}
          onDone={(p) => { setPhotos([...photos, { ...p, shot: next }]); setSrc(null); setExtra(false); }} />
      </div>
    );
  }

  return (
    <div className="pt-6 space-y-5">
      {photos.length === 0 && (
        <div>
          <h1 className="text-2xl font-semibold">Check a skin rash</h1>
          <p className="text-black/60 mt-1">Up to 3 photos of the same rash give a more accurate result: a close-up, one at an angle, and one from a distance.</p>
        </div>
      )}

      {photos.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {photos.map((p, i) => (
            <div key={i} className="shrink-0 text-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={p.dataUrl} alt={SHOT_INFO[p.shot].title} className="w-20 h-20 rounded-xl object-cover" />
              <p className="text-[11px] text-black/60 mt-1">{SHOT_INFO[p.shot].title}</p>
              <button className="text-[11px] text-red-700" onClick={() => setPhotos(photos.filter((_, j) => j !== i))}>Remove</button>
            </div>
          ))}
        </div>
      )}

      {next && (
        <div className="rounded-2xl bg-white border p-4 space-y-3">
          <p className="text-xs uppercase tracking-wide text-brand font-semibold">
            Photo {Math.min(photos.length + 1, MAX_PHOTOS)} · {SHOT_INFO[next].required ? "required" : "optional"}
          </p>
          <p className="font-semibold text-lg">{SHOT_INFO[next].title}</p>
          <p className="text-sm text-black/70">{SHOT_INFO[next].how}</p>
          <PickButtons onPick={setSrc} />
          {!SHOT_INFO[next].required && (
            <button className="w-full text-sm text-black/60 py-1"
              onClick={() => (extra ? setExtra(false) : setSkipped([...skipped, next]))}>
              {extra ? "Cancel" : "Skip this photo"}
            </button>
          )}
        </div>
      )}

      {photos.some((p) => p.shot === "close_up") && (
        <div className="space-y-3">
          {!next && photos.length < MAX_PHOTOS && (
            <button onClick={() => setExtra(true)} className="w-full rounded-2xl border border-brand text-brand py-3">
              + Add another close-up
            </button>
          )}
          <button onClick={() => onDone(photos)} className="w-full rounded-2xl bg-brand text-white py-4 font-medium">
            Continue with {photos.length} photo{photos.length > 1 ? "s" : ""}
          </button>
        </div>
      )}

      {photos.length === 0 && (
        <ul className="text-sm text-black/60 space-y-1 list-disc pl-5">
          <li>Use daylight, no flash</li>
          <li>Hold steady and tap the screen to focus</li>
          <li>Include some normal skin around the rash</li>
        </ul>
      )}
    </div>
  );
}
