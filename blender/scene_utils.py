import json
import math
import os
import shutil
import subprocess
import bpy
import numpy as np
from mathutils import Vector

BLENDER_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BLENDER_DIR, "config.json")


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(edge0, edge1, x):
    if abs(edge1 - edge0) < 1e-8:
        return 1.0 if x >= edge1 else 0.0
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def frame_to_seconds(frame, cfg):
    fps = cfg["timeline"]["fps"]
    return clamp((frame - 1) / float(fps), 0.0, cfg["timeline"]["duration_seconds"])


def sample_piecewise_smooth(anchors, u):
    clamped = clamp(u, anchors[0][0], anchors[-1][0])
    for i in range(len(anchors) - 1):
        u0, v0 = anchors[i]
        u1, v1 = anchors[i + 1]
        if clamped <= u1 or i == len(anchors) - 2:
            t = (clamped - u0) / max(1e-6, u1 - u0)
            s = t * t * (3.0 - 2.0 * t)
            return lerp(v0, v1, lerp(t, s, 0.45))
    return anchors[-1][1]


def sample_monotonic_spline(knots, u):
    c = clamp(u, knots[0][0], knots[-1][0])
    for i in range(len(knots) - 1):
        t0, y0 = knots[i]
        t1, y1 = knots[i + 1]
        if c <= t1 or i == len(knots) - 2:
            local_t = clamp((c - t0) / max(1e-6, t1 - t0), 0.0, 1.0)
            s = local_t * local_t * (3.0 - 2.0 * local_t)
            return lerp(y0, y1, lerp(local_t, s, 0.65))
    return knots[-1][1]


_SUPERSCRIPTS = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def to_sup(text):
    return str(text).translate(_SUPERSCRIPTS)


def get_physical_time(u, cfg):
    log10_s = sample_piecewise_smooth(cfg["time_anchors"], u)
    seconds = math.pow(10.0, log10_s)
    if log10_s < -0.3:
        exp = math.floor(log10_s)
        mantissa = math.pow(10.0, log10_s - exp)
        if mantissa >= 9.95:
            mantissa = 1.0
            exp += 1
        if u <= 0.04:
            return f"10{to_sup('-43')} s"
        return f"{mantissa:.1f} × 10{to_sup(exp)} s"
    return f"~{seconds:.1f} s"


def get_temperature(u, cfg):
    log10_k = sample_piecewise_smooth(cfg["temp_anchors"], u)
    exp = math.floor(log10_k)
    mantissa = math.pow(10.0, log10_k - exp)
    if mantissa >= 9.95:
        mantissa = 1.0
        exp += 1
    return f"~{mantissa:.1f} × 10{to_sup(exp)} K"


def get_stage_weights(u):
    return {
        "planck": 1.0 - smoothstep(1.55, 2.75, u),
        "inflation": smoothstep(1.55, 2.35, u) * (1.0 - smoothstep(5.45, 6.65, u)),
        "qgp": smoothstep(5.45, 6.45, u) * (1.0 - smoothstep(10.35, 11.45, u)),
        "hadrons": smoothstep(10.45, 11.25, u) * (1.0 - smoothstep(13.55, 14.35, u)),
        "matter": smoothstep(13.55, 14.25, u) * (1.0 - smoothstep(15.65, 16.45, u)),
        "neutrinos": smoothstep(15.65, 16.35, u) * (1.0 - smoothstep(18.6, 19.55, u)),
        "ripples": smoothstep(17.2, 18.8, u),
    }


def get_active_stage(u, cfg):
    dur = cfg["timeline"]["duration_seconds"]
    cu = clamp(u, 0.0, dur)
    stages = cfg["stages"]
    idx = len(stages) - 1
    for i, st in enumerate(stages):
        if cu < st["end_s"] or i == len(stages) - 1:
            idx = i
            break
    st = stages[idx]
    fade_in = 1.0 if idx == 0 else smoothstep(st["start_s"], st["start_s"] + 0.25, cu)
    fade_out = 1.0 if idx == len(stages) - 1 else 1.0 - smoothstep(st["end_s"] - 0.25, st["end_s"], cu)
    opacity = clamp(min(fade_in, fade_out), 0.0, 1.0)
    subtitle = st["subtitle"]
    if idx == len(stages) - 1 and cu >= st.get("late_subtitle_s", 18.2) and "late_subtitle" in st:
        subtitle = st["late_subtitle"]
    return {
        "index": idx,
        "stage": st,
        "opacity": opacity,
        "subtitle": subtitle,
    }


def get_camera_pose(u, cfg):
    cam_cfg = cfg["camera"]
    dur = cfg["timeline"]["duration_seconds"]
    cu = clamp(u, 0.0, dur)
    R = sample_monotonic_spline(cam_cfg["radius_knots"], cu)
    theta = cam_cfg["azimuth_rate"] * cu
    phi = cam_cfg["elevation_amp"] * math.sin(cu * 0.23 + 0.4)

    # Blender is Z-up: start on -Y side looking toward +Y / origin, orbiting smoothly outward
    cos_phi = math.cos(phi)
    dir_vec = Vector((
        cos_phi * math.sin(theta),
        -cos_phi * math.cos(theta),
        math.sin(phi),
    ))
    base_pos = dir_vec * R

    # Gentle organic handheld-style drift scaled slightly with radius
    amp = cam_cfg.get("handheld_pos_amp", 0.18) * (1.0 + 0.015 * R)
    drift = Vector((
        amp * (0.65 * math.sin(cu * 1.15) + 0.35 * math.cos(cu * 2.1)),
        amp * (0.55 * math.cos(cu * 0.92) + 0.45 * math.sin(cu * 1.75)),
        amp * 0.75 * math.sin(cu * 1.35 + 1.1),
    ))
    pos = base_pos + drift

    # Orbital tangent forward vector in XY plane
    tan_vec = Vector((math.cos(theta), math.sin(theta), 0.0))

    # Stage 1: look dead center into Planck core (0,0,0)
    # Stages 2-5: look smoothly inward/tangentially through the active concentric shell
    # Stage 6: sweep gently tangentially through the cooling rippled plasma
    mid_bias = smoothstep(2.0, 5.5, cu) * (1.0 - smoothstep(14.5, 17.5, cu))
    late_sweep = smoothstep(15.5, 19.2, cu)

    radial_anchor = lerp(0.0, 0.25 * R, mid_bias) + lerp(0.0, 0.58 * R, late_sweep)
    tangent_shift = lerp(0.0, 4.5, mid_bias) + lerp(0.0, 18.0, late_sweep)
    vert_shift = lerp(0.0, 1.3 * math.sin(cu * 0.35), mid_bias + late_sweep)

    target = dir_vec * radial_anchor + tan_vec * tangent_shift + Vector((0.0, 0.0, vert_shift))
    target += drift * 0.35

    focus_dist = clamp(
        lerp(9.0, 18.0, smoothstep(0.0, 14.0, cu)) + lerp(0.0, 12.0, late_sweep),
        6.0,
        36.0,
    )
    roll_rad = math.radians(cam_cfg.get("handheld_roll_deg", 1.1) * math.sin(cu * 0.62 + 0.3))
    return pos, target, focus_dist, roll_rad


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ensure_collection(name, parent=None):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    if parent is None:
        bpy.context.scene.collection.children.link(col)
    else:
        parent.children.link(col)
    return col


