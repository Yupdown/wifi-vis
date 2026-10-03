from pathlib import Path
import math

import numpy as np
from PIL import Image
from OpenGL import GL as gl
from OpenGL.GL.shaders import compileProgram, compileShader

ROOT = Path(__file__).resolve().parent


class WaveGPU:
    """Ping-pong FDTD wave solver; RGB = current, previous, mean-square field."""
    def __init__(self, width=336, height=1074):
        self.width, self.height = width, height
        self.tick = 0
        self.front = 0
        self.vao = gl.glGenVertexArrays(1)
        self.fbo = gl.glGenFramebuffers(1)
        vertex = (ROOT / "shaders/fullscreen.vert").read_text()
        self.programs = []
        for name in ("step", "display"):
            self.programs.append(compileProgram(
                compileShader(vertex, gl.GL_VERTEX_SHADER),
                compileShader((ROOT / f"shaders/{name}.frag").read_text(), gl.GL_FRAGMENT_SHADER)))
        self.locations = {}
        self.states = [self.texture(width, height, gl.GL_RGBA32F, gl.GL_RGBA, gl.GL_FLOAT) for _ in range(2)]
        self.output = self.texture(width, height, gl.GL_RGBA8, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        wall = np.array(Image.open(ROOT / "assets/walls.png").convert("L"))
        self.wall_pixels = wall
        # All domain coordinates have y=0 at the top; ImGui displays texture row 0 at top.
        self.walls = self.texture(wall.shape[1], wall.shape[0], gl.GL_R8, gl.GL_RED, gl.GL_UNSIGNED_BYTE, wall)
        palette = np.array(Image.open(ROOT / "assets/palette.png").convert("RGB"))
        self.palette = self.texture(256, 1, gl.GL_RGB8, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, palette)
        self.clear()

    @staticmethod
    def texture(w, h, internal, fmt, dtype, data=None):
        texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal, w, h, 0, fmt, dtype, data)
        for key in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, key, gl.GL_LINEAR)
        for key in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, key, gl.GL_CLAMP_TO_EDGE)
        return texture

    def uniform(self, program, name):
        key = program, name
        if key not in self.locations:
            self.locations[key] = gl.glGetUniformLocation(program, name)
        return self.locations[key]

    def set_wall_map(self, pixels):
        """Prepare new GPU resources before replacing the working scene."""
        height, width = pixels.shape
        created = []
        try:
            specs = [(gl.GL_R8, gl.GL_RED, gl.GL_UNSIGNED_BYTE, pixels),
                     (gl.GL_RGBA32F, gl.GL_RGBA, gl.GL_FLOAT, None),
                     (gl.GL_RGBA32F, gl.GL_RGBA, gl.GL_FLOAT, None),
                     (gl.GL_RGBA8, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)]
            for internal, fmt, dtype, data in specs:
                created.append(self.texture(width, height, internal, fmt, dtype, data))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0, 0, 0, 0)
            for texture in created[1:]:
                gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
                if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError("Could not allocate the wall image framebuffer")
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        except Exception:
            if created:
                gl.glDeleteTextures(created)
            raise
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        old = self.states + [self.output, self.walls]
        self.walls, first, second, self.output = created
        self.states = [first, second]
        self.width, self.height = width, height
        self.wall_pixels = pixels
        self.front = 0
        self.tick = 0
        gl.glDeleteTextures(old)

    def target(self, texture):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("The GPU cannot create the wave framebuffer")
        gl.glViewport(0, 0, self.width, self.height)

    def bind(self, program, name, texture, unit):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glUniform1i(self.uniform(program, name), unit)

    def clear(self):
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0, 0, 0, 0)
        for texture in self.states:
            self.target(texture)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        self.tick = 0

    def step(self, sources, count=12, loss=.001, transmission=.15, walls=True):
        p = self.programs[0]
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glBindVertexArray(self.vao)
        gl.glUseProgram(p)
        gl.glUniform2f(self.uniform(p, "grid"), self.width, self.height)
        gl.glUniform1f(self.uniform(p, "loss"), loss)
        gl.glUniform1f(self.uniform(p, "transmission"), transmission)
        gl.glUniform1i(self.uniform(p, "useWalls"), walls)
        active = [s for s in sources if s.enabled]
        gl.glUniform1i(self.uniform(p, "sourceCount"), len(active))
        if active:
            data = np.array([[s.x, s.y, math.sqrt(s.power), 2*math.pi*.028*s.frequency/2.4] for s in active], dtype=np.float32)
            phases = np.array([math.radians(s.phase) for s in active], dtype=np.float32)
            gl.glUniform4fv(self.uniform(p, "sources"), len(active), data)
            gl.glUniform1fv(self.uniform(p, "phases"), len(active), phases)
        self.bind(p, "walls", self.walls, 1)
        for _ in range(count):
            self.target(self.states[1-self.front])
            self.bind(p, "state", self.states[self.front], 0)
            gl.glUniform1f(self.uniform(p, "tick"), self.tick)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            self.front = 1-self.front
            self.tick += 1
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def render(self, exposure=5.0, mode=0, show_walls=True, interpolation=1.0):
        p = self.programs[1]
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glBindVertexArray(self.vao)
        gl.glUseProgram(p)
        self.target(self.output)
        self.bind(p, "state", self.states[self.front], 0)
        self.bind(p, "walls", self.walls, 1)
        self.bind(p, "palette", self.palette, 2)
        self.bind(p, "previousState", self.states[1-self.front], 3)
        gl.glUniform1f(self.uniform(p, "exposure"), exposure)
        gl.glUniform1f(self.uniform(p, "interpolation"), interpolation)
        gl.glUniform1i(self.uniform(p, "mode"), mode)
        gl.glUniform1i(self.uniform(p, "showWalls"), show_walls)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def read_state(self):
        self.target(self.states[self.front])
        data = gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_FLOAT)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        return np.frombuffer(data, np.float32).reshape(self.height, self.width, 4).copy()

    def read_image(self):
        self.target(self.output)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        data = gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        # Domain row zero is displayed at the top by ImGui; do not flip it.
        return Image.frombytes("RGB", (self.width, self.height), data)

    def clone(self):
        """Independent solver snapshot for export; live simulation keeps running."""
        state = self.read_state()
        clone = WaveGPU(self.width, self.height)
        try:
            pixels = self.wall_pixels.copy()
            texture = self.texture(pixels.shape[1], pixels.shape[0], gl.GL_R8,
                                   gl.GL_RED, gl.GL_UNSIGNED_BYTE, pixels)
            gl.glDeleteTextures([clone.walls])
            clone.walls = texture
            clone.wall_pixels = pixels
            for texture in clone.states:
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, self.width, self.height,
                                  gl.GL_RGBA, gl.GL_FLOAT, state)
            clone.tick = self.tick
            return clone
        except Exception:
            clone.close()
            raise

    def close(self):
        gl.glDeleteTextures(self.states + [self.output, self.walls, self.palette])
        gl.glDeleteFramebuffers(1, [self.fbo])
        gl.glDeleteVertexArrays(1, [self.vao])
        for program in self.programs:
            gl.glDeleteProgram(program)
