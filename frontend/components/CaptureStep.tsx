"use client";
import { useCallback, useState } from "react";
import Cropper from "react-easy-crop";
import { cropSquare, type Area } from "@/lib/image";
import type { Photo, Shot } from "@/lib/types";

const MAX_PHOTOS = 5;

export const SHOT_INFO: Record<Shot, { title: string; how: string; required?: boolean }> = {
  close_up: {
    title: "Close-up",
    how: "Hold the phone about a hand-length (15 cm) from the rash so it fills the square. Daylight, no flash, tap to focus.",
    required: true,
  },
  angle: {
    title: "At an angle",
    how: "Same spot, tilt the phone about 45° to the side so bumps, blisters and scales are visible.",
  },
  distance: {
    title: "From a distance",
    how: "Step back so we can see where on the body it is: the whole arm, leg or back.",
  },
  extra_close_up: {
    title: "Another close-up",
    how: "A close-up of a different spot of the same rash, a hand-length away.",
  },
};
const ORDER: Shot[] = ["close_up", "angle", "distance"];

function CropView({ src, onDone, onCancel }: { src: string; onDone: (p: { blob: Blob; dataUrl: string }) => void; onCancel: () => void }) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [area, setArea] = useState<Area | null>(null);
  const onCropComplete = useCallback((_: Area, px: Area) => setArea(px), []);
  return (
    <div className="space-y-4">
      <p className="eyebrow">Fit the rash inside the square</p>
      <div className="relative w-full aspect-square overflow-hidden rounded-[4px] bg-foreground">
        <Cropper image={src} crop={crop} zoom={zoom} aspect={1} onCropChange={setCrop}
          onZoomChange={setZoom} onCropComplete={onCropComplete} showGrid={false} />
      </div>
      <label className="flex items-center gap-3 text-sm text-muted">
        <span className="num">ZOOM</span>
        <input type="range" min={1} max={4} step={0.05} value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))} className="w-full accent-[#16130F]" />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <button onClick={onCancel} className="btn btn-ghost">Retake</button>
        <button disabled={!area} className="btn btn-ink" onClick={async () => onDone(await cropSquare(src, area!))}>
          Use photo <span className="font-mono font-normal">→</span>
        </button>
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
      <label className="btn btn-ink">
        Take photo
        <input type="file" accept="image/*" capture="environment" className="hidden" onChange={pick} />
      </label>
      <label className="btn btn-ghost">
        From gallery
        <input type="file" accept="image/*" className="hidden" onChange={pick} />
      </label>
    </div>
  );
}

/** Step 1: guided capture. Close-up (required) -> angle (optional) -> distance (optional), plus extra close-ups. */
export default function CaptureStep({ onDone }: { onDone: (photos: Photo[]) => void }) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [skipped, setSkipped] = useState<Shot[]>([]);
  const [src, setSrc] = useState<string | null>(null);
  const [extra, setExtra] = useState(false);

  const has = (s: Shot) => photos.some((p) => p.shot === s) || skipped.includes(s);
  const next: Shot | null = extra ? "extra_close_up"
    : !has("close_up") ? "close_up" : !has("angle") ? "angle" : !has("distance") ? "distance" : null;
  const ready = photos.some((p) => p.shot === "close_up");

  return (
    <div className="grid gap-10 pt-10 md:grid-cols-[minmax(0,5fr)_minmax(0,4fr)] md:gap-14 md:pt-16">
      {/* ---------- left: copy + plan ---------- */}
      <section>
        <p className="eyebrow">Step 1 of 3 · Photos</p>
        <h1 className="display mt-5">Show us the rash, <em>from three sides.</em></h1>
        <p className="lede mt-6 text-muted">
          A close-up, an angle and a distance shot give the most accurate result. Only the close-up is required.
        </p>

        <ol className="mt-10 rule-top">
          {ORDER.map((s, i) => {
            const p = photos.find((x) => x.shot === s);
            const isSkipped = skipped.includes(s);
            return (
              <li key={s} className="grid grid-cols-[40px_1fr_auto] items-center gap-3 border-b border-rule py-4">
                <span className="num">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <p className="font-medium leading-tight">{SHOT_INFO[s].title}</p>
                  <p className="text-sm text-muted">{SHOT_INFO[s].required ? "Required" : "Optional"}</p>
                </div>
                {p ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.dataUrl} alt={SHOT_INFO[s].title} className="h-14 w-14 rounded-[2px] object-cover" />
                ) : (
                  <span className="num">{isSkipped ? "SKIPPED" : next === s ? "NEXT" : "—"}</span>
                )}
              </li>
            );
          })}
        </ol>

        {photos.filter((p) => p.shot === "extra_close_up").length > 0 && (
          <p className="mt-3 text-sm text-muted">
            + {photos.filter((p) => p.shot === "extra_close_up").length} extra close-up(s)
          </p>
        )}
        {photos.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1">
            {photos.map((p, i) => (
              <button key={i} className="text-sm text-muted underline underline-offset-4 hover:text-foreground"
                onClick={() => setPhotos(photos.filter((_, j) => j !== i))}>
                Remove {SHOT_INFO[p.shot].title.toLowerCase()}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ---------- right: the active step ---------- */}
      <section className="md:pt-2">
        {src && next ? (
          <CropView src={src} onCancel={() => setSrc(null)}
            onDone={(p) => { setPhotos([...photos, { ...p, shot: next }]); setSrc(null); setExtra(false); }} />
        ) : next ? (
          <div className="card p-6 sm:p-7 space-y-5">
            <div className="flex items-baseline justify-between">
              <p className="eyebrow">Photo {Math.min(photos.length + 1, MAX_PHOTOS)}</p>
              <p className="eyebrow">{SHOT_INFO[next].required ? "Required" : "Optional"}</p>
            </div>
            <h2 className="title">{SHOT_INFO[next].title}</h2>
            <p className="text-muted">{SHOT_INFO[next].how}</p>
            <PickButtons onPick={setSrc} />
            {!SHOT_INFO[next].required && (
              <button className="w-full text-sm text-muted underline underline-offset-4 hover:text-foreground"
                onClick={() => (extra ? setExtra(false) : setSkipped([...skipped, next]))}>
                {extra ? "Cancel" : "Skip this photo"}
              </button>
            )}
          </div>
        ) : (
          <div className="card p-6 sm:p-7">
            <p className="eyebrow">All set</p>
            <h2 className="title mt-3">Photos ready.</h2>
            <p className="mt-2 text-muted">Add another close-up of a different spot, or continue to the questions.</p>
          </div>
        )}

        {ready && !src && (
          <div className="mt-5 grid gap-3">
            {!next && photos.length < MAX_PHOTOS && (
              <button onClick={() => setExtra(true)} className="btn btn-ghost">+ Add another close-up</button>
            )}
            <button onClick={() => onDone(photos)} className="btn btn-accent">
              Continue with {photos.length} photo{photos.length > 1 ? "s" : ""} <span className="font-mono font-normal">→</span>
            </button>
          </div>
        )}

        {!ready && !src && (
          <ul className="mt-6 space-y-1.5 text-sm text-muted">
            <li>— Daylight, no flash</li>
            <li>— Hold steady and tap the screen to focus</li>
            <li>— Include some normal skin around the rash</li>
            <li>— Photos are not stored on any server</li>
          </ul>
        )}
      </section>
    </div>
  );
}