def link_to_collection(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def get_action_fcurves(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return []
    act = obj.animation_data.action
    slot = obj.animation_data.action_slot
    if not act.layers:
        return []
    strip = act.layers[0].strips[0]
    cb = strip.channelbag(slot)
    return list(cb.fcurves) if cb else []


def set_fcurve_interpolation(obj, interp="BEZIER"):
    for fc in get_action_fcurves(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def keyframe_socket_weights(node_socket, frames_and_vals, interp="BEZIER"):
    for frame, val in frames_and_vals:
        node_socket.default_value = val
        node_socket.keyframe_insert("default_value", frame=frame)


def setup_color_management(scene, cfg):
    cm = cfg["color_management"]
    scene.view_settings.view_transform = cm["view_transform"]
    scene.view_settings.look = cm["look"]
    scene.view_settings.exposure = cm.get("exposure", 0.0)


def apply_render_profile(scene, cfg, profile_name):
    prof = cfg["render_profiles"][profile_name]
    vol_cfg = cfg["volumetrics"]

    scene.render.resolution_x = prof["width"]
    scene.render.resolution_y = prof["height"]
    scene.render.resolution_percentage = 100
    scene.render.fps = cfg["timeline"]["fps"]
    scene.render.engine = prof["engine"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"

    if prof["engine"] == "BLENDER_EEVEE":
        ee = scene.eevee
        ee.taa_render_samples = prof["samples"]
        ee.use_raytracing = prof.get("use_raytracing", False)
        ee.use_volume_custom_range = True
        ee.volumetric_start = vol_cfg["start"]
        ee.volumetric_end = vol_cfg["end"]
        ee.volumetric_sample_distribution = vol_cfg["distribution"]
        ee.volumetric_tile_size = str(prof["volumetric_tile_size"])
        ee.volumetric_samples = prof["volumetric_samples"]
        ee.volumetric_ray_depth = vol_cfg["ray_depth"]
        ee.use_volumetric_shadows = vol_cfg["use_shadows"]
        ee.volumetric_shadow_samples = prof.get("volumetric_shadow_samples", vol_cfg["shadow_samples"])
    elif prof["engine"] == "CYCLES":
        cp = bpy.context.preferences.addons["cycles"].preferences
        cp.compute_device_type = "METAL"
        cp.get_devices()
        for d in cp.devices:
            d.use = d.type == "METAL"
        scene.cycles.device = "GPU"
        scene.cycles.samples = prof["samples"]
        scene.cycles.use_denoising = prof.get("use_denoising", True)
        scene.cycles.volume_step_rate = prof.get("volume_step_rate", 1.0)
        scene.cycles.volume_max_steps = prof.get("volume_max_steps", 256)
        scene.cycles.max_bounces = 8
        scene.cycles.volume_bounces = prof.get("volume_bounces", 1)


def setup_world_volume(scene, cfg, mode="scaffold"):
    world = bpy.data.worlds.new("BigBang_World")
    scene.world = world
    nt = world.node_tree
    nt.nodes.clear()

    n_out = nt.nodes.new("ShaderNodeOutputWorld")
    n_out.location = (600, 0)

    n_bg = nt.nodes.new("ShaderNodeBackground")
    n_bg.location = (320, 160)

    n_pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    n_pv.location = (320, -100)

    if mode == "scaffold":
        sg = cfg["scaffold_greys"]
        bg_col = (*sg["world_color"], 1.0)
        n_bg.inputs["Color"].default_value = bg_col
        n_bg.inputs["Strength"].default_value = 0.14

        # Subtle neutral grey 4D noise modulating world volume so backdrop is smoky opaque, never flat white or black
        n_texcoord = nt.nodes.new("ShaderNodeTexCoord")
        n_texcoord.location = (-480, -100)
        n_noise = nt.nodes.new("ShaderNodeTexNoise")
        n_noise.location = (-240, -100)
        n_noise.noise_dimensions = "4D"
        n_noise.inputs["Scale"].default_value = 0.045
        n_noise.inputs["Detail"].default_value = 4.0
        n_noise.inputs["Roughness"].default_value = 0.58
        n_noise.inputs["W"].default_value = 0.0
        n_noise.inputs["W"].keyframe_insert("default_value", frame=cfg["timeline"]["frame_start"])
        n_noise.inputs["W"].default_value = 1.6
        n_noise.inputs["W"].keyframe_insert("default_value", frame=cfg["timeline"]["frame_end"])

        n_ramp = nt.nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (20, -100)
        n_ramp.color_ramp.elements[0].position = 0.25
        n_ramp.color_ramp.elements[0].color = (0.14, 0.14, 0.16, 1.0)
        n_ramp.color_ramp.elements[1].position = 0.78
        n_ramp.color_ramp.elements[1].color = (0.34, 0.34, 0.38, 1.0)

        nt.links.new(n_texcoord.outputs["Object"], n_noise.inputs["Vector"])
        nt.links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])
        nt.links.new(n_ramp.outputs["Color"], n_pv.inputs["Emission Color"])
        nt.links.new(n_ramp.outputs["Color"], n_pv.inputs["Color"])

        n_pv.inputs["Density"].default_value = sg["world_density"]
        n_pv.inputs["Emission Strength"].default_value = sg["world_emission"]
        n_pv.inputs["Anisotropy"].default_value = 0.25
    else:
        # Fast opaque primordial plasma world using single 4D Noise (rich dark saturated contrast, zero 81-cell Voronoi lag)
        n_texcoord = nt.nodes.new("ShaderNodeTexCoord")
        n_texcoord.location = (-740, -100)

        n_noise = nt.nodes.new("ShaderNodeTexNoise")
        n_noise.location = (-480, -80)
        n_noise.noise_dimensions = "4D"
        n_noise.inputs["Scale"].default_value = 0.038
        n_noise.inputs["Detail"].default_value = 3.0
        n_noise.inputs["Roughness"].default_value = 0.58
        n_noise.inputs["Distortion"].default_value = 0.35

        f_start = cfg["timeline"]["frame_start"]
        f_end = cfg["timeline"]["frame_end"]
        n_noise.inputs["W"].default_value = 0.0
        n_noise.inputs["W"].keyframe_insert("default_value", frame=f_start)
        n_noise.inputs["W"].default_value = 1.6
        n_noise.inputs["W"].keyframe_insert("default_value", frame=f_end)

        n_col_a = nt.nodes.new("ShaderNodeRGB")
        n_col_a.location = (-220, 160)
        n_col_b = nt.nodes.new("ShaderNodeRGB")
        n_col_b.location = (-220, -20)

        n_col_mix = nt.nodes.new("ShaderNodeMix")
        n_col_mix.location = (60, 40)
        n_col_mix.data_type = "RGBA"
        n_col_mix.clamp_factor = True

        n_dens_mul = nt.nodes.new("ShaderNodeMath")
        n_dens_mul.location = (60, -180)
        n_dens_mul.operation = "MULTIPLY"

        n_em_mul = nt.nodes.new("ShaderNodeMath")
        n_em_mul.location = (60, -320)
        n_em_mul.operation = "MULTIPLY"

        n_pv.inputs["Anisotropy"].default_value = 0.48

        # Deep saturated plasma backdrops so emissive structures pop cleanly under AgX
        epoch_keys = [
            (1,   (0.015, 0.06, 0.36), (0.06, 0.22, 0.72), 0.012, 0.0055, (0.015, 0.05, 0.26), 0.06),
            (48,  (0.012, 0.05, 0.30), (0.05, 0.18, 0.62), 0.011, 0.0050, (0.012, 0.04, 0.22), 0.05),
            (97,  (0.010, 0.03, 0.22), (0.04, 0.12, 0.46), 0.010, 0.0045, (0.010, 0.03, 0.16), 0.05),
            (145, (0.060, 0.01, 0.12), (0.20, 0.03, 0.08), 0.012, 0.0052, (0.050, 0.01, 0.09), 0.05),
            (205, (0.080, 0.01, 0.08), (0.28, 0.04, 0.02), 0.013, 0.0058, (0.070, 0.01, 0.04), 0.06),
            (265, (0.140, 0.03, 0.01), (0.36, 0.09, 0.015), 0.011, 0.0055, (0.100, 0.025, 0.01), 0.06),
            (303, (0.150, 0.035, 0.01), (0.38, 0.10, 0.018), 0.011, 0.0052, (0.110, 0.03, 0.01), 0.06),
            (345, (0.180, 0.05, 0.01), (0.44, 0.14, 0.022), 0.010, 0.0052, (0.130, 0.04, 0.01), 0.06),
            (385, (0.160, 0.04, 0.01), (0.40, 0.12, 0.020), 0.010, 0.0048, (0.120, 0.035, 0.01), 0.06),
            (480, (0.140, 0.032, 0.008), (0.36, 0.10, 0.018), 0.010, 0.0045, (0.100, 0.028, 0.008), 0.05),
        ]
        for f, ca, cb, dens, em, bgc, bgs in epoch_keys:
            n_col_a.outputs[0].default_value = (*ca, 1.0)
            n_col_a.outputs[0].keyframe_insert("default_value", frame=f)
            n_col_b.outputs[0].default_value = (*cb, 1.0)
            n_col_b.outputs[0].keyframe_insert("default_value", frame=f)
            n_dens_mul.inputs[1].default_value = dens
            n_dens_mul.inputs[1].keyframe_insert("default_value", frame=f)
            n_em_mul.inputs[1].default_value = em
            n_em_mul.inputs[1].keyframe_insert("default_value", frame=f)
            n_bg.inputs["Color"].default_value = (*bgc, 1.0)
            n_bg.inputs["Color"].keyframe_insert("default_value", frame=f)
            n_bg.inputs["Strength"].default_value = bgs
            n_bg.inputs["Strength"].keyframe_insert("default_value", frame=f)

        set_fcurve_interpolation_data(nt, "BEZIER")

        nt.links.new(n_texcoord.outputs["Object"], n_noise.inputs["Vector"])
        nt.links.new(n_noise.outputs["Fac"], n_col_mix.inputs["Factor"])
        nt.links.new(n_col_a.outputs[0], n_col_mix.inputs["A"])
        nt.links.new(n_col_b.outputs[0], n_col_mix.inputs["B"])
        nt.links.new(n_col_mix.outputs["Result"], n_pv.inputs["Color"])
        nt.links.new(n_col_mix.outputs["Result"], n_pv.inputs["Emission Color"])
        nt.links.new(n_noise.outputs["Fac"], n_dens_mul.inputs[0])
        nt.links.new(n_dens_mul.outputs["Value"], n_pv.inputs["Density"])
        nt.links.new(n_noise.outputs["Fac"], n_em_mul.inputs[0])
        nt.links.new(n_em_mul.outputs["Value"], n_pv.inputs["Emission Strength"])

    nt.links.new(n_bg.outputs["Background"], n_out.inputs["Surface"])
    nt.links.new(n_pv.outputs["Volume"], n_out.inputs["Volume"])
    return world


def build_volumetric_lights(scene, cfg, mode="scaffold"):
    if mode == "scaffold":
        return None
    col = ensure_collection("Volumetric_Lights")
    energies = cfg["full_look"]["core_light_energy_w"]

    light_data = bpy.data.lights.new("Core_Volumetric_Light", type="POINT")
    light_data.shadow_soft_size = 2.8
    light_data.use_shadow = True
    light_obj = bpy.data.objects.new("Core_Volumetric_Light", light_data)
    light_obj.location = (0.0, 0.0, 0.0)
    link_to_collection(light_obj, col)

    light_keys = [
        (1,   (0.75, 0.88, 1.00), energies["planck"]),
        (48,  (0.62, 0.84, 1.00), energies["planck"] * 0.85),
        (97,  (0.38, 0.78, 1.00), energies["inflation"]),
        (145, (0.92, 0.36, 0.55), energies["qgp"] * 0.85),
        (205, (1.00, 0.42, 0.14), energies["qgp"]),
        (265, (1.00, 0.54, 0.18), energies["hadrons"]),
        (337, (1.00, 0.68, 0.24), energies["matter"] * 0.85),
        (359, (1.00, 0.82, 0.42), energies["matter"]),
        (385, (1.00, 0.48, 0.16), energies["neutrinos"]),
        (480, (0.95, 0.38, 0.12), energies["neutrinos"]),
    ]
    for f, col_rgb, en in light_keys:
        light_data.color = col_rgb
        light_data.keyframe_insert("color", frame=f)
        light_data.energy = en
        light_data.keyframe_insert("energy", frame=f)
    set_fcurve_interpolation_data(light_data, "BEZIER")
    return light_obj


def setup_compositor(scene, cfg, mode="scaffold"):
    comp_cfg = cfg["compositor"]
    scene.compositor_effects.clear()

    ng = bpy.data.node_groups.new("BigBang_Compositor", "CompositorNodeTree")
    ng.interface.new_socket(name="Image", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")

    n_in = ng.nodes.new("NodeGroupInput")
    n_in.location = (-600, 0)
    n_out = ng.nodes.new("NodeGroupOutput")
    n_out.location = (650, 0)

    # 1. Bloom Glare
    n_glare = ng.nodes.new("CompositorNodeGlare")
    n_glare.location = (-360, 0)
    n_glare.inputs["Type"].default_value = "Bloom"
    n_glare.inputs["Quality"].default_value = "High"
    n_glare.inputs["Threshold"].default_value = comp_cfg["bloom_threshold"]
    n_glare.inputs["Size"].default_value = comp_cfg["bloom_size"]
    if mode == "scaffold":
        n_glare.inputs["Strength"].default_value = 0.28
        n_glare.inputs["Saturation"].default_value = 0.0
    else:
        n_glare.inputs["Saturation"].default_value = 1.0
        for f, val in (
            (1, 0.52),
            (48, 0.48),
            (97, 0.45),
            (205, 0.46),
            (303, 0.46),
            (359, 0.58),
            (409, 0.34),
            (480, 0.25),
        ):
            n_glare.inputs["Strength"].default_value = val
            n_glare.inputs["Strength"].keyframe_insert("default_value", frame=f)

    # 1b. Subtle Optical Glare Streaks on hottest core & annihilation flashes (full mode only)
    if mode != "scaffold":
        n_streaks = ng.nodes.new("CompositorNodeGlare")
        n_streaks.location = (-160, 0)
        n_streaks.inputs["Type"].default_value = "Streaks"
        n_streaks.inputs["Quality"].default_value = "High"
        n_streaks.inputs["Threshold"].default_value = comp_cfg.get("streaks_threshold", 3.4)
        n_streaks.inputs["Strength"].default_value = comp_cfg.get("streaks_strength", 0.16)
        n_streaks.inputs["Streaks"].default_value = 4
        n_streaks.inputs["Fade"].default_value = 0.86

    # 2. Subtle Lens Distortion & Chromatic Aberration
    n_lens = ng.nodes.new("CompositorNodeLensdist")
    n_lens.location = (60, 0)
    n_lens.inputs["Type"].default_value = "Radial"
    n_lens.inputs["Distortion"].default_value = -0.010 if mode == "scaffold" else comp_cfg["lens_distortion"]
    n_lens.inputs["Dispersion"].default_value = 0.0 if mode == "scaffold" else comp_cfg["lens_dispersion"]
    n_lens.inputs["Fit"].default_value = True

    # 3. Subtle animated 4D film grain using ShaderNodeTexWhiteNoise + ShaderNodeMix
    n_coords = ng.nodes.new("CompositorNodeImageCoordinates")
    n_coords.location = (-300, -280)

    n_noise = ng.nodes.new("ShaderNodeTexWhiteNoise")
    n_noise.location = (-40, -280)
    n_noise.noise_dimensions = "4D"
    n_noise.inputs["W"].default_value = 0.0
    n_noise.inputs["W"].keyframe_insert("default_value", frame=cfg["timeline"]["frame_start"])
    n_noise.inputs["W"].default_value = 48.0
    n_noise.inputs["W"].keyframe_insert("default_value", frame=cfg["timeline"]["frame_end"])

    n_grain_mix = ng.nodes.new("ShaderNodeMix")
    n_grain_mix.location = (320, 0)
    n_grain_mix.data_type = "RGBA"
    n_grain_mix.blend_type = "OVERLAY"
    n_grain_mix.inputs["Factor"].default_value = 0.012 if mode == "scaffold" else comp_cfg["grain_strength"]

    set_fcurve_interpolation_data(ng, "BEZIER")

    ng.links.new(n_in.outputs["Image"], n_glare.inputs["Image"])
    if mode != "scaffold":
        ng.links.new(n_glare.outputs["Image"], n_streaks.inputs["Image"])
        ng.links.new(n_streaks.outputs["Image"], n_lens.inputs["Image"])
    else:
        ng.links.new(n_glare.outputs["Image"], n_lens.inputs["Image"])
    ng.links.new(n_coords.outputs["Pixel"], n_noise.inputs["Vector"])
    ng.links.new(n_lens.outputs["Image"], n_grain_mix.inputs["A"])
    ng.links.new(n_noise.outputs["Color"], n_grain_mix.inputs["B"])
    ng.links.new(n_grain_mix.outputs["Result"], n_out.inputs["Image"])

    eff = scene.compositor_effects.new("Cinematic_Post")
    eff.node_group = ng
    eff.enable_for_render = True
    eff.enable_for_preview = True
    return eff


def build_camera_rig(scene, cfg):
    col = ensure_collection("Camera_Rig")
    cam_cfg = cfg["camera"]
    f_start = cfg["timeline"]["frame_start"]
    f_end = cfg["timeline"]["frame_end"]
    step = cam_cfg.get("keyframe_step", 4)

    target_empty = bpy.data.objects.new("Cam_Target", None)
    target_empty.empty_display_type = "PLAIN_AXES"
    target_empty.empty_display_size = 1.5
    link_to_collection(target_empty, col)

    cam_data = bpy.data.cameras.new("MainCamera")
    cam_data.lens = cam_cfg["lens_mm"]
    cam_data.sensor_width = cam_cfg["sensor_width_mm"]
    cam_data.clip_start = cam_cfg["clip_start"]
    cam_data.clip_end = cam_cfg["clip_end"]
    cam_data.dof.use_dof = cam_cfg.get("dof_enabled", True)
    cam_data.dof.aperture_fstop = cam_cfg.get("aperture_fstop", 2.4)

    cam_obj = bpy.data.objects.new("MainCamera", cam_data)
    link_to_collection(cam_obj, col)
    scene.camera = cam_obj

    track = cam_obj.constraints.new("TRACK_TO")
    track.target = target_empty
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    # Subtle roll object parented? TrackTo locks roll around Z, so use DAMPED_TRACK or keyframe camera delta rotation?
    # Better: keyframe TrackTo influence or apply subtle roll via Camera shift_y / lens breathing;
    # actually a tiny child camera under Cam_Carrier or TrackTo -> Cam_Target keeps Up=Z rock solid,
    # and we can keyframe target Z wobble cleanly. Let's sample keyframes at every `step` frames + exact stage boundaries.
    sample_frames = set(range(f_start, f_end + 1, step))
    sample_frames.add(f_end)
    for st in cfg["stages"]:
        sample_frames.add(st["start_frame"])
        sample_frames.add(st["end_frame"])

    for f in sorted(sample_frames):
        u = frame_to_seconds(f, cfg)
        pos, tgt, focus_dist, roll_rad = get_camera_pose(u, cfg)

        cam_obj.location = pos
        cam_obj.keyframe_insert("location", frame=f)

        # Tiny organic roll offset encoded in target lateral tilt via TrackTo? Keep level horizon cleanly
        # while handheld drift comes from organic 3-axis positional & target micro-motion.
        target_empty.location = tgt + Vector((0.0, 0.0, 0.12 * math.sin(roll_rad * 4.0)))
        target_empty.keyframe_insert("location", frame=f)

        cam_data.dof.focus_distance = focus_dist
        cam_data.dof.keyframe_insert("focus_distance", frame=f)

    set_fcurve_interpolation(cam_obj, "BEZIER")
    set_fcurve_interpolation(target_empty, "BEZIER")
    set_fcurve_interpolation(cam_data, "BEZIER")
    return cam_obj, target_empty


def add_timeline_markers(scene, cfg):
    scene.timeline_markers.clear()
    for st in cfg["stages"]:
        m = scene.timeline_markers.new(f"S{st['index'] + 1}_{st['id'].upper()}", frame=st["start_frame"])
        m.frame = st["start_frame"]
    m_end = scene.timeline_markers.new("END", frame=cfg["timeline"]["frame_end"])
    m_end.frame = cfg["timeline"]["frame_end"]


def stitch_contact_sheet(image_paths, out_path, cols=3, rows=2, pad=14, target_cell_w=960):
    loaded = []
    for p in image_paths:
        img = bpy.data.images.load(p, check_existing=False)
        w, h = img.size[0], img.size[1]
        if target_cell_w and w > target_cell_w:
            scale_h = max(1, int(round(h * (target_cell_w / float(w)))))
            img.scale(target_cell_w, scale_h)
            w, h = target_cell_w, scale_h
        arr = np.array(img.pixels[:], dtype=np.float32).reshape((h, w, 4))
        loaded.append(arr)
        bpy.data.images.remove(img)

    cell_h, cell_w = loaded[0].shape[0], loaded[0].shape[1]
    sheet_w = cols * cell_w + (cols + 1) * pad
    sheet_h = rows * cell_h + (rows + 1) * pad
    sheet = np.zeros((sheet_h, sheet_w, 4), dtype=np.float32)
    sheet[:, :, 0:3] = 0.04
    sheet[:, :, 3] = 1.0

    for idx, arr in enumerate(loaded):
        r = idx // cols
        c = idx % cols
        # Blender image pixels are bottom-up (row 0 = bottom of image), so top visual row = (rows - 1 - r)
        y0 = (rows - 1 - r) * (cell_h + pad) + pad
        x0 = c * (cell_w + pad) + pad
        sheet[y0:y0 + cell_h, x0:x0 + cell_w, :] = arr

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_img = bpy.data.images.new("ContactSheet", width=sheet_w, height=sheet_h, alpha=True)
    out_img.pixels.foreach_set(sheet.ravel())
    out_img.filepath_raw = out_path
    out_img.file_format = "PNG"
    out_img.save()
    bpy.data.images.remove(out_img)
    return out_path


def alpha_over_png(base_png_path, overlay_png_path, out_png_path):
    base_img = bpy.data.images.load(base_png_path, check_existing=False)
    ov_img = bpy.data.images.load(overlay_png_path, check_existing=False)

    w, h = base_img.size[0], base_img.size[1]
    base = np.array(base_img.pixels[:], dtype=np.float32).reshape((h, w, 4))
    ov = np.array(ov_img.pixels[:], dtype=np.float32).reshape((h, w, 4))

    bpy.data.images.remove(base_img)
    bpy.data.images.remove(ov_img)

    # Blender PNGs from EEVEE are straight RGBA; alpha-over composite in sRGB-display domain
    a = ov[:, :, 3:4]
    out = np.empty_like(base)
    out[:, :, :3] = base[:, :, :3] * (1.0 - a) + ov[:, :, :3] * a
    out[:, :, 3:4] = np.clip(base[:, :, 3:4] + a * (1.0 - base[:, :, 3:4]), 0.0, 1.0)

    os.makedirs(os.path.dirname(out_png_path), exist_ok=True)
    out_img = bpy.data.images.new("CompOut", width=w, height=h, alpha=True)
    out_img.pixels.foreach_set(out.ravel())
    out_img.filepath_raw = out_png_path
    out_img.file_format = "PNG"
    out_img.save()
    bpy.data.images.remove(out_img)


def make_emissive_material(
    name,
    color_rgb=(0.8, 0.8, 0.8),
    strength=1.5,
    keyframed_strengths=None,
    alpha_weights=None,
    attr_name=None,
    attr_ramp=None,
    attr_type="GEOMETRY",
    alpha_attr_name=None,
    alpha_attr_power=1.0,
):
    mat = bpy.data.materials.new(name)
    mat.surface_render_method = "BLENDED"
    nt = mat.node_tree
    nt.nodes.clear()
    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
    n_mix = nt.nodes.new("ShaderNodeMixShader")
    n_trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    n_em = nt.nodes.new("ShaderNodeEmission")
    n_em.inputs["Color"].default_value = (*color_rgb, 1.0)
    n_em.inputs["Strength"].default_value = strength
    n_mix.inputs["Fac"].default_value = 1.0

    if attr_name and attr_ramp:
        n_attr = nt.nodes.new("ShaderNodeAttribute")
        n_attr.attribute_type = attr_type
        n_attr.attribute_name = attr_name
        n_ramp = nt.nodes.new("ShaderNodeValToRGB")
        cr = n_ramp.color_ramp
        cr.interpolation = "LINEAR"
        cr.elements[0].position = attr_ramp[0][0]
        cr.elements[0].color = (*attr_ramp[0][1], 1.0)
        cr.elements[1].position = attr_ramp[-1][0]
        cr.elements[1].color = (*attr_ramp[-1][1], 1.0)
        for pos, col_rgb in attr_ramp[1:-1]:
            el = cr.elements.new(pos)
            el.color = (*col_rgb, 1.0)
        nt.links.new(n_attr.outputs["Fac"], n_ramp.inputs["Fac"])
        nt.links.new(n_ramp.outputs["Color"], n_em.inputs["Color"])

    n_alpha_gate = nt.nodes.new("ShaderNodeValue")
    n_alpha_gate.outputs[0].default_value = 1.0

    if alpha_attr_name:
        n_aattr = nt.nodes.new("ShaderNodeAttribute")
        n_aattr.attribute_type = attr_type
        n_aattr.attribute_name = alpha_attr_name
        n_apow = nt.nodes.new("ShaderNodeMath")
        n_apow.operation = "POWER"
        n_apow.use_clamp = True
        n_apow.inputs[1].default_value = alpha_attr_power
        n_amul = nt.nodes.new("ShaderNodeMath")
        n_amul.operation = "MULTIPLY"
        n_amul.use_clamp = True
        nt.links.new(n_aattr.outputs["Fac"], n_apow.inputs[0])
        nt.links.new(n_apow.outputs["Value"], n_amul.inputs[0])
        nt.links.new(n_alpha_gate.outputs[0], n_amul.inputs[1])
        nt.links.new(n_amul.outputs["Value"], n_mix.inputs["Fac"])
    else:
        nt.links.new(n_alpha_gate.outputs[0], n_mix.inputs["Fac"])

    nt.links.new(n_trans.outputs["BSDF"], n_mix.inputs[1])
    nt.links.new(n_em.outputs["Emission"], n_mix.inputs[2])
    nt.links.new(n_mix.outputs["Shader"], n_out.inputs["Surface"])

    if keyframed_strengths:
        for frame, val in keyframed_strengths:
            n_em.inputs["Strength"].default_value = val
            n_em.inputs["Strength"].keyframe_insert("default_value", frame=frame)
    if alpha_weights:
        for frame, val in alpha_weights:
            n_alpha_gate.outputs[0].default_value = val
            n_alpha_gate.outputs[0].keyframe_insert("default_value", frame=frame)
    if keyframed_strengths or alpha_weights:
        set_fcurve_interpolation_data(nt, "BEZIER")
    return mat

def set_fcurve_interpolation_data(data_block, interp="BEZIER"):
    if not data_block.animation_data or not data_block.animation_data.action:
        return
    act = data_block.animation_data.action
    slot = data_block.animation_data.action_slot
    if not act.layers:
        return
    cb = act.layers[0].strips[0].channelbag(slot)
    if not cb:
        return
    for fc in cb.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def make_shell_volume_material(
    name,
    inner_r,
    outer_r,
    feather=2.5,
    base_color=(0.5, 0.5, 0.5),
    hot_color=(0.85, 0.85, 0.85),
    noise_scale=0.14,
    noise_detail=4.0,
    noise_distortion=0.6,
    noise_speed=1.4,
    anisotropy=0.25,
    density_keyframes=None,
    emission_keyframes=None,
    cfg=None,
):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()

    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (820, 0)

    n_pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    n_pv.location = (540, 0)
    n_pv.inputs["Anisotropy"].default_value = anisotropy
    n_pv.inputs["Color"].default_value = (*base_color, 1.0)

    n_tc = nt.nodes.new("ShaderNodeTexCoord")
    n_tc.location = (-720, 0)

    # Radial shell envelope in world meters (mesh radius == outer_r + feather, scale == 1)
    n_len = nt.nodes.new("ShaderNodeVectorMath")
    n_len.location = (-480, 220)
    n_len.operation = "LENGTH"
    nt.links.new(n_tc.outputs["Object"], n_len.inputs[0])

    n_outer_map = nt.nodes.new("ShaderNodeMapRange")
    n_outer_map.location = (-240, 140)
    n_outer_map.inputs["From Min"].default_value = max(0.0, outer_r - feather)
    n_outer_map.inputs["From Max"].default_value = outer_r + feather * 0.5
    n_outer_map.inputs["To Min"].default_value = 1.0
    n_outer_map.inputs["To Max"].default_value = 0.0
    nt.links.new(n_len.outputs["Value"], n_outer_map.inputs["Value"])

    if inner_r > 0.01:
        n_inner_map = nt.nodes.new("ShaderNodeMapRange")
        n_inner_map.location = (-240, 340)
        n_inner_map.inputs["From Min"].default_value = max(0.0, inner_r - feather)
        n_inner_map.inputs["From Max"].default_value = inner_r + feather
        n_inner_map.inputs["To Min"].default_value = 0.0
        n_inner_map.inputs["To Max"].default_value = 1.0
        nt.links.new(n_len.outputs["Value"], n_inner_map.inputs["Value"])

        n_shell_mask = nt.nodes.new("ShaderNodeMath")
        n_shell_mask.location = (-20, 240)
        n_shell_mask.operation = "MULTIPLY"
        nt.links.new(n_inner_map.outputs["Result"], n_shell_mask.inputs[0])
        nt.links.new(n_outer_map.outputs["Result"], n_shell_mask.inputs[1])
        mask_socket = n_shell_mask.outputs["Value"]
    else:
        mask_socket = n_outer_map.outputs["Result"]

    # Animated 4D noise
    n_noise = nt.nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-480, -140)
    n_noise.noise_dimensions = "4D"
    n_noise.inputs["Scale"].default_value = noise_scale
    n_noise.inputs["Detail"].default_value = noise_detail
    n_noise.inputs["Roughness"].default_value = 0.58
    n_noise.inputs["Distortion"].default_value = noise_distortion
    f_start = cfg["timeline"]["frame_start"] if cfg else 1
    f_end = cfg["timeline"]["frame_end"] if cfg else 480
    n_noise.inputs["W"].default_value = 0.0
    n_noise.inputs["W"].keyframe_insert("default_value", frame=f_start)
    n_noise.inputs["W"].default_value = noise_speed
    n_noise.inputs["W"].keyframe_insert("default_value", frame=f_end)

    n_ramp = nt.nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-200, -160)
    n_ramp.color_ramp.elements[0].position = 0.28
    n_ramp.color_ramp.elements[0].color = (*base_color, 1.0)
    n_ramp.color_ramp.elements[1].position = 0.74
    n_ramp.color_ramp.elements[1].color = (*hot_color, 1.0)

    n_dens_remap = nt.nodes.new("ShaderNodeMapRange")
    n_dens_remap.location = (-200, 10)
    n_dens_remap.inputs["From Min"].default_value = 0.25
    n_dens_remap.inputs["From Max"].default_value = 0.78
    n_dens_remap.inputs["To Min"].default_value = 0.25
    n_dens_remap.inputs["To Max"].default_value = 1.25

    n_dens_mask = nt.nodes.new("ShaderNodeMath")
    n_dens_mask.location = (60, 110)
    n_dens_mask.operation = "MULTIPLY"

    n_dens_gain = nt.nodes.new("ShaderNodeValue")
    n_dens_gain.location = (60, 260)
    n_dens_gain.outputs[0].default_value = 0.05

    n_dens_final = nt.nodes.new("ShaderNodeMath")
    n_dens_final.location = (290, 140)
    n_dens_final.operation = "MULTIPLY"

    n_em_gain = nt.nodes.new("ShaderNodeValue")
    n_em_gain.location = (60, -280)
    n_em_gain.outputs[0].default_value = 0.5

    n_em_mask = nt.nodes.new("ShaderNodeMath")
    n_em_mask.location = (290, -120)
    n_em_mask.operation = "MULTIPLY"

    n_em_final = nt.nodes.new("ShaderNodeMath")
    n_em_final.location = (410, -180)
    n_em_final.operation = "MULTIPLY"

    nt.links.new(n_tc.outputs["Object"], n_noise.inputs["Vector"])
    nt.links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])
    nt.links.new(n_noise.outputs["Fac"], n_dens_remap.inputs["Value"])
    nt.links.new(n_ramp.outputs["Color"], n_pv.inputs["Color"])
    nt.links.new(n_ramp.outputs["Color"], n_pv.inputs["Emission Color"])

    nt.links.new(mask_socket, n_dens_mask.inputs[0])
    nt.links.new(n_dens_remap.outputs["Result"], n_dens_mask.inputs[1])
    nt.links.new(n_dens_mask.outputs["Value"], n_dens_final.inputs[0])
    nt.links.new(n_dens_gain.outputs[0], n_dens_final.inputs[1])
    nt.links.new(n_dens_final.outputs["Value"], n_pv.inputs["Density"])

    nt.links.new(mask_socket, n_em_mask.inputs[0])
    nt.links.new(n_dens_remap.outputs["Result"], n_em_mask.inputs[1])
    nt.links.new(n_em_mask.outputs["Value"], n_em_final.inputs[0])
    nt.links.new(n_em_gain.outputs[0], n_em_final.inputs[1])
    nt.links.new(n_em_final.outputs["Value"], n_pv.inputs["Emission Strength"])

    nt.links.new(n_pv.outputs["Volume"], n_out.inputs["Volume"])

    if density_keyframes:
        for f, val in density_keyframes:
            n_dens_gain.outputs[0].default_value = val
            n_dens_gain.outputs[0].keyframe_insert("default_value", frame=f)
    if emission_keyframes:
        for f, val in emission_keyframes:
            n_em_gain.outputs[0].default_value = val
            n_em_gain.outputs[0].keyframe_insert("default_value", frame=f)

    set_fcurve_interpolation_data(nt, "BEZIER")
    return mat


