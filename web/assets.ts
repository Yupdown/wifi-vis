import wallUrl from '../wifivis/assets/walls.png';
import paletteUrl from '../wifivis/assets/palette.png';

export interface WallMap { pixels: Uint8Array; width: number; height: number; inverted: boolean; name: string; }
export interface Reference { wall: WallMap; palette: Uint8Array; }

async function bitmap(url: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}`);
  return createImageBitmap(await response.blob(), { colorSpaceConversion: 'none' });
}
function raster(image: ImageBitmap, width = image.width, height = image.height) {
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(image, 0, 0, width, height);
  return ctx.getImageData(0, 0, width, height).data;
}
export async function loadReference(): Promise<Reference> {
  const [wall, palette] = await Promise.all([bitmap(wallUrl), bitmap(paletteUrl)]);
  try {
    const data = raster(wall), colors = raster(palette);
    return {
      wall: { pixels: Uint8Array.from({ length: wall.width*wall.height }, (_, i) => data[i*4]), width: wall.width, height: wall.height, inverted: false, name: '' },
      palette: Uint8Array.from({ length: 256*3 }, (_, i) => colors[Math.floor(i/3)*4+i%3]),
    };
  } finally { wall.close(); palette.close(); }
}
function median(values: number[]) {
  values.sort((a, b) => a-b);
  const n = values.length;
  return n ? (values[Math.floor(n/2)]+values[Math.floor((n-1)/2)])/2 : 0;
}
export async function loadWall(file: File, invert?: boolean): Promise<WallMap> {
  let image: ImageBitmap;
  if (/\.tiff?$/i.test(file.name) || file.type === 'image/tiff') {
    const { default: tiff } = await import('utif');
    const buffer = await file.arrayBuffer(), directory = tiff.decode(buffer)[0];
    if (!directory) throw new Error('The TIFF file has no image.');
    tiff.decodeImage(buffer, directory);
    image = await createImageBitmap(new ImageData(new Uint8ClampedArray(tiff.toRGBA8(directory)), directory.width, directory.height));
  } else image = await createImageBitmap(file, { colorSpaceConversion: 'none' });
  try {
    const scale = Math.min(2, 1074/Math.max(image.width, image.height), Math.sqrt(360864/(image.width*image.height)));
    const width = Math.max(2, Math.round(image.width*scale)), height = Math.max(2, Math.round(image.height*scale));
    const rgba = raster(image, width, height), gray = new Uint8Array(width*height);
    let transparent = false;
    const border: number[] = [], visible: number[] = [];
    for (let i = 0; i < gray.length; i++) {
      gray[i] = Math.round(.299*rgba[i*4]+.587*rgba[i*4+1]+.114*rgba[i*4+2]);
      if (rgba[i*4+3] < 128) transparent = true;
      else visible.push(gray[i]);
      if (i < width || i >= width*(height-1) || i%width === 0 || i%width === width-1) border.push(gray[i]);
    }
    const inverted = invert ?? (transparent ? visible.length > 0 && median(visible) < 128 : median(border) >= 128);
    const pixels = Uint8Array.from(gray, (v, i) => Math.round((inverted ? 255-v : v)*rgba[i*4+3]/255));
    return { pixels, width, height, inverted, name: file.name };
  } finally { image.close(); }
}
