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
    parser = argparse.ArgumentParser(description="Render 1080p hero stills for all 6 stages + contact sheet")
    parser.add_argument("--blend", default=os.path.join(BLENDER_DIR, "big_bang.blend"))
    parser.add_argument("--profile", default="stills_1080p")
    parser.add_argument("--mode", choices=["scaffold", "full"], default="full")
    parser.add_argument("--clean-only", action="store_true")
    parser.add_argument("--include-late", action="store_true")
    parser.add_argument("--frames", default="")
    parser.add_argument("--no-sheet", action="store_true")
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

    out_dir = os.path.join(BLENDER_DIR, "renders", f"stills_{args.profile}")
    os.makedirs(out_dir, exist_ok=True)
    tmp_hud = os.path.join(out_dir, "_hud_tmp.png")

    if args.frames:
        targets = []
        frame_to_id = {st["hero_frame"]: st["id"] for st in cfg["stages"]}
        if "late_hero_frame" in cfg["stages"][-1]:
            frame_to_id[cfg["stages"][-1]["late_hero_frame"]] = "neutrinos_ripples"
        for tok in args.frames.split(","):
            if tok.strip():
                f = int(tok.strip())
                targets.append((frame_to_id.get(f, "frame"), f))
    else:
        targets = [(st["id"], st["hero_frame"]) for st in cfg["stages"]]
        if args.include_late and "late_hero_frame" in cfg["stages"][-1]:
            targets.append(("neutrinos_ripples", cfg["stages"][-1]["late_hero_frame"]))

    labelled_paths = []
    timings = []
    last_sim_frame = -1

    for label_id, frame in targets:
        clean_path = os.path.join(out_dir, f"{label_id}_f{frame:04d}_clean.png")
        lbl_path = os.path.join(out_dir, f"{label_id}_f{frame:04d}.png")

        t0 = time.perf_counter()
        last_sim_frame = _warmup_sim_if_needed(main_scene, frame, last_sim_frame)
        main_scene.render.filepath = clean_path
        bpy.ops.render.render(write_still=True, scene=main_scene.name)

        if not args.clean_only and hud_scene:
            hud_scene.frame_set(frame)
            overlay_hud.update_hud_for_frame(hud_scene, cfg, frame, mode=args.mode)
            hud_scene.render.filepath = tmp_hud
            bpy.ops.render.render(write_still=True, scene=hud_scene.name)
            utils.alpha_over_png(clean_path, tmp_hud, lbl_path)
            labelled_paths.append(lbl_path)
        else:
            labelled_paths.append(clean_path)

        dt = time.perf_counter() - t0
        timings.append(dt)
        print(f"[render_stills] {label_id} (f{frame:04d}): {dt:.2f}s")

    if os.path.exists(tmp_hud):
        os.remove(tmp_hud)

    avg_s = sum(timings) / max(1, len(timings))
    print(f"[render_stills] Avg time per 1080p still ({args.profile}): {avg_s:.2f}s")

    if not args.no_sheet and len(labelled_paths) >= 6:
        sheet_path = os.path.join(BLENDER_DIR, "renders", "milestone2_contact_sheet.png")
        utils.stitch_contact_sheet(labelled_paths[:6], sheet_path, cols=3, rows=2, target_cell_w=960)
        print(f"[render_stills] Contact sheet saved: {sheet_path}")


if __name__ == "__main__":
    main()
