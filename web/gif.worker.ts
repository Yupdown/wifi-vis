import { GIFEncoder, applyPalette } from 'gifenc';

let encoder: ReturnType<typeof GIFEncoder>;
let palette: number[][];
let first = true;
self.onmessage = (event: MessageEvent) => {
  try {
    const message = event.data;
    if (message.type === 'init') { encoder = GIFEncoder(); palette = message.palette; first = true; }
    if (message.type === 'frame') {
      const index = applyPalette(new Uint8Array(message.pixels), palette);
      encoder.writeFrame(index, message.width, message.height, { palette: first ? palette : undefined, delay: 20, repeat: 0, dispose: 2 });
      first = false;
      self.postMessage({ type: 'frame', index: message.index });
    }
    if (message.type === 'finish') {
      encoder.finish(); const bytes = encoder.bytes();
      self.postMessage({ type: 'done', bytes: bytes.buffer }, { transfer: [bytes.buffer] });
    }
  } catch (error) { self.postMessage({ type: 'error', message: String(error) }); }
};
