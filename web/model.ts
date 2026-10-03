export interface Transmitter {
  id: number; x: number; y: number; power: number; frequency: number; phase: number; enabled: boolean;
}
export const MAX_SOURCES = 32;
export const clamp = (x: number, a: number, b: number) => Math.min(b, Math.max(a, x));

export class Scene {
  sources: Transmitter[] = [{ id: 1, x: .8, y: .45, power: 1, frequency: 2.4, phase: 0, enabled: true }];
  selected = 1;
  nextId = 2;
  current() { return this.sources.find(s => s.id === this.selected)!; }
  add(x = .5, y = .5) {
    if (this.sources.length >= MAX_SOURCES) return null;
    const s = { id: this.nextId++, x: clamp(x, .015, .985), y: clamp(y, .015, .985), power: 1, frequency: 2.4, phase: 0, enabled: true };
    this.sources.push(s); this.selected = s.id;
    return s;
  }
  remove() {
    if (this.sources.length <= 1) return;
    this.sources = this.sources.filter(s => s.id !== this.selected);
    this.selected = this.sources[0].id;
  }
  move(id: number, x: number, y: number) {
    const s = this.sources.find(s => s.id === id);
    if (s) { s.x = clamp(x, .015, .985); s.y = clamp(y, .015, .985); }
  }
  hit(x: number, y: number, width: number, height: number) {
    let found: number | null = null, distance = 17;
    for (const s of this.sources) {
      const d = Math.hypot((s.x-x)*width, (s.y-y)*height);
      if (d < distance) { distance = d; found = s.id; }
    }
    return found;
  }
}

export interface Settings {
  paused: boolean; speed: number; loss: number; transmission: number;
  exposure: number; mode: number; walls: boolean; showWalls: boolean; markers: boolean;
}
export const defaultSettings = (): Settings => ({
  paused: false, speed: 1, loss: .001, transmission: .15, exposure: 5,
  mode: 0, walls: true, showWalls: true, markers: true,
});
export function phaseOffsets(interval: number, frequency: number) {
  if (!Number.isFinite(interval) || interval < 1 || interval > 180) throw new Error('Phase step must be 1–180 degrees.');
  if (!Number.isFinite(frequency) || frequency <= 0) throw new Error('Frequency must be positive.');
  const ratio = 360/interval, nearest = Math.round(ratio);
  const count = Math.abs(ratio-nearest) <= 1e-7*Math.abs(ratio) ? nearest : Math.ceil(ratio);
  return Array.from({ length: count }, (_, i) => i*interval/(360*.028*frequency/2.4));
}