def make_rich_volume_material(
    name,
    inner_r,
    outer_r,
    feather=3.0,
    ramp_stops=None,
    noise_scale=0.14,
    noise_detail=4.0,
    noise_distortion=1.2,
    noise_speed=2.0,
    voronoi_scale=0.18,
    voronoi_mix=0.0,
    anisotropy=0.45,
    emission_power=1.35,
    dens_range=(0.22, 0.80),
    density_keyframes=None,
    emission_keyframes=None,
    cfg=None,
):
    if ramp_stops is None:
        ramp_stops = [
            (0.18, (0.12, 0.04, 0.02)),
            (0.45, (0.55, 0.16, 0.04)),
            (0.72, (0.95, 0.45, 0.12)),
            (0.92, (1.00, 0.86, 0.58)),
        ]

    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()

    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (960, 0)

    n_pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    n_pv.location = (660, 0)
    n_pv.inputs["Anisotropy"].default_value = anisotropy

    n_tc = nt.nodes.new("ShaderNodeTexCoord")
    n_tc.location = (-860, 0)

    # Radial shell mask in world units
    n_len = nt.nodes.new("ShaderNodeVectorMath")
    n_len.location = (-600, 260)
    n_len.operation = "LENGTH"
    nt.links.new(n_tc.outputs["Object"], n_len.inputs[0])

    n_outer = nt.nodes.new("ShaderNodeMapRange")
    n_outer.location = (-360, 180)
    n_outer.inputs["From Min"].default_value = max(0.0, outer_r - feather)
    n_outer.inputs["From Max"].default_value = outer_r + feather * 0.5
    n_outer.inputs["To Min"].default_value = 1.0
    n_outer.inputs["To Max"].default_value = 0.0
    nt.links.new(n_len.outputs["Value"], n_outer.inputs["Value"])

    if inner_r > 0.01:
        n_inner = nt.nodes.new("ShaderNodeMapRange")
        n_inner.location = (-360, 380)
        n_inner.inputs["From Min"].default_value = max(0.0, inner_r - feather)
        n_inner.inputs["From Max"].default_value = inner_r + feather
        n_inner.inputs["To Min"].default_value = 0.0
        n_inner.inputs["To Max"].default_value = 1.0
        nt.links.new(n_len.outputs["Value"], n_inner.inputs["Value"])

        n_shell = nt.nodes.new("ShaderNodeMath")
        n_shell.location = (-120, 280)
        n_shell.operation = "MULTIPLY"
        nt.links.new(n_inner.outputs["Result"], n_shell.inputs[0])
        nt.links.new(n_outer.outputs["Result"], n_shell.inputs[1])
        mask_socket = n_shell.outputs["Value"]
    else:
        mask_socket = n_outer.outputs["Result"]

    f_start = cfg["timeline"]["frame_start"] if cfg else 1
    f_end = cfg["timeline"]["frame_end"] if cfg else 480

    # Fast animated 4D Noise (optionally blended with fast 3D Voronoi F1 instead of 81-cell 4D SMOOTH_F1)
    n_noise = nt.nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-600, -40)
    n_noise.noise_dimensions = "4D"
    n_noise.inputs["Scale"].default_value = noise_scale
    n_noise.inputs["Detail"].default_value = noise_detail
    n_noise.inputs["Roughness"].default_value = 0.58
    n_noise.inputs["Distortion"].default_value = noise_distortion
    n_noise.inputs["W"].default_value = 0.0
    n_noise.inputs["W"].keyframe_insert("default_value", frame=f_start)
    n_noise.inputs["W"].default_value = noise_speed
    n_noise.inputs["W"].keyframe_insert("default_value", frame=f_end)
    nt.links.new(n_tc.outputs["Object"], n_noise.inputs["Vector"])

    if voronoi_mix > 0.01:
        n_vshift = nt.nodes.new("ShaderNodeCombineXYZ")
        n_vshift.location = (-860, -320)
        n_vshift.inputs["Z"].default_value = 0.0
        n_vshift.inputs["Z"].keyframe_insert("default_value", frame=f_start)
        n_vshift.inputs["Z"].default_value = noise_speed * 2.4
        n_vshift.inputs["Z"].keyframe_insert("default_value", frame=f_end)

        n_vadd = nt.nodes.new("ShaderNodeVectorMath")
        n_vadd.location = (-720, -320)
        n_vadd.operation = "ADD"
        nt.links.new(n_tc.outputs["Object"], n_vadd.inputs[0])
        nt.links.new(n_vshift.outputs["Vector"], n_vadd.inputs[1])

        n_vor = nt.nodes.new("ShaderNodeTexVoronoi")
        n_vor.location = (-560, -320)
        n_vor.voronoi_dimensions = "3D"
        n_vor.feature = "F1"
        n_vor.inputs["Scale"].default_value = voronoi_scale
        nt.links.new(n_vadd.outputs["Vector"], n_vor.inputs["Vector"])

        n_tex_mix = nt.nodes.new("ShaderNodeMix")
        n_tex_mix.location = (-320, -140)
        n_tex_mix.data_type = "FLOAT"
        n_tex_mix.inputs["Factor"].default_value = voronoi_mix
        nt.links.new(n_noise.outputs["Fac"], n_tex_mix.inputs["A"])
        nt.links.new(n_vor.outputs["Distance"], n_tex_mix.inputs["B"])
        tex_out = n_tex_mix.outputs["Result"]
    else:
        tex_out = n_noise.outputs["Fac"]

    # 4-stop temperature ramp
    n_ramp = nt.nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-60, -180)
    cr = n_ramp.color_ramp
    cr.elements[0].position = ramp_stops[0][0]
    cr.elements[0].color = (*ramp_stops[0][1], 1.0)
    cr.elements[1].position = ramp_stops[-1][0]
    cr.elements[1].color = (*ramp_stops[-1][1], 1.0)
    for pos, col_rgb in ramp_stops[1:-1]:
        el = cr.elements.new(pos)
        el.color = (*col_rgb, 1.0)

    n_dens_remap = nt.nodes.new("ShaderNodeMapRange")
    n_dens_remap.location = (-60, 40)
    n_dens_remap.inputs["From Min"].default_value = dens_range[0]
    n_dens_remap.inputs["From Max"].default_value = dens_range[1]
    n_dens_remap.inputs["To Min"].default_value = 0.14
    n_dens_remap.inputs["To Max"].default_value = 1.45

    n_em_pow = nt.nodes.new("ShaderNodeMath")
    n_em_pow.location = (-60, -400)
    n_em_pow.operation = "POWER"
    n_em_pow.inputs[1].default_value = emission_power

    n_dens_mask = nt.nodes.new("ShaderNodeMath")
    n_dens_mask.location = (180, 140)
    n_dens_mask.operation = "MULTIPLY"

    n_dens_gain = nt.nodes.new("ShaderNodeValue")
    n_dens_gain.location = (180, 300)
    n_dens_gain.outputs[0].default_value = 0.05

    n_dens_final = nt.nodes.new("ShaderNodeMath")
    n_dens_final.location = (400, 160)
    n_dens_final.operation = "MULTIPLY"

    n_em_mask = nt.nodes.new("ShaderNodeMath")
    n_em_mask.location = (180, -240)
    n_em_mask.operation = "MULTIPLY"

    n_em_gain = nt.nodes.new("ShaderNodeValue")
    n_em_gain.location = (180, -400)
    n_em_gain.outputs[0].default_value = 0.04

    n_em_final = nt.nodes.new("ShaderNodeMath")
    n_em_final.location = (400, -260)
    n_em_final.operation = "MULTIPLY"

    nt.links.new(tex_out, n_ramp.inputs["Fac"])
    nt.links.new(tex_out, n_dens_remap.inputs["Value"])
    nt.links.new(n_dens_remap.outputs["Result"], n_em_pow.inputs[0])

    nt.links.new(n_ramp.outputs["Color"], n_pv.inputs["Color"])
    nt.links.new(n_ramp.outputs["Color"], n_pv.inputs["Emission Color"])

    nt.links.new(mask_socket, n_dens_mask.inputs[0])
    nt.links.new(n_dens_remap.outputs["Result"], n_dens_mask.inputs[1])
    nt.links.new(n_dens_mask.outputs["Value"], n_dens_final.inputs[0])
    nt.links.new(n_dens_gain.outputs[0], n_dens_final.inputs[1])
    nt.links.new(n_dens_final.outputs["Value"], n_pv.inputs["Density"])

    nt.links.new(mask_socket, n_em_mask.inputs[0])
    nt.links.new(n_em_pow.outputs["Value"], n_em_mask.inputs[1])
    nt.links.new(n_em_mask.outputs["Value"], n_em_final.inputs[0])
    nt.links.new(n_em_gain.outputs[0], n_em_final.inputs[1])
    nt.links.new(n_em_final.outputs["Value"], n_pv.inputs["Emission Strength"])

    nt.links.new(n_pv.outputs["Volume"], n_out.inputs["Volume"])

    if density_keyframes:
        for f, val in density_keyframes:
            n_dens_gain.outputs[0].default_value = val
            n_dens_gain.outputs[0].keyframe_insert("default_value", frame=f)
    if emission_keyframes:
        for f, val in emission_keyframes:
            n_em_gain.outputs[0].default_value = val
            n_em_gain.outputs[0].keyframe_insert("default_value", frame=f)

    set_fcurve_interpolation_data(nt, "BEZIER")
    return mat


