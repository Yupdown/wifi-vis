import argparse
from pathlib import Path
import time

import glfw
import imgui
import numpy as np
from imgui.integrations.glfw import GlfwRenderer
from OpenGL import GL as gl
from PIL import Image

from .gpu import ROOT, WaveGPU
from .gif_export import FPS, GifExport, choose_gif_file, phase_offsets
from .model import MAX_SOURCES, Scene
from .walls import choose_wall_file, load_wall_map


class Application:
    def __init__(self, hidden=False):
        if not glfw.init():
            raise RuntimeError("GLFW initialization failed. A desktop and OpenGL 3.3 driver are required.")
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
        glfw.window_hint(glfw.VISIBLE, not hidden)
        self.window = glfw.create_window(920, 980, "WiFi Field | Signal Intensity Visualization", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Could not create an OpenGL 3.3 window. Update the graphics driver.")
        glfw.set_window_size_limits(self.window, 760, 680, glfw.DONT_CARE, glfw.DONT_CARE)
        glfw.make_context_current(self.window)
        glfw.swap_interval(0 if hidden else 1)
        self.context = imgui.create_context()
        imgui.get_io().ini_file_name = None
        font = Path("C:/Windows/Fonts/malgun.ttf")
        if font.exists():
            fonts = imgui.get_io().fonts
            fonts.add_font_from_file_ttf(str(font), 16, glyph_ranges=fonts.get_glyph_ranges_korean())
        self.ui = GlfwRenderer(self.window)
        self.style()
        self.gpu = WaveGPU()
        self.scene = Scene()
        self.paused = False
        self.adding = False
        self.dragging = None
        self.speed = 1.0
        self.loss = .001
        self.transmission = .15
        self.exposure = 5.0
        self.mode = 0
        self.walls = True
        self.show_walls = True
        self.markers = True
        self.accumulator = 0.0
        self.canvas_rect = None
        self.wall_path = None
        self.wall_inverted = False
        self.wall_error = ""
        self.pending_wall = None
        self.gif_phase_step = 7.2
        self.pending_gif = None
        self.gif_job = None
        self.gif_message = ""
        self.gif_error = False
        self.last_gif_path = None
        self.last_time = time.perf_counter()
        self.gpu.step(self.scene.sources, 700)

    @staticmethod
    def style():
        imgui.style_colors_dark()
        style = imgui.get_style()
        style.window_padding = (20, 16)
        style.frame_padding = (9, 4)
        style.item_spacing = (9, 7)
        style.window_rounding = 0
        style.frame_rounding = 5
        style.grab_rounding = 5
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = (.035, .047, .07, 1)
        style.colors[imgui.COLOR_CHILD_BACKGROUND] = (.055, .072, .10, 1)
        style.colors[imgui.COLOR_FRAME_BACKGROUND] = (.10, .13, .18, 1)
        style.colors[imgui.COLOR_BUTTON] = (.13, .23, .32, 1)
        style.colors[imgui.COLOR_BUTTON_HOVERED] = (.16, .37, .47, 1)
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = (.18, .46, .54, 1)
        style.colors[imgui.COLOR_CHECK_MARK] = (.33, .86, .83, 1)
        style.colors[imgui.COLOR_SLIDER_GRAB] = (.33, .86, .83, 1)
        style.colors[imgui.COLOR_HEADER] = (.12, .29, .36, 1)
        style.colors[imgui.COLOR_TEXT] = (.90, .94, .98, 1)

    @staticmethod
    def muted(text):
        imgui.text_colored(text, .48, .58, .69)

    @staticmethod
    def section(text):
        imgui.spacing()
        imgui.text_colored(text, .36, .85, .82)
        imgui.separator()

    def controls(self):
        self.section(f"TRANSMITTERS   /   {len(self.scene.sources):02d} OF {MAX_SOURCES}")
        if imgui.button("Place transmitter", -1, 34):
            self.adding = not self.adding
        if self.adding:
            imgui.text_colored("Click the map to place. Esc cancels.", .97, .76, .35)
        else:
            self.muted("Double-click the map to add.")
        imgui.begin_child("source_list", 0, 76, border=True)
        for source in self.scene.sources:
            clicked, _ = imgui.selectable(
                f"TX {source.id:02d}    {source.frequency:.1f} GHz" + ("  [off]" if not source.enabled else ""),
                source.id == self.scene.selected)
            if clicked:
                self.scene.selected = source.id
        imgui.end_child()
        source = self.scene.current()
        imgui.text(f"Selected: TX {source.id:02d}")
        imgui.same_line(spacing=20)
        _, source.enabled = imgui.checkbox("Enabled", source.enabled)
        imgui.push_item_width(155)
        _, source.power = imgui.slider_float("Power", source.power, .05, 3, "%.2f x")
        _, source.frequency = imgui.slider_float("Frequency", source.frequency, 1, 6, "%.2f GHz")
        _, source.phase = imgui.slider_float("Phase", source.phase, -180, 180, "%.0f deg")
        imgui.pop_item_width()
        self.muted(f"Position   {source.x*100:5.1f}% / {source.y*100:5.1f}%")
        if len(self.scene.sources) > 1:
            if imgui.button("Remove selected", -1):
                self.scene.remove_selected()
        else:
            self.muted("Keep at least one transmitter.")

        self.section("SIMULATION")
        if imgui.button("Resume" if self.paused else "Pause", 126, 32):
            self.paused = not self.paused
        imgui.same_line()
        if imgui.button("Clear waves", -1, 32):
            self.gpu.clear()
        imgui.push_item_width(155)
        _, self.speed = imgui.slider_float("Speed", self.speed, .1, 3, "%.1f x")
        _, self.loss = imgui.slider_float("Air loss", self.loss, .0001, .01, "%.4f")
        _, self.transmission = imgui.slider_float("Wall pass", self.transmission, .01, 1, "%.2f")
        imgui.pop_item_width()
        changed, self.walls = imgui.checkbox("Use walls", self.walls)
        if changed:
            self.gpu.clear()

        self.section("HEATMAP")
        _, self.show_walls = imgui.checkbox("Wall visualization", self.show_walls)
        imgui.push_item_width(155)
        _, self.mode = imgui.combo("Display", self.mode, ["Instant wave", "Mean intensity"])
        _, self.exposure = imgui.slider_float("Gain", self.exposure, .5, 15, "%.1f")
        imgui.pop_item_width()
        _, self.markers = imgui.checkbox("Show transmitter markers", self.markers)
        imgui.image(self.gpu.palette, max(1, imgui.get_content_region_available_width()), 16)
        self.muted("WEAK                                      STRONG")
        self.muted("Sampled from the reference video")
        if imgui.button("Reset scene", -1):
            self.scene = Scene()
            self.dragging = None
            self.adding = False
            self.gpu.clear()

    def pointer(self, x, y, width, height, hovered, clicked, double_clicked, down):
        """Map input to normalized simulation coordinates, independent of DPI."""
        if clicked and hovered:
            hit = self.scene.hit_test(x, y, width, height)
            if self.adding or (double_clicked and hit is None):
                source = self.scene.add(x, y)
                if source:
                    self.dragging = source.id
                self.adding = False
            elif hit is not None:
                self.scene.selected = hit
                self.dragging = hit
        if self.dragging is not None:
            if down:
                self.scene.move(self.dragging, x, y)
            else:
                self.dragging = None

    def load_wall(self, path=None, invert=None):
        """Run between frames: queued ImGui draws must not use deleted textures."""
        try:
            if path is None:
                with Image.open(ROOT / "assets/walls.png") as image:
                    pixels = np.array(image.resize((336, 1074), Image.Resampling.BILINEAR))
                inverted = False
            else:
                wall_map = load_wall_map(path, invert)
                pixels, inverted = wall_map.pixels, wall_map.inverted
            self.gpu.set_wall_map(pixels)
        except Exception as error:
            self.wall_error = f"Could not load wall image: {error}"
            return False
        self.wall_path = Path(path).resolve() if path is not None else None
        self.wall_inverted = inverted
        self.wall_error = ""
        self.walls = True
        self.accumulator = 0
        self.dragging = None
        self.adding = False
        return True

    def browse_wall(self):
        try:
            path = choose_wall_file(self.wall_path.parent if self.wall_path else None)
            if path is not None:
                self.pending_wall = (path, None)
        except Exception as error:
            self.wall_error = f"Could not open file chooser: {error}"
        finally:
            self.last_time = time.perf_counter()

    def canvas(self):
        imgui.text("CUSTOM PLAN" if self.wall_path else "REFERENCE PLAN")
        imgui.same_line()
        self.muted("/  live wave field")
        if imgui.button("Open wall image..."):
            self.browse_wall()
        imgui.same_line()
        if imgui.button("Use reference"):
            self.pending_wall = (None, None)
        if self.wall_path:
            name = self.wall_path.name
            self.muted(name if len(name) < 42 else name[:39] + "...")
            if imgui.is_item_hovered():
                imgui.set_tooltip(str(self.wall_path))
            changed, inverted = imgui.checkbox("Dark walls on light background", self.wall_inverted)
            if changed:
                self.pending_wall = (self.wall_path, inverted)
        if self.wall_error:
            imgui.push_style_color(imgui.COLOR_TEXT, 1, .5, .4, 1)
            imgui.text_wrapped(self.wall_error)
            imgui.pop_style_color()
        self.gif_controls()
        available_w, available_h = imgui.get_content_region_available()
        height = max(100, available_h - 45)
        width = height * self.gpu.width / self.gpu.height
        if width > available_w:
            width = available_w
            height = width * self.gpu.height / self.gpu.width
        pos = imgui.get_cursor_screen_pos()
        left = pos.x + (available_w-width)/2
        top = pos.y
        imgui.set_cursor_screen_pos((left, top))
        imgui.image(self.gpu.output, width, height)
        self.canvas_rect = (left, top, width, height)
        hovered = imgui.is_item_hovered()
        mx, my = imgui.get_io().mouse_pos
        x, y = (mx-left)/width, (my-top)/height
        self.pointer(x, y, width, height, hovered,
                     imgui.is_mouse_clicked(0), imgui.is_mouse_double_clicked(0), imgui.is_mouse_down(0))
        draw = imgui.get_window_draw_list()
        if self.markers:
            for source in self.scene.sources:
                sx, sy = left+source.x*width, top+source.y*height
                selected = source.id == self.scene.selected
                color = imgui.get_color_u32_rgba(*((.30, 1, .91, 1) if selected else (1, 1, 1, .9)))
                if not source.enabled:
                    color = imgui.get_color_u32_rgba(.5, .55, .6, .8)
                draw.add_circle_filled(sx, sy, 8, imgui.get_color_u32_rgba(.015, .025, .04, .95))
                draw.add_circle(sx, sy, 11 if selected else 8, color, thickness=2)
                draw.add_line(sx-4, sy, sx+4, sy, color, 1.5)
                draw.add_line(sx, sy-4, sx, sy+4, color, 1.5)
                label_x = sx+15 if source.x < .70 else sx-49
                draw.add_text(label_x+1, sy-9+1, imgui.get_color_u32_rgba(0, 0, 0, 1), f"TX {source.id}")
                draw.add_text(label_x, sy-9, color, f"TX {source.id}")
        if hovered:
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)
        imgui.set_cursor_screen_pos((pos.x, top+height+12))
        self.muted("Drag a source to move it.  |  Space: pause")

    def frame(self, dt=None):
        glfw.poll_events()
        self.ui.process_inputs()
        if self.pending_wall is not None:
            pending, self.pending_wall = self.pending_wall, None
            self.load_wall(*pending)
        if self.pending_gif is not None:
            path, interval = self.pending_gif
            self.pending_gif = None
            self.start_gif(path, interval)
        self.update_gif()
        now = time.perf_counter()
        elapsed = min(.05, now-self.last_time) if dt is None else dt
        self.last_time = now
        imgui.new_frame()
        io = imgui.get_io()
        if not io.want_text_input:
            if imgui.is_key_pressed(glfw.KEY_SPACE, False):
                self.paused = not self.paused
            if imgui.is_key_pressed(glfw.KEY_ESCAPE, False):
                self.adding = False
                self.dragging = None
        if not self.paused:
            self.accumulator += elapsed * 720 * self.speed
            steps = min(108, int(self.accumulator))
            self.accumulator -= steps
            if steps:
                self.gpu.step(self.scene.sources, steps, self.loss, self.transmission, self.walls)
        self.gpu.render(self.exposure, self.mode, self.show_walls)
        width, height = glfw.get_window_size(self.window)
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(width, height)
        flags = (imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_MOVE |
                 imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS)
        imgui.begin("WiFi Field", flags=flags)
        imgui.text_colored("W I F I   /   F I E L D", .42, .92, .87)
        imgui.same_line(spacing=24)
        self.muted("Signal Intensity Visualization")
        imgui.text("Explore propagation. Move the source. See the interference.")
        imgui.separator()
        imgui.begin_child("viewport", width-380, -33, border=True)
        self.canvas()
        imgui.end_child()
        imgui.same_line()
        imgui.begin_child("controls", 0, -33, border=True)
        self.controls()
        imgui.end_child()
        status = "PAUSED" if self.paused else "LIVE"
        imgui.text_colored(status, .38, .88, .81)
        imgui.same_line()
        self.muted(f"OpenGL 3.3   |   {self.gpu.width} x {self.gpu.height}   |   Step {self.gpu.tick:,}   |   {io.framerate:.0f} FPS")
        imgui.end()
        imgui.render()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        fbw, fbh = glfw.get_framebuffer_size(self.window)
        gl.glViewport(0, 0, fbw, fbh)
        gl.glClearColor(.035, .047, .07, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        self.ui.render(imgui.get_draw_data())

    def browse_gif(self):
        try:
            path = choose_gif_file(self.last_gif_path.parent if self.last_gif_path else None)
            if path is not None:
                self.pending_gif = (path, self.gif_phase_step)
        except Exception as error:
            self.gif_message = f"Could not open save dialog: {error}"
            self.gif_error = True
        finally:
            self.last_time = time.perf_counter()

    def start_gif(self, path, interval):
        if self.gif_job is not None:
            return False
        try:
            self.gif_job = GifExport(
                self.gpu, self.scene, path, interval, exposure=self.exposure,
                mode=self.mode, walls=self.walls, show_walls=self.show_walls, loss=self.loss,
                transmission=self.transmission, markers=self.markers)
            self.gif_message = ""
            self.gif_error = False
            return True
        except Exception as error:
            self.gif_message = f"GIF export failed: {error}"
            self.gif_error = True
            return False

    def update_gif(self):
        job = self.gif_job
        if job is None:
            return
        job.advance()
        if job.done:
            if job.error:
                self.gif_message = f"GIF export failed: {job.error}"
                self.gif_error = True
            elif job.cancelled:
                self.gif_message = "GIF export cancelled."
            else:
                self.last_gif_path = job.path
                self.gif_message = f"Saved: {job.path.name}  ({len(job.offsets)} samples, {FPS} FPS)"
            job.close()
            self.gif_job = None

    def gif_controls(self):
        if self.gif_job is None:
            imgui.push_item_width(130)
            _, self.gif_phase_step = imgui.slider_float("GIF phase step", self.gif_phase_step, 1, 180, "%.1f deg")
            self.gif_phase_step = min(180.0, max(1.0, round(self.gif_phase_step, 1)))
            imgui.pop_item_width()
            if imgui.get_content_region_available_width() > 380:
                imgui.same_line()
            if imgui.button("Save GIF..."):
                self.browse_gif()
            count = len(phase_offsets(self.gif_phase_step, self.scene.current().frequency))
            self.muted(f"360 deg / TX {self.scene.selected}  |  {count} frames  |  {FPS} FPS  |  {count/FPS:.2f} s")
        else:
            job = self.gif_job
            label = "Writing GIF..." if job.future else f"Capturing GIF {len(job.frames)}/{len(job.offsets)}"
            imgui.progress_bar(job.progress, (max(1, imgui.get_content_region_available_width()-92), 22), label)
            if job.future is None:
                imgui.same_line()
                if imgui.button("Cancel"):
                    job.cancel()
        if self.gif_message:
            color = (1, .5, .4, 1) if self.gif_error else (.4, .85, .75, 1)
            imgui.push_style_color(imgui.COLOR_TEXT, *color)
            imgui.text_wrapped(self.gif_message)
            imgui.pop_style_color()
            if self.last_gif_path and imgui.is_item_hovered():
                imgui.set_tooltip(str(self.last_gif_path))

    def screenshot(self, path):
        width, height = glfw.get_framebuffer_size(self.window)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.frombytes("RGB", (width, height), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(output)

    def close(self):
        if self.gif_job is not None:
            self.gif_job.close()
            self.gif_job = None
        self.gpu.close()
        self.ui.shutdown()
        imgui.destroy_context(self.context)
        glfw.destroy_window(self.window)
        glfw.terminate()

    def run(self, frames=0, screenshot=None):
        count = 0
        try:
            while not glfw.window_should_close(self.window):
                if glfw.get_framebuffer_size(self.window)[0] == 0:
                    glfw.wait_events_timeout(.05)
                    continue
                self.frame()
                count += 1
                if frames and count >= frames:
                    if screenshot:
                        self.screenshot(screenshot)
                    break
                glfw.swap_buffers(self.window)
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="Interactive OpenGL Wi-Fi wave field")
    parser.add_argument("--hidden", action="store_true", help="Create an invisible window for automated checks")
    parser.add_argument("--frames", type=int, default=0, help="Exit after N frames (0 = interactive)")
    parser.add_argument("--screenshot", type=Path, help="Save the final frame when using --frames")
    args = parser.parse_args()
    Application(hidden=args.hidden).run(args.frames, args.screenshot)
