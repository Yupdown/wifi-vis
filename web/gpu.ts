import vertexSource from '../wifivis/shaders/fullscreen.vert?raw';
import stepSource from '../wifivis/shaders/step.frag?raw';
import displaySource from '../wifivis/shaders/display.frag?raw';
import type { WallMap } from './assets';
import type { Settings, Transmitter } from './model';

// Keep the desktop equations verbatim; only the GLSL dialect changes.
const es = (source: string) => source.replace('#version 330 core', '#version 300 es\nprecision highp float;\nprecision highp int;\nprecision highp sampler2D;');

export class WaveGPU {
  tick = 0;
  front = 0;
  states: WebGLTexture[] = [];
  output!: WebGLTexture;
  walls!: WebGLTexture;
  palette!: WebGLTexture;
  private programs: WebGLProgram[] = [];
  private locations = new Map<string, WebGLUniformLocation | null>();
  private vao: WebGLVertexArrayObject;
  private fbo: WebGLFramebuffer;
  private linearFloat: boolean;

  constructor(readonly gl: WebGL2RenderingContext, public width: number, public height: number,
    readonly wallMap: WallMap, readonly colors: Uint8Array) {
    if (!gl.getExtension('EXT_color_buffer_float')) throw new Error('This browser/GPU needs WebGL 2 and EXT_color_buffer_float. Enable hardware acceleration.');
    this.linearFloat = !!gl.getExtension('OES_texture_float_linear');
    this.vao = gl.createVertexArray()!; this.fbo = gl.createFramebuffer()!;
    try {
      this.programs = [this.program(stepSource), this.program(displaySource)];
      this.states.push(this.texture(width, height, gl.RGBA32F, gl.RGBA, gl.FLOAT));
      this.states.push(this.texture(width, height, gl.RGBA32F, gl.RGBA, gl.FLOAT));
      this.output = this.texture(width, height, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE);
      this.walls = this.texture(wallMap.width, wallMap.height, gl.R8, gl.RED, gl.UNSIGNED_BYTE, wallMap.pixels);
      this.palette = this.texture(256, 1, gl.RGB8, gl.RGB, gl.UNSIGNED_BYTE, colors);
      this.clear();
    } catch (error) { this.close(); throw error; }
  }
  private program(fragment: string) {
    const gl = this.gl, program = gl.createProgram()!;
    const shaders: WebGLShader[] = [];
    try {
      for (const [type, source] of [[gl.VERTEX_SHADER, vertexSource], [gl.FRAGMENT_SHADER, fragment]] as const) {
        const shader = gl.createShader(type)!; shaders.push(shader);
        gl.shaderSource(shader, es(source)); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) ?? 'Shader compilation failed');
        gl.attachShader(program, shader);
      }
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) ?? 'Shader linking failed');
      return program;
    } catch (error) { gl.deleteProgram(program); throw error; }
    finally { shaders.forEach(s => gl.deleteShader(s)); }
  }
  private texture(w: number, h: number, internal: number, format: number, type: number, data: Uint8Array | null = null) {
    const gl = this.gl, texture = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, format, type, data);
    const filter = type === gl.FLOAT && !this.linearFloat ? gl.NEAREST : gl.LINEAR;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return texture;
  }
  private uniform(program: number, name: string) {
    const key = `${program}:${name}`;
    if (!this.locations.has(key)) this.locations.set(key, this.gl.getUniformLocation(this.programs[program], name));
    return this.locations.get(key)!;
  }
  private target(texture: WebGLTexture) {
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('The floating-point framebuffer is not supported.');
    gl.viewport(0, 0, this.width, this.height);
  }
  private bind(program: number, name: string, texture: WebGLTexture, unit: number) {
    const gl = this.gl;
    gl.activeTexture(gl.TEXTURE0+unit); gl.bindSampler(unit, null);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.uniform1i(this.uniform(program, name), unit);
  }
  private prepare(program: number) {
    const gl = this.gl;
    gl.disable(gl.BLEND); gl.disable(gl.SCISSOR_TEST); gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);
    gl.colorMask(true, true, true, true);
    gl.bindVertexArray(this.vao); gl.useProgram(this.programs[program]);
  }
  clear() {
    const gl = this.gl;
    gl.disable(gl.SCISSOR_TEST); gl.colorMask(true, true, true, true); gl.clearColor(0, 0, 0, 0);
    for (const texture of this.states) { this.target(texture); gl.clear(gl.COLOR_BUFFER_BIT); }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); this.tick = 0;
  }
  step(sources: Transmitter[], count: number, settings: Pick<Settings, 'loss' | 'transmission' | 'walls'>) {
    const gl = this.gl; this.prepare(0);
    gl.uniform2f(this.uniform(0, 'grid'), this.width, this.height);
    gl.uniform1f(this.uniform(0, 'loss'), settings.loss);
    gl.uniform1f(this.uniform(0, 'transmission'), settings.transmission);
    gl.uniform1i(this.uniform(0, 'useWalls'), +settings.walls);
    const active = sources.filter(s => s.enabled);
    gl.uniform1i(this.uniform(0, 'sourceCount'), active.length);
    if (active.length) {
      gl.uniform4fv(this.uniform(0, 'sources[0]'), new Float32Array(active.flatMap(s => [s.x, s.y, Math.sqrt(s.power), 2*Math.PI*.028*s.frequency/2.4])));
      gl.uniform1fv(this.uniform(0, 'phases[0]'), new Float32Array(active.map(s => s.phase*Math.PI/180)));
    }
    this.bind(0, 'walls', this.walls, 1);
    for (let i = 0; i < count; i++) {
      this.target(this.states[1-this.front]); this.bind(0, 'state', this.states[this.front], 0);
      gl.uniform1f(this.uniform(0, 'tick'), this.tick);
      gl.drawArrays(gl.TRIANGLES, 0, 3); this.front = 1-this.front; this.tick++;
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }
  render(settings: Pick<Settings, 'exposure' | 'mode' | 'showWalls'>, interpolation = 1) {
    const gl = this.gl; this.prepare(1); this.target(this.output);
    this.bind(1, 'state', this.states[this.front], 0); this.bind(1, 'walls', this.walls, 1);
    this.bind(1, 'palette', this.palette, 2); this.bind(1, 'previousState', this.states[1-this.front], 3);
    gl.uniform1f(this.uniform(1, 'exposure'), settings.exposure);
    gl.uniform1f(this.uniform(1, 'interpolation'), interpolation);
    gl.uniform1i(this.uniform(1, 'mode'), settings.mode);
    gl.uniform1i(this.uniform(1, 'showWalls'), +settings.showWalls);
    gl.drawArrays(gl.TRIANGLES, 0, 3); gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }
  readPixels() {
    const gl = this.gl, pixels = new Uint8Array(this.width*this.height*4);
    this.target(this.output); gl.pixelStorei(gl.PACK_ALIGNMENT, 1);
    gl.readPixels(0, 0, this.width, this.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return pixels; // Row 0 is domain top, just as in the desktop version.
  }
  readState() {
    const gl = this.gl, data = new Float32Array(this.width*this.height*4);
    this.target(this.states[this.front]);
    gl.readPixels(0, 0, this.width, this.height, gl.RGBA, gl.FLOAT, data);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); return data;
  }
  clone() {
    const gl = this.gl, copy = new WaveGPU(gl, this.width, this.height, this.wallMap, this.colors);
    gl.disable(gl.SCISSOR_TEST);
    this.target(this.states[this.front]);
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER, copy.fbo);
    for (const texture of copy.states) {
      gl.framebufferTexture2D(gl.DRAW_FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
      gl.blitFramebuffer(0, 0, this.width, this.height, 0, 0, this.width, this.height, gl.COLOR_BUFFER_BIT, gl.NEAREST);
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); copy.tick = this.tick;
    return copy;
  }
  close() {
    const gl = this.gl;
    [...this.states, this.output, this.walls, this.palette].forEach(t => { if (t) gl.deleteTexture(t); });
    this.programs.forEach(p => gl.deleteProgram(p)); gl.deleteFramebuffer(this.fbo); gl.deleteVertexArray(this.vao);
  }
}