def make_plasma_orb_material(
    name,
    core_rgb=(1.0, 0.96, 0.90),
    edge_rgb=(1.0, 0.48, 0.12),
    strength=3.0,
    keyframed_strengths=None,
    alpha_weights=None,
    attr_name=None,
    attr_ramp=None,
    attr_type="GEOMETRY",
    power=2.2,
):
    mat = bpy.data.materials.new(name)
    mat.surface_render_method = "BLENDED"
    nt = mat.node_tree
    nt.nodes.clear()

    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (640, 0)
    n_mix_s = nt.nodes.new("ShaderNodeMixShader")
    n_mix_s.location = (420, 0)
    n_trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    n_trans.location = (180, 120)
    n_em = nt.nodes.new("ShaderNodeEmission")
    n_em.location = (180, -80)
    n_em.inputs["Strength"].default_value = strength

    # Facing goes 1.0 at center -> 0.0 at silhouette rim
    n_lw = nt.nodes.new("ShaderNodeLayerWeight")
    n_lw.location = (-560, 40)
    n_lw.inputs["Blend"].default_value = 0.5

    n_inv = nt.nodes.new("ShaderNodeMath")
    n_inv.location = (-360, 40)
    n_inv.operation = "SUBTRACT"
    n_inv.inputs[0].default_value = 1.0
    nt.links.new(n_lw.outputs["Facing"], n_inv.inputs[1])

    n_pow = nt.nodes.new("ShaderNodeMath")
    n_pow.location = (-160, 40)
    n_pow.operation = "POWER"
    n_pow.use_clamp = True
    n_pow.inputs[1].default_value = power
    nt.links.new(n_inv.outputs["Value"], n_pow.inputs[0])

    # Color mix between edge hue and hot center core
    n_cmix = nt.nodes.new("ShaderNodeMix")
    n_cmix.location = (-20, -180)
    n_cmix.data_type = "RGBA"
    n_cmix.inputs["B"].default_value = (*core_rgb, 1.0)

    if attr_name and attr_ramp:
        n_attr = nt.nodes.new("ShaderNodeAttribute")
        n_attr.location = (-560, -240)
        n_attr.attribute_type = attr_type
        n_attr.attribute_name = attr_name

        n_ramp = nt.nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (-320, -240)
        cr = n_ramp.color_ramp
        cr.interpolation = "LINEAR"
        cr.elements[0].position = attr_ramp[0][0]
        cr.elements[0].color = (*attr_ramp[0][1], 1.0)
        cr.elements[1].position = attr_ramp[-1][0]
        cr.elements[1].color = (*attr_ramp[-1][1], 1.0)
        for pos, col_rgb in attr_ramp[1:-1]:
            el = cr.elements.new(pos)
            el.color = (*col_rgb, 1.0)
        nt.links.new(n_attr.outputs["Fac"], n_ramp.inputs["Fac"])
        nt.links.new(n_ramp.outputs["Color"], n_cmix.inputs["A"])
    else:
        n_cmix.inputs["A"].default_value = (*edge_rgb, 1.0)

    nt.links.new(n_pow.outputs["Value"], n_cmix.inputs["Factor"])
    nt.links.new(n_cmix.outputs["Result"], n_em.inputs["Color"])

    # Alpha = Facing^power * stage_alpha_gate
    n_alpha_gate = nt.nodes.new("ShaderNodeValue")
    n_alpha_gate.location = (-160, 220)
    n_alpha_gate.outputs[0].default_value = 1.0

    n_alpha_mul = nt.nodes.new("ShaderNodeMath")
    n_alpha_mul.location = (120, 220)
    n_alpha_mul.operation = "MULTIPLY"
    n_alpha_mul.use_clamp = True

    nt.links.new(n_pow.outputs["Value"], n_alpha_mul.inputs[0])
    nt.links.new(n_alpha_gate.outputs[0], n_alpha_mul.inputs[1])
    nt.links.new(n_alpha_mul.outputs["Value"], n_mix_s.inputs["Fac"])

    nt.links.new(n_trans.outputs["BSDF"], n_mix_s.inputs[1])
    nt.links.new(n_em.outputs["Emission"], n_mix_s.inputs[2])
    nt.links.new(n_mix_s.outputs["Shader"], n_out.inputs["Surface"])

    if keyframed_strengths:
        for f, val in keyframed_strengths:
            n_em.inputs["Strength"].default_value = val
            n_em.inputs["Strength"].keyframe_insert("default_value", frame=f)
    if alpha_weights:
        for f, val in alpha_weights:
            n_alpha_gate.outputs[0].default_value = val
            n_alpha_gate.outputs[0].keyframe_insert("default_value", frame=f)
    if keyframed_strengths or alpha_weights:
        set_fcurve_interpolation_data(nt, "BEZIER")
    return mat


