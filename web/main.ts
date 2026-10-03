import './style.css';
import {
  ImGui as I, ImGuiImplWeb as Backend, ImVec2, ImVec4, ImGuiCol,
  ImGuiWindowFlags as WindowFlags, ImGuiChildFlags, ImGuiKey, ImGuiMouseCursor,
  type ImTextureRef,
} from '@mori2003/jsimgui';
import { loadReference, loadWall, type Reference, type WallMap } from './assets';
import { WaveGPU } from './gpu';
import { Scene, defaultSettings, MAX_SOURCES, phaseOffsets, clamp } from './model';
import { GifExport, download } from './export';

const v2 = (x: number, y: number) => new ImVec2(x, y);
const v4 = (r: number, g: number, b: number, a = 1) => new ImVec4(r, g, b, a);
const muted = (text: string) => I.TextColored(v4(.48, .58, .69), text);
const section = (text: string) => { I.Spacing(); I.TextColored(v4(.36, .85, .82), text); I.Separator(); };
const color = (r: number, g: number, b: number, a = 1) => I.ColorConvertFloat4ToU32(v4(r, g, b, a));
type Rect = { x: number; y: number; width: number; height: number };

class Application {
  scene = new Scene();
  settings = defaultSettings();
  gpu: WaveGPU;
  adding = false;
  dragging: number | null = null;
  canvasRect: Rect | null = null;
  // Development-only browser tests use actual ImGui item rectangles for input.
  uiRects: Record<string, Rect> = {};
  wallName = '';
  wallInverted = false;
  wallError = '';
  private wallFile: File | null = null;
  private wallLoadId = 0;
  private pendingWall: WallMap | null = null;
  private pendingReference = false;
  private outputRef: ImTextureRef;
  private paletteRef: ImTextureRef;
  gifPhaseStep = 7.2;
  gifJob: GifExport | null = null;
  gifMessage = '';
  gifError = false;
  lastGif: Blob | null = null;
  private pendingGif = false;
  private accumulator = 0;
  private previousTime = performance.now();
  private stopped = false;
  private frameId = 0;

