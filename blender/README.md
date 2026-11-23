# Big Bang: The First ~3 Seconds (Blender 5.3 Pipeline)

Procedural, script-driven Blender 5.3 animation matching the story, timings, palette, and labels of the Three.js visualization (`20.0s @ 24 fps = 480 frames`).

## Project Files

- `config.json` — All tunable timings, shell radii, camera spline knots, colors, volumetric parameters, compositor settings, and render profiles.
- `cues.txt` — Stage start/end timestamps in seconds and 24 fps frame numbers.
- `build_scene.py` — Builds `big_bang.blend` from scratch using `config.json`.
- `stage_1_planck.py` … `stage_6_neutrinos.py` — One modular builder per cosmic epoch.
- `overlay_hud.py` — Dedicated orthographic `HUD_Scene` overlay (DOF-free, transparent alpha-over composite for `LABELLED` output).
- `render_preview.py` — Resumable PNG renderer + 6-stage contact sheet + H.264 MP4 encoder for Milestones 1 & 3.
- `render_stills.py` — 1080p hero still renderer + 3×2 contact sheet for Milestone 2 (supports EEVEE and Cycles Metal GPU).
- `render_final.py` — Resumable 1080p24 PNG renderer for `CLEAN` and `LABELLED` versions + ProRes 422 HQ (`.mov`) and H.264 (`.mp4`) export.

## Commands (Run from repo root)

```bash
# Build Milestone 1 scaffold scene
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/build_scene.py -- --mode scaffold

# Render Milestone 1 480p preview (resumable PNGs + contact sheet + MP4)
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/render_preview.py -- --profile scaffold_480p --mode scaffold --contact-sheet --encode

# Build full look-dev scene (EEVEE 1080p profile)
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/build_scene.py -- --mode full --profile stills_1080p

# Render Milestone 2 1080p look-dev stills + contact sheet (add --include-late for f0471)
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/render_stills.py -- --profile stills_1080p --mode full --include-late

# Optional Cycles Metal GPU single-still benchmark (Stage 3 hero frame 205)
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/render_stills.py -- --profile cycles_still_1080p --mode full --frames 205 --no-sheet

# Build & render Milestone 3 720p full EEVEE preview
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/build_scene.py -- --mode full --profile preview_720p
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/render_preview.py -- --profile preview_720p --mode full --contact-sheet --encode --out-name milestone3_preview_720p.mp4 --sheet-name milestone3_contact_sheet.png

# Build & render Milestone 4 1080p24 CLEAN + LABELLED finals (PNGs + ProRes 422 HQ + H.264 MP4)
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/build_scene.py -- --mode full --profile final_1080p
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/render_final.py -- --profile final_1080p
```

### Final Deliverables (`blender/renders/`)
- `final_1080p/clean/frame_0001.png` … `frame_0480.png` — 480 `CLEAN` 1080p PNGs (no HUD)
- `final_1080p/labelled/frame_0001.png` … `frame_0480.png` — 480 `LABELLED` 1080p PNGs (time/temp/stage HUD)
- `big_bang_1080p24_clean.mp4` & `big_bang_1080p24_clean_prores422hq.mov` — `CLEAN` master exports
- `big_bang_1080p24_labelled.mp4` & `big_bang_1080p24_labelled_prores422hq.mov` — `LABELLED` master exports

## Measured Performance on Apple Mac mini M4 (Blender 5.3.0 Beta)

- **Milestone 1 (`scaffold_480p`, `854×480` EEVEE, 8 samples, tile size 8, 32 vol samples + HUD composite)**:
  - **0.445 s / frame** average across frames 1–480 (`0.391 s` min, `0.904 s` max; `472` remaining frames rendered in `210.0 s` / `~3.5 min`, plus `4.6 s` H.264 `.mp4` encode via Blender VSE FFmpeg).
- **Milestone 2 (`stills_1080p`, `1920×1080` EEVEE, 32 samples, tile size 4, 64 vol samples + HUD composite)**:
  - **4.02 s / frame** average across all 7 hero stills (`3.26 s`–`5.12 s`: `planck f0022: 3.59 s`, `inflation f0097: 4.51 s`, `qgp f0205: 5.12 s`, `hadrons f0303: 4.11 s`, `matter f0359: 4.21 s`, `neutrinos f0409: 3.32 s`, `neutrinos_ripples f0471: 3.26 s`).
  - Projected 480-frame 1080p EEVEE final (`CLEAN` + `LABELLED` pass): **~32 min**.
- **Optional Cycles Metal Benchmark (`cycles_still_1080p`, `1920×1080` `CYCLES` `Apple M4 (GPU - 10 cores)`, 64 samples + OIDN denoiser, volume step rate 1.5, max steps 128, 1 volume bounce + HUD composite)**:
  - **192.82 s / frame** (~3.2 min) on Stage 3 `qgp (f0205)`.
  - Projected 480-frame 1080p Cycles sequence: **~25.7 hours** (suitable for hero stills or a multi-day/overnight split render).
- **Milestone 3 (`preview_720p`, `1280×720` EEVEE, 16 samples, tile size 8, 48 vol samples + HUD composite)**:
  - **0.969 s / frame** average across the 468 main pass frames (`0.681 s` min, `1.594 s` max; `453.3 s` / `~7.6 min`, following the 12-frame transition gate at `1.103 s / frame` / `13.2 s`), plus contact sheet and `17 MB` `1280×720` `24 fps` H.264 `.mp4` encode (`milestone3_preview_720p.mp4`).
- **Milestone 4 (`final_1080p`, `1920×1080 @ 24 fps` EEVEE, 32 samples, tile size 4, 64 vol samples, `CLEAN` + `LABELLED` passes)**:
  - **4.283 s / frame** average across all 480 frames (`3.069 s` min, `5.911 s` max; rendered in `2056.0 s` / `34.3 min`).
  - Encoding via Blender VSE FFmpeg: **22.3 s** for `CLEAN` (`big_bang_1080p24_clean.mp4` `30 MB` + `big_bang_1080p24_clean_prores422hq.mov` `567 MB`) and **22.8 s** for `LABELLED` (`big_bang_1080p24_labelled.mp4` `28 MB` + `big_bang_1080p24_labelled_prores422hq.mov` `569 MB`).
