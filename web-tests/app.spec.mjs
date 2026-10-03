import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';

async function ready(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  await page.goto('/');
  await page.waitForFunction(() => window.__wifi?.gpu.tick >= 700);
  await expect(page.locator('#status')).toBeHidden();
  return errors;
}
async function click(page, label) {
  await page.waitForFunction(label => !!window.__wifi.uiRects[label], label);
  const r = await page.evaluate(label => window.__wifi.uiRects[label], label);
  await page.mouse.click(r.x+r.width/2, r.y+r.height/2);
}

test('real ImGui controls, source dragging, wall import and GIF download', async ({ page }) => {
  const errors = await ready(page);
  await click(page, 'Pause');
  await page.waitForFunction(() => window.__wifi.settings.paused);
  const initialTick = await page.evaluate(() => window.__wifi.gpu.tick);
  await page.waitForTimeout(80);
  expect(await page.evaluate(() => window.__wifi.gpu.tick)).toBe(initialTick);
  await click(page, 'Place transmitter');
  await page.waitForFunction(() => window.__wifi.adding);
  let r = await page.evaluate(() => window.__wifi.canvasRect);
  await page.mouse.click(r.x+r.width*.4, r.y+r.height*.3);
  await page.waitForFunction(() => window.__wifi.scene.sources.length === 2);
  await page.mouse.move(r.x+r.width*.4, r.y+r.height*.3);
  await page.mouse.down();
  await page.mouse.move(r.x+r.width*.6, r.y+r.height*.2, { steps: 8 });
  await page.mouse.up();
  const moved = await page.evaluate(() => window.__wifi.scene.current());
  expect(moved.x).toBeCloseTo(.6, 2); expect(moved.y).toBeCloseTo(.2, 2);
  await click(page, 'Enabled');
  await page.waitForFunction(() => !window.__wifi.scene.current().enabled);
  await click(page, 'Enabled');
  await click(page, 'Remove selected');
  await page.waitForFunction(() => window.__wifi.scene.sources.length === 1);

  await page.evaluate(() => { const a = window.__wifi; window._before = a.gpu.readState(); window._visible = a.gpu.readPixels(); });
  await click(page, 'Wall visualization');
  await page.waitForFunction(() => !window.__wifi.settings.showWalls);
  await page.waitForTimeout(50);
  expect(await page.evaluate(() => {
    const a = window.__wifi, state = a.gpu.readState(), pixels = a.gpu.readPixels();
    return a.settings.walls && state.every((v,i) => v === window._before[i]) && pixels.some((v,i) => v !== window._visible[i]);
  })).toBe(true);

  const chooser = page.waitForEvent('filechooser');
  await click(page, 'Open wall image...');
  await (await chooser).setFiles({ name: '사용자 평면도.png', mimeType: 'image/png', buffer: await fs.readFile('web-tests/fixtures/wall.png') });
  await page.waitForFunction(() => window.__wifi.wallName === '사용자 평면도.png');
  expect(await page.evaluate(() => ({ width: window.__wifi.gpu.width, height: window.__wifi.gpu.height, invert: window.__wifi.wallInverted }))).toEqual({ width: 240, height: 160, invert: true });
  await page.setInputFiles('#wall-file', { name: 'broken.png', mimeType: 'image/png', buffer: Buffer.from('not an image') });
  await page.waitForFunction(() => !!window.__wifi.wallError);
  expect(await page.evaluate(() => window.__wifi.gpu.width)).toBe(240);
  await click(page, 'Dark walls on light background');
  await page.waitForFunction(() => !window.__wifi.wallInverted);
  await page.setInputFiles('#wall-file', 'web-tests/fixtures/wall.tiff');
  await page.waitForFunction(() => window.__wifi.wallName === 'wall.tiff' && window.__wifi.wallInverted);
  await click(page, 'Use reference');
  await page.waitForFunction(() => window.__wifi.gpu.width === 336 && window.__wifi.wallName === '');
  await click(page, 'Wall visualization');
  await page.waitForFunction(() => window.__wifi.settings.showWalls);
  await click(page, 'Resume');
  await page.waitForFunction(() => window.__wifi.gpu.tick > 400);
  await page.keyboard.press('Space');
  await page.waitForFunction(() => window.__wifi.settings.paused);
  const savedTick = await page.evaluate(() => window.__wifi.gpu.tick);
  const downloaded = page.waitForEvent('download', { timeout: 60000 });
  await click(page, 'Save GIF...');
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe('wifi-field.gif');
  await fs.mkdir('artifacts', { recursive: true });
  await download.saveAs('artifacts/web-export.gif');
  expect(await page.evaluate(() => window.__wifi.gpu.tick)).toBe(savedTick);
  expect(await page.evaluate(() => window.__wifi.gifError)).toBe(false);
  await page.screenshot({ path: 'artifacts/web-app.png' });
  await click(page, 'Save GIF...');
  await page.waitForFunction(() => !!window.__wifi.gifJob);
  await click(page, 'Cancel');
  await page.waitForFunction(() => !window.__wifi.gifJob);
  expect(await page.evaluate(() => window.__wifi.gifMessage)).toContain('cancelled');
  expect(await page.evaluate(() => window.__wifi.gl.getError())).toBe(0);
  expect(errors).toEqual([]);
});