def make_shockwave_shell_material(name, color_rgb=(1.0, 0.72, 0.25), strength=4.5, alpha_weights=None):
    mat = bpy.data.materials.new(name)
    mat.surface_render_method = "BLENDED"
    nt = mat.node_tree
    nt.nodes.clear()

    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
    n_mix_s = nt.nodes.new("ShaderNodeMixShader")
    n_trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    n_em = nt.nodes.new("ShaderNodeEmission")
    n_em.inputs["Color"].default_value = (*color_rgb, 1.0)
    n_em.inputs["Strength"].default_value = strength

    # Asymmetric bell curve in Facing: peaks around r/R=0.62 and vanishes cleanly well before the silhouette edge
    n_lw = nt.nodes.new("ShaderNodeLayerWeight")
    n_lw.inputs["Blend"].default_value = 0.5

    n_inv = nt.nodes.new("ShaderNodeMath")
    n_inv.operation = "SUBTRACT"
    n_inv.inputs[0].default_value = 1.0

    n_inv_pow = nt.nodes.new("ShaderNodeMath")
    n_inv_pow.operation = "POWER"
    n_inv_pow.use_clamp = True
    n_inv_pow.inputs[1].default_value = 3.5

    n_bell = nt.nodes.new("ShaderNodeMath")
    n_bell.operation = "MULTIPLY"

    n_bell_gain = nt.nodes.new("ShaderNodeMath")
    n_bell_gain.operation = "MULTIPLY"
    n_bell_gain.use_clamp = True
    n_bell_gain.inputs[1].default_value = 10.8

    n_pow = nt.nodes.new("ShaderNodeMath")
    n_pow.operation = "POWER"
    n_pow.use_clamp = True
    n_pow.inputs[1].default_value = 1.8

    n_gate = nt.nodes.new("ShaderNodeValue")
    n_gate.outputs[0].default_value = 0.38

    n_mul = nt.nodes.new("ShaderNodeMath")
    n_mul.operation = "MULTIPLY"
    n_mul.use_clamp = True

    nt.links.new(n_lw.outputs["Facing"], n_inv.inputs[1])
    nt.links.new(n_inv.outputs["Value"], n_inv_pow.inputs[0])
    nt.links.new(n_lw.outputs["Facing"], n_bell.inputs[0])
    nt.links.new(n_inv_pow.outputs["Value"], n_bell.inputs[1])
    nt.links.new(n_bell.outputs["Value"], n_bell_gain.inputs[0])
    nt.links.new(n_bell_gain.outputs["Value"], n_pow.inputs[0])
    nt.links.new(n_pow.outputs["Value"], n_mul.inputs[0])
    nt.links.new(n_gate.outputs[0], n_mul.inputs[1])
    nt.links.new(n_mul.outputs["Value"], n_mix_s.inputs["Fac"])
    nt.links.new(n_trans.outputs["BSDF"], n_mix_s.inputs[1])
    nt.links.new(n_em.outputs["Emission"], n_mix_s.inputs[2])
    nt.links.new(n_mix_s.outputs["Shader"], n_out.inputs["Surface"])

    if alpha_weights:
        for f, val in alpha_weights:
            n_gate.outputs[0].default_value = val * 0.42
            n_gate.outputs[0].keyframe_insert("default_value", frame=f)
        set_fcurve_interpolation_data(nt, "BEZIER")
    return mat


