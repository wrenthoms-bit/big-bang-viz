import bpy
import math
import random
import scene_utils as utils
from mathutils import Vector


def _create_neutrino_ray_curves(name, cfg, hero_n=180, shell_n=80):
    curve_data = bpy.data.curves.new(name, type="CURVE")
    curve_data.dimensions = "3D"
    rng = random.Random(606)
    world_up = Vector((0.0, 0.0, 1.0))

    for i in range(hero_n):
        u_s = 16.0 + (i / hero_n) * 2.55
        pos, tgt, _, _ = utils.get_camera_pose(u_s, cfg)
        fwd = (tgt - pos).normalized()
        right = fwd.cross(world_up).normalized()
        up = right.cross(fwd).normalized()

        depth = rng.uniform(13.0, 38.0)
        sx = rng.uniform(-0.56, 0.56) * depth
        sy = rng.uniform(-0.32, 0.32) * depth
        origin = pos + fwd * depth + right * sx + up * sy

        d = origin.normalized()
        d = (d + Vector((rng.uniform(-0.24, 0.24), rng.uniform(-0.24, 0.24), rng.uniform(-0.24, 0.24)))).normalized()
        length = rng.uniform(3.8, 7.2)

        spline = curve_data.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co = (origin.x, origin.y, origin.z, 1.0)
        p1 = origin + d * length
        spline.points[1].co = (p1.x, p1.y, p1.z, 1.0)

    for _ in range(shell_n):
        th = rng.uniform(0.0, math.tau)
        cphi = rng.uniform(-0.85, 0.85)
        sphi = math.sqrt(max(0.0, 1.0 - cphi * cphi))
        r = rng.uniform(78.0, 122.0)
        origin = Vector((r * sphi * math.sin(th), -r * sphi * math.cos(th), r * cphi))
        d = origin.normalized()
        length = rng.uniform(4.2, 7.8)
        spline = curve_data.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co = (origin.x, origin.y, origin.z, 1.0)
        p1 = origin + d * length
        spline.points[1].co = (p1.x, p1.y, p1.z, 1.0)

    return curve_data


