# Third-party components

The web app bundles its dependencies and assets locally; it does not require a CDN at runtime.

- [jsimgui](https://github.com/mori2003/jsimgui), MIT; JavaScript / WebAssembly bindings and WebGL backend for Dear ImGui. Notice: `public/licenses/jsimgui.txt`.
- [Dear ImGui](https://github.com/ocornut/imgui), MIT; included in jsimgui's WebAssembly build. Notice: `public/licenses/dear-imgui.txt`.
- [gifenc](https://github.com/mattdesl/gifenc), MIT; animated GIF encoding. Notice: `public/licenses/gifenc.txt`.
- [UTIF.js](https://github.com/photopea/UTIF.js), MIT; TIFF image decoding. Notice: `public/licenses/utif.txt`.
- [pako](https://github.com/nodeca/pako), MIT / Zlib; compression support used by UTIF. Notice: `public/licenses/pako.txt`.
- [Noto Sans KR](https://github.com/google/fonts/tree/main/ofl/notosanskr), SIL Open Font License 1.1. `public/fonts/NotoSansKR-Regular.ttf` is the regular-weight instance of the upstream variable font. License: `public/fonts/OFL.txt`.

The wall image and color lookup table in `wifivis/assets/` were extracted from the user-provided reference video. They are shared unchanged by the Python and TypeScript implementations.