def add_shade_smooth(ng, geom_socket):
    n_ss = ng.nodes.new("GeometryNodeSetShadeSmooth")
    n_ss.inputs["Shade Smooth"].default_value = True
    ng.links.new(geom_socket, n_ss.inputs["Mesh"])
    return n_ss.outputs[0]


def create_volume_sphere(name, col, radius, mat, subdivisions=3, active_frame_range=None):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=radius, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    obj.display_type = "WIRE"
    obj.visible_shadow = False
    link_to_collection(obj, col)

    if active_frame_range is not None:
        f_on, f_off = active_frame_range
        keys = []
        if f_on > 1:
            keys.extend([(1, True), (f_on - 1, True)])
        keys.extend([(f_on, False), (f_off, False)])
        if f_off < 480:
            keys.append((f_off + 1, True))
        for f, hidden in keys:
            obj.hide_render = hidden
            obj.keyframe_insert("hide_render", frame=f)
    return obj


def sample_stage_envelope(stage_key, cfg, peak_val, rest_val=0.0):
    frames = sorted(
        set(
            list(range(cfg["timeline"]["frame_start"], cfg["timeline"]["frame_end"] + 1, 6))
            + [cfg["timeline"]["frame_end"]]
            + [st["start_frame"] for st in cfg["stages"]]
            + [st["end_frame"] for st in cfg["stages"]]
        )
    )
    out = []
    for f in frames:
        w = get_stage_weights(frame_to_seconds(f, cfg))[stage_key]
        out.append((f, lerp(rest_val, peak_val, w)))
    return out


