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
    parser = argparse.ArgumentParser(description="Render resumable preview PNGs + MP4 + contact sheet")
    parser.add_argument("--blend", default=os.path.join(BLENDER_DIR, "big_bang.blend"))
    parser.add_argument("--profile", default="scaffold_480p")
    parser.add_argument("--mode", choices=["scaffold", "full"], default="scaffold")
    parser.add_argument("--labelled", action="store_true", default=True)
    parser.add_argument("--clean-only", action="store_true")
    parser.add_argument("--frames", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--encode", action="store_true")
    parser.add_argument("--contact-sheet", action="store_true")
    parser.add_argument("--out-name", default="")
    parser.add_argument("--sheet-name", default="")
    return parser.parse_args(argv)


def _warmup_sim_if_needed(scene, target_frame, last_sim_frame):
    # Stage 3 QGP simulation zone runs from frame 125..278
    if 125 <= target_frame <= 278:
        start_f = 125 if last_sim_frame < 125 or last_sim_frame > target_frame else last_sim_frame + 1
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

    render_root = os.path.join(BLENDER_DIR, "renders", args.profile)
    clean_dir = os.path.join(render_root, "clean")
    labelled_dir = os.path.join(render_root, "labelled")
    os.makedirs(clean_dir, exist_ok=True)
    if not args.clean_only:
        os.makedirs(labelled_dir, exist_ok=True)

    if args.frames:
        frame_list = [int(x.strip()) for x in args.frames.split(",") if x.strip()]
    else:
        frame_list = list(range(cfg["timeline"]["frame_start"], cfg["timeline"]["frame_end"] + 1))

    tmp_hud = os.path.join(render_root, "_hud_tmp.png")
    timings = []
    last_sim_frame = -1
    t_all_start = time.perf_counter()

    for idx, f in enumerate(frame_list):
        clean_path = os.path.join(clean_dir, f"frame_{f:04d}.png")
        lbl_path = os.path.join(labelled_dir, f"frame_{f:04d}.png")

        need_clean = args.overwrite or not os.path.exists(clean_path)
        need_lbl = (not args.clean_only) and (args.overwrite or not os.path.exists(lbl_path))

        if not need_clean and not need_lbl:
            continue

        t0 = time.perf_counter()
        if need_clean:
            last_sim_frame = _warmup_sim_if_needed(main_scene, f, last_sim_frame)
            main_scene.render.filepath = clean_path
            bpy.ops.render.render(write_still=True, scene=main_scene.name)

        if need_lbl and hud_scene:
            hud_scene.frame_set(f)
            overlay_hud.update_hud_for_frame(hud_scene, cfg, f, mode=args.mode)
            hud_scene.render.filepath = tmp_hud
            bpy.ops.render.render(write_still=True, scene=hud_scene.name)
            utils.alpha_over_png(clean_path, tmp_hud, lbl_path)

        dt = time.perf_counter() - t0
        timings.append(dt)
        if (idx + 1) % 24 == 0 or len(frame_list) <= 20:
            avg = sum(timings) / len(timings)
            print(f"[render_preview] Frame {f:04d} ({idx + 1}/{len(frame_list)}): {dt:.3f}s (avg {avg:.3f}s/f)")

    if os.path.exists(tmp_hud):
        os.remove(tmp_hud)

    total_s = time.perf_counter() - t_all_start
    if timings:
        avg_s = sum(timings) / len(timings)
        print(
            f"[render_preview] Rendered {len(timings)} frames in {total_s:.1f}s "
            f"(avg {avg_s:.3f}s/frame, min {min(timings):.3f}s, max {max(timings):.3f}s)"
        )

    if args.contact_sheet:
        hero_frames = [st["hero_frame"] for st in cfg["stages"]]
        src_dir = clean_dir if args.clean_only else labelled_dir
        hero_paths = [os.path.join(src_dir, f"frame_{hf:04d}.png") for hf in hero_frames]
        missing = [p for p in hero_paths if not os.path.exists(p)]
        if not missing:
            sheet_name = args.sheet_name or f"{args.profile}_contact_sheet.png"
            sheet_path = os.path.join(BLENDER_DIR, "renders", sheet_name)
            utils.stitch_contact_sheet(hero_paths, sheet_path, cols=3, rows=2)
            print(f"[render_preview] Saved contact sheet: {sheet_path}")

    if args.encode:
        src_dir = clean_dir if args.clean_only else labelled_dir
        mp4_name = args.out_name or f"{args.profile}.mp4"
        mp4_path = os.path.join(BLENDER_DIR, "renders", mp4_name)
        utils.encode_png_sequence(
            src_dir,
            mp4_path,
            fps=cfg["timeline"]["fps"],
            width=prof["width"],
            height=prof["height"],
        )
        print(f"[render_preview] Encoded video: {mp4_path}")


if __name__ == "__main__":
    main()