def _build_neutrinos_gn(name, mat, taper=False):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")

    n_time = ng.nodes.new("GeometryNodeInputSceneTime")
    n_pos = ng.nodes.new("GeometryNodeInputPosition")

    n_t_sub = ng.nodes.new("ShaderNodeMath")
    n_t_sub.operation = "SUBTRACT"
    n_t_sub.inputs[1].default_value = 15.8
    n_t_max = ng.nodes.new("ShaderNodeMath")
    n_t_max.operation = "MAXIMUM"
    n_t_max.inputs[1].default_value = 0.0

    n_t_speed = ng.nodes.new("ShaderNodeMath")
    n_t_speed.operation = "MULTIPLY"
    n_t_speed.inputs[1].default_value = 6.8 if taper else 11.0

    n_dir = ng.nodes.new("ShaderNodeVectorMath")
    n_dir.operation = "NORMALIZE"

    n_offset = ng.nodes.new("ShaderNodeVectorMath")
    n_offset.operation = "SCALE"

    n_setpos = ng.nodes.new("GeometryNodeSetPosition")
    ng.links.new(n_time.outputs["Seconds"], n_t_sub.inputs[0])
    ng.links.new(n_t_sub.outputs["Value"], n_t_max.inputs[0])
    ng.links.new(n_t_max.outputs["Value"], n_t_speed.inputs[0])
    ng.links.new(n_pos.outputs["Position"], n_dir.inputs[0])
    ng.links.new(n_dir.outputs["Vector"], n_offset.inputs[0])
    ng.links.new(n_t_speed.outputs["Value"], n_offset.inputs["Scale"])
    ng.links.new(n_in.outputs["Geometry"], n_setpos.inputs["Geometry"])
    ng.links.new(n_offset.outputs["Vector"], n_setpos.inputs["Offset"])

    cur_geom = n_setpos.outputs["Geometry"]

    if taper:
        n_res = ng.nodes.new("GeometryNodeResampleCurve")
        n_res.inputs["Count"].default_value = 12
        n_sp = ng.nodes.new("GeometryNodeSplineParameter")

        # Sleek comet needle profile: 0 at both tail (0) and tip (1), peaking around t=0.65
        n_pow_tail = ng.nodes.new("ShaderNodeMath")
        n_pow_tail.operation = "POWER"
        n_pow_tail.inputs[1].default_value = 0.65

        n_one_minus = ng.nodes.new("ShaderNodeMath")
        n_one_minus.operation = "SUBTRACT"
        n_one_minus.inputs[0].default_value = 1.0

        n_pow_tip = ng.nodes.new("ShaderNodeMath")
        n_pow_tip.operation = "POWER"
        n_pow_tip.inputs[1].default_value = 0.35

        n_shape = ng.nodes.new("ShaderNodeMath")
        n_shape.operation = "MULTIPLY"

        n_shape_gain = ng.nodes.new("ShaderNodeMath")
        n_shape_gain.operation = "MULTIPLY"
        n_shape_gain.inputs[1].default_value = 2.0

        # Smooth camera proximity fade so streaks never clip or slab across the lens
        cam_obj = bpy.context.scene.camera
        n_cam_fade = None
        if cam_obj is not None:
            n_pos_anim = ng.nodes.new("GeometryNodeInputPosition")
            n_cam_info = ng.nodes.new("GeometryNodeObjectInfo")
            n_cam_info.transform_space = "RELATIVE"
            n_cam_info.inputs["Object"].default_value = cam_obj

            n_dist = ng.nodes.new("ShaderNodeVectorMath")
            n_dist.operation = "DISTANCE"
            n_cam_fade = ng.nodes.new("ShaderNodeMapRange")
            n_cam_fade.clamp = True
            n_cam_fade.inputs["From Min"].default_value = 9.0
            n_cam_fade.inputs["From Max"].default_value = 15.0
            n_cam_fade.inputs["To Min"].default_value = 0.0
            n_cam_fade.inputs["To Max"].default_value = 1.0

            ng.links.new(n_pos_anim.outputs["Position"], n_dist.inputs[0])
            ng.links.new(n_cam_info.outputs["Location"], n_dist.inputs[1])
            ng.links.new(n_dist.outputs["Value"], n_cam_fade.inputs["Value"])

        n_rad_mul = ng.nodes.new("ShaderNodeMath")
        n_rad_mul.operation = "MULTIPLY"

        n_setrad = ng.nodes.new("GeometryNodeSetCurveRadius")

        n_store = ng.nodes.new("GeometryNodeStoreNamedAttribute")
        n_store.domain = "POINT"
        n_store.data_type = "FLOAT"
        n_store.inputs["Name"].default_value = "trail_t"

        ng.links.new(cur_geom, n_res.inputs["Curve"])
        ng.links.new(n_sp.outputs["Factor"], n_pow_tail.inputs[0])
        ng.links.new(n_sp.outputs["Factor"], n_one_minus.inputs[1])
        ng.links.new(n_one_minus.outputs["Value"], n_pow_tip.inputs[0])
        ng.links.new(n_pow_tail.outputs["Value"], n_shape.inputs[0])
        ng.links.new(n_pow_tip.outputs["Value"], n_shape.inputs[1])
        ng.links.new(n_shape.outputs["Value"], n_shape_gain.inputs[0])

        if n_cam_fade is not None:
            ng.links.new(n_shape_gain.outputs["Value"], n_rad_mul.inputs[0])
            ng.links.new(n_cam_fade.outputs["Result"], n_rad_mul.inputs[1])
            rad_sock = n_rad_mul.outputs["Value"]
        else:
            rad_sock = n_shape_gain.outputs["Value"]

        ng.links.new(n_res.outputs["Curve"], n_setrad.inputs["Curve"])
        ng.links.new(rad_sock, n_setrad.inputs["Radius"])
        ng.links.new(n_setrad.outputs["Curve"], n_store.inputs["Geometry"])
        ng.links.new(n_sp.outputs["Factor"], n_store.inputs["Value"])
        cur_geom = n_store.outputs["Geometry"]

    n_prof = ng.nodes.new("GeometryNodeCurvePrimitiveCircle")
    n_prof.inputs["Resolution"].default_value = 8 if taper else 5
    n_prof.inputs["Radius"].default_value = 0.024 if taper else 0.055

    n_c2m = ng.nodes.new("GeometryNodeCurveToMesh")
    n_c2m.inputs["Fill Caps"].default_value = False
    n_setmat = ng.nodes.new("GeometryNodeSetMaterial")
    n_setmat.inputs["Material"].default_value = mat

    ng.links.new(cur_geom, n_c2m.inputs["Curve"])
    ng.links.new(n_prof.outputs["Curve"], n_c2m.inputs["Profile Curve"])
    ng.links.new(utils.add_shade_smooth(ng, n_c2m.outputs["Mesh"]), n_setmat.inputs["Geometry"])
    ng.links.new(n_setmat.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def build(scene, cfg, mode="scaffold"):
    col = utils.ensure_collection("Stage_6_Neutrinos")

    frames = sorted(
        set(
            list(range(cfg["timeline"]["frame_start"], cfg["timeline"]["frame_end"] + 1, 6))
            + [cfg["timeline"]["frame_end"]]
        )
    )

    if mode == "scaffold":
        sg = cfg["scaffold_greys"]
        dens_keys = []
        em_keys = []
        for f in frames:
            u = utils.frame_to_seconds(f, cfg)
            w = utils.smoothstep(15.2, 16.5, u)
            dens_keys.append((f, sg["neutrinos_density"] * w))
            em_keys.append((f, sg["neutrinos_emission"] * w))

        vol_mat = utils.make_shell_volume_material(
            "Stage6_Cooling_VolMat",
            inner_r=72.0,
            outer_r=140.0,
            feather=6.0,
            base_color=(0.18, 0.18, 0.21),
            hot_color=(0.70, 0.70, 0.74),
            noise_scale=0.065,
            noise_detail=2.0,
            noise_distortion=0.12,
            noise_speed=0.45,
            density_keyframes=dens_keys,
            emission_keyframes=em_keys,
            cfg=cfg,
        )
        utils.create_volume_sphere("Neutrinos_Cooling_Volume", col, radius=144.0, mat=vol_mat, subdivisions=3)

        neu_alpha = utils.sample_stage_envelope("neutrinos", cfg, 0.72, rest_val=0.0)
        trail_mat = utils.make_emissive_material(
            "Stage6_NeutrinoTrail_Mat",
            color_rgb=(0.90, 0.90, 0.94),
            strength=1.35,
            keyframed_strengths=utils.sample_stage_envelope("neutrinos", cfg, 1.45, rest_val=0.0),
            alpha_weights=neu_alpha,
        )
        curve_data = _create_neutrino_ray_curves("Neutrino_Trails_CurveData", cfg)
        trails_obj = bpy.data.objects.new("Neutrino_Trails", curve_data)
        trails_obj.visible_shadow = False
        utils.link_to_collection(trails_obj, col)
        for f, hidden in ((1, True), (373, True), (374, False), (468, False), (469, True)):
            trails_obj.hide_render = hidden
            trails_obj.keyframe_insert("hide_render", frame=f)

        mod = trails_obj.modifiers.new("NeutrinosGN", "NODES")
        mod.node_group = _build_neutrinos_gn("Neutrinos_Trails_GN", trail_mat)
        return col

    # Full cinematic look-development mode
    fl = cfg["full_look"]["neutrinos"]
    dens_keys = []
    em_keys = []
    for f in frames:
        u = utils.frame_to_seconds(f, cfg)
        w = utils.smoothstep(15.2, 16.5, u)
        dens_keys.append((f, fl["shell_density"] * w))
        em_keys.append((f, fl["shell_emission"] * w))

    # Smooth cooling burnt-orange/terracotta plasma with gentle acoustic density ripples (NO cosmic web)
    cool_ramp = [
        (0.14, (0.16, 0.032, 0.010)),
        (0.45, (0.52, 0.145, 0.028)),
        (0.74, (0.94, 0.390, 0.090)),
        (0.95, (1.00, 0.600, 0.220)),
    ]
    vol_mat = utils.make_rich_volume_material(
        "Stage6_Cooling_VolMat",
        inner_r=72.0,
        outer_r=144.0,
        feather=6.5,
        ramp_stops=cool_ramp,
        noise_scale=0.048,
        noise_detail=2.5,
        noise_distortion=0.10,
        noise_speed=0.45,
        voronoi_scale=0.06,
        voronoi_mix=0.0,
        anisotropy=0.40,
        emission_power=1.22,
        dens_range=(0.24, 0.78),
        density_keyframes=dens_keys,
        emission_keyframes=em_keys,
        cfg=cfg,
    )
    utils.create_volume_sphere("Neutrinos_Cooling_Volume", col, radius=148.0, mat=vol_mat, subdivisions=3, active_frame_range=(365, 480))

    # Faint, fast free-streaming pale silver-blue neutrino trails fading gracefully before f461
    trail_ramp = [
        (0.0, (0.36, 0.56, 0.88)),
        (0.65, tuple(cfg["colors"]["neutrino_trail"])),
        (1.0, (1.0, 1.0, 1.0)),
    ]
    trail_env = []
    for f in frames:
        u = utils.frame_to_seconds(f, cfg)
        w = utils.smoothstep(15.3, 16.2, u) * (1.0 - utils.smoothstep(17.9, 19.2, u))
        trail_env.append((f, w))
    neu_alpha = [(f, w * 0.72) for f, w in trail_env]
    neu_em = [(f, w * fl["trail_emission"]) for f, w in trail_env]
    trail_mat = utils.make_emissive_material(
        "Stage6_NeutrinoTrail_Mat",
        strength=fl["trail_emission"],
        keyframed_strengths=neu_em,
        alpha_weights=neu_alpha,
        attr_name="trail_t",
        attr_ramp=trail_ramp,
        attr_type="GEOMETRY",
        alpha_attr_name="trail_t",
        alpha_attr_power=1.6,
    )
    curve_data = _create_neutrino_ray_curves(
        "Neutrino_Trails_CurveData", cfg, hero_n=fl["hero_trails"], shell_n=fl["shell_trails"]
    )
    trails_obj = bpy.data.objects.new("Neutrino_Trails", curve_data)
    trails_obj.visible_shadow = False
    utils.link_to_collection(trails_obj, col)
    for f, hidden in ((1, True), (365, True), (366, False), (463, False), (464, True)):
        trails_obj.hide_render = hidden
        trails_obj.keyframe_insert("hide_render", frame=f)

    mod = trails_obj.modifiers.new("NeutrinosGN", "NODES")
    mod.node_group = _build_neutrinos_gn("Neutrinos_Trails_GN", trail_mat, taper=True)
    return col
