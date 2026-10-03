import { WaveGPU } from './gpu';
import { phaseOffsets, type Scene, type Settings, type Transmitter } from './model';

function paletteForGif(colors: Uint8Array) {
  const palette: number[][] = [];
  for (let i = 0; i < 240; i++) { const n = Math.round(i*255/239)*3; palette.push(Array.from(colors.slice(n, n+3))); }
  for (let i = 0; i < 14; i++) { const v = Math.round(i*255/13); palette.push([v, v, v]); }
  return [...palette, [77, 255, 232], [4, 6, 10]];
}

export class GifExport {
  readonly offsets: number[];
  readonly sources: Transmitter[];
  readonly settings: Settings;
  readonly selected: number;
  private gpu: WaveGPU | null;
  private worker: Worker;
  private overlay: CanvasRenderingContext2D | null = null;
  private advanced = 0;
  private waiting = false;
  captured = 0;
  encoded = 0;
  done = false;
  error = '';
  result: Blob | null = null;
  constructor(gpu: WaveGPU, scene: Scene, settings: Settings, interval: number) {
    this.offsets = phaseOffsets(interval, scene.current().frequency);
    this.sources = structuredClone(scene.sources); this.selected = scene.selected; this.settings = { ...settings };
    this.gpu = gpu.clone();
    this.worker = new Worker(new URL('./gif.worker.ts', import.meta.url), { type: 'module' });
    this.worker.postMessage({ type: 'init', palette: paletteForGif(gpu.colors) });
    this.worker.onmessage = e => {
      if (e.data.type === 'frame') { this.encoded++; this.waiting = false; }
      if (e.data.type === 'done') { this.result = new Blob([e.data.bytes], { type: 'image/gif' }); this.done = true; }
      if (e.data.type === 'error') { this.error = e.data.message; this.done = true; }
    };
    this.worker.onerror = e => { this.error = e.message || 'GIF worker failed'; this.done = true; };
    if (settings.markers) {
      const canvas = document.createElement('canvas'); canvas.width = gpu.width; canvas.height = gpu.height;
      this.overlay = canvas.getContext('2d', { willReadFrequently: true });
    }
  }
  advance() {
    if (this.done || this.waiting || !this.gpu) return;
    try {
      const gpu = this.gpu, offset = this.offsets[this.captured], target = Math.ceil(offset);
      gpu.step(this.sources, target-this.advanced, this.settings); this.advanced = target;
      gpu.render(this.settings, 1-(target-offset));
      let pixels = gpu.readPixels();
      if (this.overlay) {
        const ctx = this.overlay;
        ctx.putImageData(new ImageData(new Uint8ClampedArray(pixels), gpu.width, gpu.height), 0, 0);
        ctx.font = '12px sans-serif';
        for (const s of this.sources) {
          const x = s.x*gpu.width, y = s.y*gpu.height;
          ctx.strokeStyle = ctx.fillStyle = !s.enabled ? '#8c8c8c' : s.id === this.selected ? '#4dffe8' : '#ffffff';
          ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 8, 0, 2*Math.PI); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(x-4, y); ctx.lineTo(x+4, y); ctx.moveTo(x, y-4); ctx.lineTo(x, y+4); ctx.stroke();
          ctx.fillText(`TX ${s.id}`, s.x < .7 ? x+12 : x-40, y+4);
        }
        pixels = new Uint8Array(ctx.getImageData(0, 0, gpu.width, gpu.height).data);
      }
      this.worker.postMessage({ type: 'frame', index: this.captured, width: gpu.width, height: gpu.height, pixels: pixels.buffer }, [pixels.buffer]);
      this.waiting = true; this.captured++;
      if (this.captured === this.offsets.length) {
        this.worker.postMessage({ type: 'finish' }); gpu.close(); this.gpu = null;
      }
    } catch (error) { this.error = String(error); this.done = true; }
  }
  close() { this.worker.terminate(); this.gpu?.close(); this.gpu = null; }
}

export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = name; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
