import argparse
import os
import sys
import bpy

BLENDER_DIR = os.path.dirname(os.path.abspath(__file__))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

import scene_utils as utils
import overlay_hud
import stage_1_planck
import stage_2_inflation
import stage_3_qgp
import stage_4_hadrons
import stage_5_matter
import stage_6_neutrinos


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Build Big Bang 3D scene from config.json")
    parser.add_argument("--mode", choices=["scaffold", "full"], default="scaffold")
    parser.add_argument("--profile", default="scaffold_480p")
    parser.add_argument("--out", default=os.path.join(BLENDER_DIR, "big_bang.blend"))
    return parser.parse_args(argv)


def main():
    args = parse_args()
    cfg = utils.load_config()

    utils.clear_scene()
    scene = bpy.context.scene
    scene.name = "BigBang_Main"
    scene.frame_start = cfg["timeline"]["frame_start"]
    scene.frame_end = cfg["timeline"]["frame_end"]
    scene.frame_set(scene.frame_start)

    utils.setup_color_management(scene, cfg)
    utils.apply_render_profile(scene, cfg, args.profile)
    utils.setup_world_volume(scene, cfg, mode=args.mode)
    utils.build_volumetric_lights(scene, cfg, mode=args.mode)
    utils.build_camera_rig(scene, cfg)
    utils.add_timeline_markers(scene, cfg)
    utils.setup_compositor(scene, cfg, mode=args.mode)

    stage_1_planck.build(scene, cfg, mode=args.mode)
    stage_2_inflation.build(scene, cfg, mode=args.mode)
    stage_3_qgp.build(scene, cfg, mode=args.mode)
    stage_4_hadrons.build(scene, cfg, mode=args.mode)
    stage_5_matter.build(scene, cfg, mode=args.mode)
    stage_6_neutrinos.build(scene, cfg, mode=args.mode)

    overlay_hud.build_hud_scene(cfg, mode=args.mode)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    print(f"[build_scene] Saved {args.out} (mode={args.mode}, profile={args.profile})")


if __name__ == "__main__":
    main()
