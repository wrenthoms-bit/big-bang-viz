import argparse
import os
import sys
import time
import bpy

BLENDER_DIR = os.path.dirname(os.path.abspath(__file__))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

import scene_utils as utils
import overlay_hud


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Render 1080p24 CLEAN and LABELLED finals + ProRes 422 HQ & H.264 MP4")
    parser.add_argument("--blend", default=os.path.join(BLENDER_DIR, "big_bang.blend"))
    parser.add_argument("--profile", default="final_1080p")
    parser.add_argument("--ranges", default="", help="Comma-separated frame ranges or numbers, e.g. 1-172,246-402")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-encode", action="store_true")
    return parser.parse_args(argv)


def _parse_frame_ranges(ranges_str, f_start, f_end):
    if not ranges_str or not ranges_str.strip():
        return list(range(f_start, f_end + 1))
    selected = set()
    for tok in ranges_str.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok:
            parts = tok.split("-", 1)
            a = max(f_start, int(parts[0].strip()))
            b = min(f_end, int(parts[1].strip()))
            if a <= b:
                selected.update(range(a, b + 1))
        else:
            f = int(tok)
            if f_start <= f <= f_end:
                selected.add(f)
    return sorted(selected)


def _warmup_sim_if_needed(scene, target_frame, last_sim_frame):
    # Stage 3 QGP simulation zone runs from frame 125..278
    if 125 <= target_frame <= 278:
        if last_sim_frame < 125 or last_sim_frame > target_frame:
            scene.frame_set(1)
            start_f = 120
        else:
            start_f = last_sim_frame + 1
        for sf in range(start_f, target_frame + 1):
            scene.frame_set(sf)
        return target_frame
    scene.frame_set(target_frame)
    return last_sim_frame


def main():
    args = parse_args()
    cfg = utils.load_config()
    bpy.ops.wm.open_mainfile(filepath=args.blend)

    main_scene = bpy.data.scenes.get("BigBang_Main", bpy.context.scene)
    hud_scene = bpy.data.scenes.get("HUD_Scene")
    prof = cfg["render_profiles"][args.profile]
    utils.apply_render_profile(main_scene, cfg, args.profile)

    if hud_scene:
        hud_scene.render.resolution_x = prof["width"]
        hud_scene.render.resolution_y = prof["height"]
        hud_scene.render.resolution_percentage = 100
        hud_scene.render.image_settings.file_format = "PNG"
        hud_scene.render.image_settings.color_mode = "RGBA"

    final_root = os.path.join(BLENDER_DIR, "renders", "final_1080p")
    clean_dir = os.path.join(final_root, "clean")
    labelled_dir = os.path.join(final_root, "labelled")
    os.makedirs(clean_dir, exist_ok=True)
    os.makedirs(labelled_dir, exist_ok=True)

    tmp_hud = os.path.join(final_root, "_hud_tmp.png")
    timings = []
    last_sim_frame = -1
    t_all_start = time.perf_counter()
    f_start = cfg["timeline"]["frame_start"]
    f_end = cfg["timeline"]["frame_end"]
    frame_list = _parse_frame_ranges(args.ranges, f_start, f_end)

    for idx, f in enumerate(frame_list):
        clean_path = os.path.join(clean_dir, f"frame_{f:04d}.png")
        lbl_path = os.path.join(labelled_dir, f"frame_{f:04d}.png")

        need_clean = args.overwrite or not os.path.exists(clean_path)
        need_lbl = args.overwrite or not os.path.exists(lbl_path)
        if not need_clean and not need_lbl:
            continue

        t0 = time.perf_counter()
        if need_clean:
            last_sim_frame = _warmup_sim_if_needed(main_scene, f, last_sim_frame)
            main_scene.render.filepath = clean_path
            bpy.ops.render.render(write_still=True, scene=main_scene.name)

        if need_lbl and hud_scene:
            hud_scene.frame_set(f)
            overlay_hud.update_hud_for_frame(hud_scene, cfg, f, mode="full")
            hud_scene.render.filepath = tmp_hud
            bpy.ops.render.render(write_still=True, scene=hud_scene.name)
            utils.alpha_over_png(clean_path, tmp_hud, lbl_path)

        dt = time.perf_counter() - t0
        timings.append(dt)
        if len(timings) % 24 == 0 or (idx + 1) == len(frame_list):
            avg = sum(timings) / len(timings)
            print(f"[render_final] Frame {f:04d} ({idx + 1}/{len(frame_list)}): {dt:.2f}s (avg {avg:.2f}s/f)")

    if os.path.exists(tmp_hud):
        os.remove(tmp_hud)

    total_s = time.perf_counter() - t_all_start
    if timings:
        avg_s = sum(timings) / len(timings)
        print(
            f"[render_final] Rendered {len(timings)} frames in {total_s:.1f}s "
            f"(avg {avg_s:.3f}s/frame, min {min(timings):.3f}s, max {max(timings):.3f}s)"
        )

    if not args.skip_encode:
        fps = cfg["timeline"]["fps"]
        t_enc0 = time.perf_counter()
        utils.encode_png_sequence(
            clean_dir,
            os.path.join(BLENDER_DIR, "renders", "big_bang_1080p24_clean.mp4"),
            out_prores=os.path.join(BLENDER_DIR, "renders", "big_bang_1080p24_clean_prores422hq.mov"),
            fps=fps,
            width=prof["width"],
            height=prof["height"],
        )
        print(f"[render_final] Encoded CLEAN MP4 + ProRes 422 HQ in {time.perf_counter() - t_enc0:.1f}s")

        t_enc1 = time.perf_counter()
        utils.encode_png_sequence(
            labelled_dir,
            os.path.join(BLENDER_DIR, "renders", "big_bang_1080p24_labelled.mp4"),
            out_prores=os.path.join(BLENDER_DIR, "renders", "big_bang_1080p24_labelled_prores422hq.mov"),
            fps=fps,
            width=prof["width"],
            height=prof["height"],
        )
        print(f"[render_final] Encoded LABELLED MP4 + ProRes 422 HQ in {time.perf_counter() - t_enc1:.1f}s")


if __name__ == "__main__":
    main()