def encode_png_sequence(png_dir, out_mp4, out_prores=None, fps=24, width=854, height=480, frame_start=1, frame_end=480):
    files = sorted(f for f in os.listdir(png_dir) if f.endswith(".png"))
    if not files:
        raise RuntimeError(f"No PNG files found in {png_dir}")

    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        pattern = os.path.join(png_dir, "frame_%04d.png")
        subprocess.run([
            ffmpeg_bin, "-y", "-framerate", str(fps), "-i", pattern,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", out_mp4
        ], check=True)
        if out_prores:
            os.makedirs(os.path.dirname(out_prores), exist_ok=True)
            subprocess.run([
                ffmpeg_bin, "-y", "-framerate", str(fps), "-i", pattern,
                "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", out_prores
            ], check=True)
        return

    # Fallback: encode directly with Blender 5.3's built-in VSE FFmpeg encoder
    enc_scene = bpy.data.scenes.new("EncodeScene")
    enc_scene.sequence_editor_create()
    strips = enc_scene.sequence_editor.strips

    first_path = os.path.join(png_dir, files[0])
    strip = strips.new_image("Seq", first_path, channel=1, frame_start=1)
    for fn in files[1:]:
        strip.elements.append(fn)

    enc_scene.frame_start = 1
    enc_scene.frame_end = len(files)
    enc_scene.render.fps = fps
    enc_scene.render.resolution_x = width
    enc_scene.render.resolution_y = height
    enc_scene.render.resolution_percentage = 100
    enc_scene.render.use_sequencer = True
    enc_scene.view_settings.view_transform = "Standard"
    enc_scene.view_settings.look = "None"
    enc_scene.render.image_settings.media_type = "VIDEO"
    enc_scene.render.image_settings.file_format = "FFMPEG"
    enc_scene.render.image_settings.color_mode = "RGB"

    # 1. H.264 MP4
    enc_scene.render.ffmpeg.format = "MPEG4"
    enc_scene.render.ffmpeg.codec = "H264"
    enc_scene.render.ffmpeg.constant_rate_factor = "HIGH"
    enc_scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    enc_scene.render.filepath = out_mp4
    bpy.ops.render.render(animation=True, scene=enc_scene.name)

    # 2. ProRes 422 HQ MOV (if requested)
    if out_prores:
        os.makedirs(os.path.dirname(out_prores), exist_ok=True)
        enc_scene.render.ffmpeg.format = "QUICKTIME"
        enc_scene.render.ffmpeg.codec = "PRORES"
        enc_scene.render.ffmpeg.ffmpeg_prores_profile = "422_HQ"
        enc_scene.render.filepath = out_prores
        bpy.ops.render.render(animation=True, scene=enc_scene.name)

    bpy.data.scenes.remove(enc_scene)
