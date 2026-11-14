export type Area = { x: number; y: number; width: number; height: number };

function load(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

/** Crop the selected square and scale it to `size` px. Returns a JPEG blob and data URL. */
export async function cropSquare(src: string, area: Area, size = 768, quality = 0.9) {
  const img = await load(src);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  canvas.getContext("2d")!.drawImage(img, area.x, area.y, area.width, area.height, 0, 0, size, size);
  const blob: Blob = await new Promise((r) => canvas.toBlob((b) => r(b!), "image/jpeg", quality));
  return { blob, dataUrl: canvas.toDataURL("image/jpeg", quality) };
}

/** Small thumbnail for local history (keeps storage small). */
export async function thumbnail(dataUrl: string, size = 256) {
  const img = await load(dataUrl);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  canvas.getContext("2d")!.drawImage(img, 0, 0, size, size);
  return canvas.toDataURL("image/jpeg", 0.7);
}

/** Photo with the heatmap PNG drawn on top (50% opacity), as a small JPEG for reports. */
export async function heatmapOverlay(photoDataUrl: string, heatmapB64: string, size = 320) {
  const [img, hm] = await Promise.all([load(photoDataUrl), load(`data:image/png;base64,${heatmapB64}`)]);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(img, 0, 0, size, size);
  ctx.globalAlpha = 0.5;
  ctx.drawImage(hm, 0, 0, size, size);
  return canvas.toDataURL("image/jpeg", 0.8);
}