test('WebGL wave state and pixels match the desktop GPU fixture', async ({ page }) => {
  const errors = await ready(page);
  const reference = JSON.parse(await fs.readFile('web-tests/fixtures/desktop-wave.json', 'utf8'));
  const result = await page.evaluate(async reference => {
    const { WaveGPU } = await import('/web/gpu.ts');
    const app = window.__wifi;
    app.settings.paused = true;
    const gpu = new WaveGPU(app.gl, reference.width, reference.height, app.reference.wall, app.reference.palette);
    try {
      gpu.step(reference.sources, reference.ticks, { loss: .001, transmission: .15, walls: true });
      gpu.render({ exposure: 5, mode: 0, showWalls: true });
      const decode = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
      const expected = new Float32Array(decode(reference.stateFloat32LE).buffer), state = gpu.readState();
      const image = decode(reference.rgba), pixels = gpu.readPixels();
      let max = 0, pixelError = 0;
      state.forEach((v,i) => { max = Math.max(max, Math.abs(v-expected[i])); });
      pixels.forEach((v,i) => { pixelError += Math.abs(v-image[i]); });
      return { max, pixelMean: pixelError/pixels.length, glError: app.gl.getError() };
    } finally { gpu.close(); }
  }, reference);
  expect(result.glError).toBe(0);
  expect(result.max).toBeLessThan(.001);
  expect(result.pixelMean).toBeLessThan(1);
  console.log('Desktop/WebGL comparison:', result);
  expect(errors).toEqual([]);
});

test('high-DPI resizing keeps source interaction aligned', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  await ready(page);
  await click(page, 'Pause');
  await page.waitForFunction(() => window.__wifi.settings.paused);
  await page.setViewportSize({ width: 800, height: 750 });
  await page.waitForFunction(() => document.querySelector('#app').width === 1600);
  await click(page, 'Place transmitter');
  const r = await page.evaluate(() => window.__wifi.canvasRect);
  await page.mouse.click(r.x+r.width*.3, r.y+r.height*.6);
  await page.waitForFunction(() => window.__wifi.scene.sources.length === 2);
  expect(await page.evaluate(() => window.__wifi.scene.current().x)).toBeCloseTo(.3, 2);
  expect(await page.evaluate(() => window.__wifi.scene.current().y)).toBeCloseTo(.6, 2);
  expect(await page.evaluate(() => window.__wifi.gl.getError())).toBe(0);
  await context.close();
});

test('unsupported WebGL gives a readable startup error', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, ...args) { return type === 'webgl2' ? null : original.call(this, type, ...args); };
  });
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('WebGL 2 is required');
});