  constructor(readonly canvas: HTMLCanvasElement, readonly gl: WebGL2RenderingContext, readonly reference: Reference) {
    this.gpu = new WaveGPU(gl, 336, 1074, reference.wall, reference.palette);
    this.outputRef = Backend.RegisterTexture(this.gpu.output);
    this.paletteRef = Backend.RegisterTexture(this.gpu.palette);
    this.gpu.step(this.scene.sources, 700, this.settings);
    const input = document.querySelector<HTMLInputElement>('#wall-file')!;
    input.addEventListener('change', () => {
      const file = input.files?.[0]; input.value = '';
      if (file) void this.importWall(file);
    });
    canvas.addEventListener('pointerdown', e => { canvas.focus(); canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointercancel', () => { this.dragging = null; I.GetIO().AddMouseButtonEvent(0, false); });
    canvas.addEventListener('wheel', e => e.preventDefault(), { passive: false });
    canvas.addEventListener('keydown', e => { if ([' ', 'ArrowUp', 'ArrowDown'].includes(e.key)) e.preventDefault(); });
    canvas.addEventListener('webglcontextlost', e => {
      e.preventDefault(); this.stopped = true; cancelAnimationFrame(this.frameId); this.gifJob?.close();
      showFailure('The graphics context was lost. Reload this page to restart the simulation.');
    });
    document.addEventListener('visibilitychange', () => { this.previousTime = performance.now(); });
  }
  private remember(key: string) {
    if (!import.meta.env.DEV) return;
    const min = I.GetItemRectMin(), max = I.GetItemRectMax();
    this.uiRects[key] = { x: min.x, y: min.y, width: max.x-min.x, height: max.y-min.y };
  }
  private button(label: string, width = 0, height = 0) {
    const clicked = I.Button(label, v2(width, height)); this.remember(label); return clicked;
  }
  private checkbox(label: string, value: boolean) {
    const ref: [boolean] = [value]; I.Checkbox(label, ref); this.remember(label); return ref[0];
  }
  private slider(label: string, value: number, min: number, max: number, format: string) {
    const ref: [number] = [value]; I.SliderFloat(label, ref, min, max, format); this.remember(label);
    return Number.isFinite(ref[0]) ? clamp(ref[0], min, max) : value;
  }
  private releaseTexture(ref: ImTextureRef) {
    // jsimgui exposes registration only; release our own registry slot before
    // deleting its WebGL texture. No font/backend textures are touched.
    const textures = Backend.GetEmscriptenExports().GL.textures;
    textures[Number(ref._TexID)] = null;
  }
  async importWall(file: File, invert?: boolean) {
    const id = ++this.wallLoadId;
    try {
      const wall = await loadWall(file, invert);
      if (id !== this.wallLoadId) return;
      this.pendingWall = wall; this.pendingReference = false; this.wallFile = file; this.wallError = '';
    } catch (error) { if (id === this.wallLoadId) this.wallError = `Could not load wall image: ${String(error)}`; }
  }
  useReference() {
    this.wallLoadId++; this.pendingWall = this.reference.wall; this.pendingReference = true;
  }
  private applyWall() {
    if (!this.pendingWall) return;
    const wall = this.pendingWall, reference = this.pendingReference;
    this.pendingWall = null;
    try {
      const next = new WaveGPU(this.gl, reference ? 336 : wall.width, reference ? 1074 : wall.height, wall, this.reference.palette);
      const nextOutput = Backend.RegisterTexture(next.output), nextPalette = Backend.RegisterTexture(next.palette);
      this.releaseTexture(this.outputRef); this.releaseTexture(this.paletteRef); this.gpu.close();
      this.gpu = next; this.outputRef = nextOutput; this.paletteRef = nextPalette;
      this.wallName = reference ? '' : wall.name; this.wallInverted = wall.inverted;
      if (reference) this.wallFile = null;
      this.settings.walls = true; this.accumulator = 0; this.dragging = null; this.adding = false; this.wallError = '';
    } catch (error) { this.wallError = `Could not apply wall image: ${String(error)}`; }
  }
  startGif() {
    if (this.gifJob) return;
    try {
      this.gifJob = new GifExport(this.gpu, this.scene, this.settings, this.gifPhaseStep);
      this.gifMessage = ''; this.gifError = false;
    } catch (error) { this.gifMessage = String(error); this.gifError = true; }
  }
  private updateGif() {
    if (this.pendingGif) { this.pendingGif = false; this.startGif(); }
    const job = this.gifJob;
    if (!job) return;
    job.advance();
    if (job.done) {
      if (job.error) { this.gifMessage = `GIF export failed: ${job.error}`; this.gifError = true; }
      else if (job.result) {
        this.lastGif = job.result;
        this.gifMessage = `Saved: wifi-field.gif (${job.offsets.length} frames, 50 FPS)`;
        download(job.result, 'wifi-field.gif');
      }
      job.close(); this.gifJob = null;
    }
  }
  private gifControls() {
    if (!this.gifJob) {
      I.PushItemWidth(130);
      this.gifPhaseStep = Math.round(this.slider('GIF phase step', this.gifPhaseStep, 1, 180, '%.1f deg')*10)/10;
      I.PopItemWidth();
      if (I.GetContentRegionAvail().x > 380) I.SameLine();
      if (this.button('Save GIF...')) this.pendingGif = true;
      const count = phaseOffsets(this.gifPhaseStep, this.scene.current().frequency).length;
      muted(`360 deg / TX ${this.scene.selected}  |  ${count} frames  |  50 FPS  |  ${(count/50).toFixed(2)} s`);
    } else {
      const job = this.gifJob;
      I.ProgressBar(job.encoded/job.offsets.length, v2(Math.max(1, I.GetContentRegionAvail().x-90), 22), `Saving GIF ${job.encoded}/${job.offsets.length}`);
      I.SameLine();
      if (this.button('Cancel')) { job.close(); this.gifJob = null; this.gifMessage = 'GIF export cancelled.'; }
    }
    if (this.gifMessage) {
      I.PushStyleColorImVec4(ImGuiCol.Text, this.gifError ? v4(1, .5, .4) : v4(.4, .85, .75));
      I.TextWrapped(this.gifMessage); I.PopStyleColor();
      if (this.lastGif && !this.gifJob && this.button('Download again')) download(this.lastGif, 'wifi-field.gif');
    }
  }
  private viewport() {
    I.Text(this.wallName ? 'CUSTOM PLAN' : 'REFERENCE PLAN'); I.SameLine(); muted('/  live wave field');
    if (this.button('Open wall image...')) document.querySelector<HTMLInputElement>('#wall-file')!.click();
    I.SameLine(); if (this.button('Use reference')) this.useReference();
    if (this.wallName) {
      muted(this.wallName.length > 42 ? this.wallName.slice(0, 39)+'...' : this.wallName);
      if (I.IsItemHovered()) I.SetTooltip(this.wallName);
      const invert = this.checkbox('Dark walls on light background', this.wallInverted);
      if (invert !== this.wallInverted && this.wallFile) void this.importWall(this.wallFile, invert);
    }
    if (this.wallError) { I.PushStyleColorImVec4(ImGuiCol.Text, v4(1, .5, .4)); I.TextWrapped(this.wallError); I.PopStyleColor(); }
    this.gifControls();
    const available = I.GetContentRegionAvail();
    let height = Math.max(100, available.y-45), width = height*this.gpu.width/this.gpu.height;
    if (width > available.x) { width = Math.max(1, available.x); height = width*this.gpu.height/this.gpu.width; }
    const pos = I.GetCursorScreenPos(), left = pos.x+(available.x-width)/2, top = pos.y;
    I.SetCursorScreenPos(v2(left, top)); I.Image(this.outputRef, v2(width, height));
    this.canvasRect = { x: left, y: top, width, height };
    const hovered = I.IsItemHovered(), mouse = I.GetIO().MousePos;
    const x = (mouse.x-left)/width, y = (mouse.y-top)/height;
    if (I.IsMouseClicked(0) && hovered) {
      const hit = this.scene.hit(x, y, width, height);
      if (this.adding || (I.IsMouseDoubleClicked(0) && hit === null)) {
        const s = this.scene.add(x, y); if (s) this.dragging = s.id; this.adding = false;
      } else if (hit !== null) { this.scene.selected = hit; this.dragging = hit; }
    }
    if (this.dragging !== null) {
      if (I.IsMouseDown(0)) this.scene.move(this.dragging, x, y); else this.dragging = null;
    }
    if (this.settings.markers) {
      const draw = I.GetWindowDrawList();
      for (const s of this.scene.sources) {
        const sx = left+s.x*width, sy = top+s.y*height, selected = s.id === this.scene.selected;
        const col = !s.enabled ? color(.5, .55, .6, .8) : selected ? color(.30, 1, .91) : color(1, 1, 1, .9);
        draw.AddCircleFilled(v2(sx, sy), 8, color(.015, .025, .04, .95));
        draw.AddCircle(v2(sx, sy), selected ? 11 : 8, col, 0, 2);
        draw.AddLine(v2(sx-4, sy), v2(sx+4, sy), col, 1.5); draw.AddLine(v2(sx, sy-4), v2(sx, sy+4), col, 1.5);
        const lx = s.x < .7 ? sx+15 : sx-49;
        draw.AddText(v2(lx+1, sy-8), color(0, 0, 0), `TX ${s.id}`); draw.AddText(v2(lx, sy-9), col, `TX ${s.id}`);
      }
    }
    if (hovered) I.SetMouseCursor(ImGuiMouseCursor.Hand);
    I.SetCursorScreenPos(v2(pos.x, top+height+12)); muted('Drag a source to move it.  |  Space: pause');
  }
  private controls() {
    const settings = this.settings;
    section(`TRANSMITTERS   /   ${String(this.scene.sources.length).padStart(2, '0')} OF ${MAX_SOURCES}`);
    I.BeginDisabled(this.scene.sources.length >= MAX_SOURCES);
    if (this.button('Place transmitter', -1, 34)) this.adding = !this.adding;
    I.EndDisabled();
    if (this.adding) I.TextColored(v4(.97, .76, .35), 'Click the map to place. Esc cancels.'); else muted('Double-click the map to add.');
    I.BeginChild('source_list', v2(0, 76), ImGuiChildFlags.Borders);
    for (const s of this.scene.sources) {
      if (I.Selectable(`TX ${String(s.id).padStart(2, '0')}    ${s.frequency.toFixed(1)} GHz${s.enabled ? '' : '  [off]'}`, s.id === this.scene.selected)) this.scene.selected = s.id;
      this.remember(`source-${s.id}`);
    }
    I.EndChild();
    const source = this.scene.current();
    I.Text(`Selected: TX ${String(source.id).padStart(2, '0')}`); I.SameLine(0, 20);
    source.enabled = this.checkbox('Enabled', source.enabled);
    I.PushItemWidth(155);
    source.power = this.slider('Power', source.power, .05, 3, '%.2f x');
    source.frequency = this.slider('Frequency', source.frequency, 1, 6, '%.2f GHz');
    source.phase = this.slider('Phase', source.phase, -180, 180, '%.0f deg');
    I.PopItemWidth();
    muted(`Position   ${(source.x*100).toFixed(1)}% / ${(source.y*100).toFixed(1)}%`);
    if (this.scene.sources.length > 1) { if (this.button('Remove selected', -1)) this.scene.remove(); }
    else muted('Keep at least one transmitter.');

    section('SIMULATION');
    if (this.button(settings.paused ? 'Resume' : 'Pause', 126, 32)) settings.paused = !settings.paused;
    I.SameLine(); if (this.button('Clear waves', -1, 32)) this.gpu.clear();
    I.PushItemWidth(155);
    settings.speed = this.slider('Speed', settings.speed, .1, 3, '%.1f x');
    settings.loss = this.slider('Air loss', settings.loss, .0001, .01, '%.4f');
    settings.transmission = this.slider('Wall pass', settings.transmission, .01, 1, '%.2f');
    I.PopItemWidth();
    const walls = this.checkbox('Use walls', settings.walls);
    if (walls !== settings.walls) { settings.walls = walls; this.gpu.clear(); }

    section('HEATMAP');
    settings.showWalls = this.checkbox('Wall visualization', settings.showWalls);
    I.PushItemWidth(155);
    const mode: [number] = [settings.mode]; I.Combo('Display', mode, 'Instant wave\0Mean intensity\0\0'); settings.mode = mode[0]; this.remember('Display');
    settings.exposure = this.slider('Gain', settings.exposure, .5, 15, '%.1f'); I.PopItemWidth();
    settings.markers = this.checkbox('Show transmitter markers', settings.markers);
    I.Image(this.paletteRef, v2(Math.max(1, I.GetContentRegionAvail().x), 16));
    muted('WEAK                                      STRONG'); muted('Sampled from the reference video');
    if (this.button('Reset scene', -1)) { this.scene = new Scene(); this.adding = false; this.dragging = null; this.gpu.clear(); }
  }
  private frame = (now: number) => {
    if (this.stopped) return;
    try {
      const canvas = this.canvas, ratio = window.devicePixelRatio || 1;
      const w = Math.round(canvas.clientWidth*ratio), h = Math.round(canvas.clientHeight*ratio);
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      this.applyWall(); this.updateGif();
      const elapsed = Math.min(.05, Math.max(0, (now-this.previousTime)/1000)); this.previousTime = now;
      Backend.BeginRender();
      const io = I.GetIO();
      if (!io.WantTextInput) {
        if (I.IsKeyPressed(ImGuiKey._Space, false)) this.settings.paused = !this.settings.paused;
        if (I.IsKeyPressed(ImGuiKey._Escape, false)) { this.adding = false; this.dragging = null; }
      }
      if (!this.settings.paused && !document.hidden) {
        this.accumulator += elapsed*720*this.settings.speed;
        const steps = Math.min(108, Math.floor(this.accumulator)); this.accumulator -= steps;
        if (steps) this.gpu.step(this.scene.sources, steps, this.settings);
      }
      this.gpu.render(this.settings);
      I.SetNextWindowPos(v2(0, 0)); I.SetNextWindowSize(v2(canvas.clientWidth, canvas.clientHeight));
      I.Begin('WiFi Field', undefined, WindowFlags.NoTitleBar | WindowFlags.NoResize | WindowFlags.NoMove | WindowFlags.NoCollapse | WindowFlags.NoSavedSettings | WindowFlags.NoBringToFrontOnFocus);
      I.TextColored(v4(.42, .92, .87), 'W I F I   /   F I E L D'); I.SameLine(0, 24); muted('Signal Intensity Visualization');
      I.Text('Explore propagation. Move the source. See the interference.'); I.Separator();
      I.BeginChild('viewport', v2(canvas.clientWidth-380, -33), ImGuiChildFlags.Borders); this.viewport(); I.EndChild();
      I.SameLine(); I.BeginChild('controls', v2(0, -33), ImGuiChildFlags.Borders); this.controls(); I.EndChild();
      I.TextColored(v4(.38, .88, .81), this.settings.paused ? 'PAUSED' : 'LIVE'); I.SameLine();
      muted(`WebGL 2   |   ${this.gpu.width} x ${this.gpu.height}   |   Step ${this.gpu.tick.toLocaleString('en-US')}   |   ${io.Framerate.toFixed(0)} FPS`);
      I.End();
      const gl = this.gl;
      gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, w, h); gl.disable(gl.SCISSOR_TEST);
      gl.clearColor(.035, .047, .07, 1); gl.clear(gl.COLOR_BUFFER_BIT);
      Backend.EndRender();
      this.frameId = requestAnimationFrame(this.frame);
    } catch (error) { this.stopped = true; this.gifJob?.close(); showFailure(String(error)); console.error(error); }
  };
  run() { this.previousTime = performance.now(); this.frameId = requestAnimationFrame(this.frame); }
}

function setStyle() {
  I.StyleColorsDark(); const style = I.GetStyle();
  style.WindowPadding = v2(20, 16); style.FramePadding = v2(9, 4); style.ItemSpacing = v2(9, 7);
  style.WindowRounding = 0; style.ChildRounding = 0; style.FrameRounding = 5; style.GrabRounding = 5;
  style.FontSizeBase = 16;
  const colors = style.Colors;
  colors[ImGuiCol.WindowBg] = v4(.035, .047, .07);
  colors[ImGuiCol.ChildBg] = v4(.055, .072, .10);
  colors[ImGuiCol.FrameBg] = v4(.10, .13, .18);
  colors[ImGuiCol.Button] = v4(.13, .23, .32);
  colors[ImGuiCol.ButtonHovered] = v4(.16, .37, .47);
  colors[ImGuiCol.ButtonActive] = v4(.18, .46, .54);
  colors[ImGuiCol.CheckMark] = v4(.33, .86, .83);
  colors[ImGuiCol.SliderGrab] = v4(.33, .86, .83);
  colors[ImGuiCol.Header] = v4(.12, .29, .36);
  colors[ImGuiCol.Text] = v4(.90, .94, .98);
  style.Colors = colors;
}
function showFailure(message: string) {
  const status = document.querySelector<HTMLDivElement>('#status')!;
  status.hidden = false; status.textContent = `WiFi Field\n\n${message}\n\nReload the page to try again.`;
}
async function main() {
  const canvas = document.querySelector<HTMLCanvasElement>('#app')!;
  const gl = canvas.getContext('webgl2', { alpha: false, antialias: false, preserveDrawingBuffer: false });
  if (!gl) throw new Error('WebGL 2 is required. Use a browser with hardware acceleration enabled.');
  const [reference] = await Promise.all([loadReference(), Backend.Init({ canvas, backend: 'webgl2' })]);
  const response = await fetch(`${import.meta.env.BASE_URL}fonts/NotoSansKR-Regular.ttf`);
  if (!response.ok) throw new Error('Could not load the UI font.');
  Backend.LoadFont('NotoSansKR-Regular.ttf', new Uint8Array(await response.arrayBuffer()));
  I.GetIO().Fonts.AddFontFromFileTTF('NotoSansKR-Regular.ttf', 16);
  setStyle();
  const app = new Application(canvas, gl, reference);
  if (import.meta.env.DEV) (window as unknown as { __wifi: Application }).__wifi = app;
  document.querySelector<HTMLDivElement>('#status')!.hidden = true;
  app.run();
}
main().catch(error => { showFailure(String(error)); console.error(error); });
