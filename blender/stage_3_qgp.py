import bpy
import math
import random
import scene_utils as utils
from mathutils import Vector


def _create_swirl_curves(name, count=90, inner_r=20.0, outer_r=44.0, smooth_nurbs=False, cfg=None):
    curve_data = bpy.data.curves.new(name, type="CURVE")
    curve_data.dimensions = "3D"
    rng = random.Random(303)

    cam_avoid = []
    if cfg is not None:
        for u_s in (6.5, 7.5, 8.5, 9.5, 10.5):
            pos, _, _, _ = utils.get_camera_pose(u_s, cfg)
            cam_avoid.append(pos)

    created = 0
    attempts = 0
    while created < count and attempts < count * 5:
        attempts += 1
        r0 = rng.uniform(inner_r + 1.5, outer_r - 1.5)
        theta0 = rng.uniform(0.0, math.tau)
        phi0 = rng.uniform(-0.85, 0.85)
        arc_len = rng.uniform(0.75, 1.55)
        wobble = rng.uniform(1.0, 2.8)
        pts = 22
        coords = []
        too_close = False
        for k in range(pts):
            t = k / (pts - 1)
            th = theta0 + t * arc_len
            ph = phi0 + 0.28 * math.sin(t * math.pi * 2.0 + wobble)
            r = r0 + 2.5 * math.sin(t * math.pi * 1.5 + theta0)
            cp = math.cos(ph)
            p = Vector((r * cp * math.sin(th), -r * cp * math.cos(th), r * math.sin(ph)))
            for cp_pos in cam_avoid:
                if (p - cp_pos).length < 6.5:
                    too_close = True
                    break
            if too_close:
                break
            coords.append(p)
        if too_close:
            continue

        spline = curve_data.splines.new("NURBS" if smooth_nurbs else "POLY")
        spline.points.add(pts - 1)
        for k, p in enumerate(coords):
            spline.points[k].co = (p.x, p.y, p.z, 1.0)
        if smooth_nurbs:
            spline.use_endpoint_u = True
            spline.order_u = 4
        created += 1

    return curve_data


def _build_qgp_filaments_gn(name, mat, taper=False, rad_max=0.095):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")

    n_time = ng.nodes.new("GeometryNodeInputSceneTime")
    n_pos = ng.nodes.new("GeometryNodeInputPosition")

    n_noise = ng.nodes.new("ShaderNodeTexNoise")
    n_noise.noise_dimensions = "4D"
    n_noise.inputs["Scale"].default_value = 0.12
    n_noise.inputs["Detail"].default_value = 3.0

    n_tscale = ng.nodes.new("ShaderNodeMath")
    n_tscale.operation = "MULTIPLY"
    n_tscale.inputs[1].default_value = 0.55

    n_sub = ng.nodes.new("ShaderNodeVectorMath")
    n_sub.operation = "SUBTRACT"
    n_sub.inputs[1].default_value = (0.5, 0.5, 0.5)

    n_vscale = ng.nodes.new("ShaderNodeVectorMath")
    n_vscale.operation = "SCALE"
    n_vscale.inputs["Scale"].default_value = 3.4

    n_setpos = ng.nodes.new("GeometryNodeSetPosition")
    ng.links.new(n_time.outputs["Seconds"], n_tscale.inputs[0])
    ng.links.new(n_pos.outputs["Position"], n_noise.inputs["Vector"])
    ng.links.new(n_tscale.outputs["Value"], n_noise.inputs["W"])
    ng.links.new(n_noise.outputs["Color"], n_sub.inputs[0])
    ng.links.new(n_sub.outputs["Vector"], n_vscale.inputs[0])
    ng.links.new(n_in.outputs["Geometry"], n_setpos.inputs["Geometry"])
    ng.links.new(n_vscale.outputs["Vector"], n_setpos.inputs["Offset"])

    cur_geom = n_setpos.outputs["Geometry"]

    if taper:
        n_res = ng.nodes.new("GeometryNodeResampleCurve")
        n_res.inputs["Count"].default_value = 68
        ng.links.new(cur_geom, n_res.inputs["Curve"])
        cur_geom = n_res.outputs["Curve"]

        # Taper curve radius smoothly from tips to midpoint + store color pulse attribute
        n_sp = ng.nodes.new("GeometryNodeSplineParameter")
        n_pi = ng.nodes.new("ShaderNodeMath")
        n_pi.operation = "MULTIPLY"
        n_pi.inputs[1].default_value = math.pi
        n_sin = ng.nodes.new("ShaderNodeMath")
        n_sin.operation = "SINE"
        n_map = ng.nodes.new("ShaderNodeMapRange")
        n_map.inputs["From Min"].default_value = 0.0
        n_map.inputs["From Max"].default_value = 1.0
        n_map.inputs["To Min"].default_value = 0.18
        n_map.inputs["To Max"].default_value = 1.0

        n_setrad = ng.nodes.new("GeometryNodeSetCurveRadius")
        ng.links.new(n_sp.outputs["Factor"], n_pi.inputs[0])
        ng.links.new(n_pi.outputs["Value"], n_sin.inputs[0])
        ng.links.new(n_sin.outputs["Value"], n_map.inputs["Value"])
        ng.links.new(cur_geom, n_setrad.inputs["Curve"])
        ng.links.new(n_map.outputs["Result"], n_setrad.inputs["Radius"])

        # Store per-spline color class
        n_rand = ng.nodes.new("FunctionNodeRandomValue")
        n_rand.data_type = "FLOAT"
        n_rand.inputs["Seed"].default_value = 77
        n_idx = ng.nodes.new("GeometryNodeInputIndex")
        ng.links.new(n_idx.outputs["Index"], n_rand.inputs["ID"])

        n_store_c = ng.nodes.new("GeometryNodeStoreNamedAttribute")
        n_store_c.domain = "CURVE"
        n_store_c.data_type = "FLOAT"
        n_store_c.inputs["Name"].default_value = "fil_class"
        ng.links.new(n_setrad.outputs["Curve"], n_store_c.inputs["Geometry"])
        ng.links.new(n_rand.outputs["Value"], n_store_c.inputs["Value"])
        cur_geom = n_store_c.outputs["Geometry"]

    n_prof = ng.nodes.new("GeometryNodeCurvePrimitiveCircle")
    n_prof.inputs["Resolution"].default_value = 6
    n_prof.inputs["Radius"].default_value = rad_max

    n_c2m = ng.nodes.new("GeometryNodeCurveToMesh")
    n_setmat = ng.nodes.new("GeometryNodeSetMaterial")
    n_setmat.inputs["Material"].default_value = mat

    ng.links.new(cur_geom, n_c2m.inputs["Curve"])
    ng.links.new(n_prof.outputs["Curve"], n_c2m.inputs["Profile Curve"])
    ng.links.new(utils.add_shade_smooth(ng, n_c2m.outputs["Mesh"]), n_setmat.inputs["Geometry"])
    ng.links.new(n_setmat.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def _build_qgp_seed_mesh(name, count, cfg):
    mesh = bpy.data.meshes.new(name)
    rng = random.Random(313)
    verts = []
    c_classes = []
    p_scales = []
    world_up = Vector((0.0, 0.0, 1.0))

    corridor_n = int(count * 0.40)
    for i in range(count):
        if i < corridor_n:
            u_s = 6.0 + (i / corridor_n) * 4.8
            pos, tgt, _, _ = utils.get_camera_pose(u_s, cfg)
            fwd = (tgt - pos).normalized()
            right = fwd.cross(world_up).normalized()
            up = right.cross(fwd).normalized()
            depth = rng.uniform(7.0, 24.0)
            p = pos + fwd * depth + right * rng.uniform(-0.62, 0.62) * depth + up * rng.uniform(-0.36, 0.36) * depth
            verts.append((p.x, p.y, p.z))
        else:
            th = rng.uniform(0.0, math.tau)
            cphi = rng.uniform(-0.92, 0.92)
            sphi = math.sqrt(max(0.0, 1.0 - cphi * cphi))
            r = rng.uniform(20.5, 44.0)
            verts.append((r * sphi * math.sin(th), -r * sphi * math.cos(th), r * cphi))

        pick = rng.random()
        c_classes.append(0.0 if pick < 0.36 else (0.5 if pick < 0.70 else 1.0))
        p_scales.append(rng.uniform(0.55, 1.55))

    mesh.from_pydata(verts, [], [])
    mesh.update()
    a1 = mesh.attributes.new("color_class", "FLOAT", "POINT")
    a1.data.foreach_set("value", c_classes)
    a2 = mesh.attributes.new("p_scale", "FLOAT", "POINT")
    a2.data.foreach_set("value", p_scales)
    return mesh


def _build_qgp_sim_gn(name, orb_mat):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")

    n_time = ng.nodes.new("GeometryNodeInputSceneTime")
    n_gate = ng.nodes.new("ShaderNodeMath")
    n_gate.operation = "GREATER_THAN"
    n_gate.inputs[1].default_value = 5.0
    ng.links.new(n_time.outputs["Seconds"], n_gate.inputs[0])

    si = ng.nodes.new("GeometryNodeSimulationInput")
    so = ng.nodes.new("GeometryNodeSimulationOutput")
    si.pair_with_output(so)
    so.state_items.new("VECTOR", "Vel")

    # Skip simulation before 5.0s
    n_not_gate = ng.nodes.new("ShaderNodeMath")
    n_not_gate.operation = "LESS_THAN"
    n_not_gate.inputs[1].default_value = 5.0
    ng.links.new(n_time.outputs["Seconds"], n_not_gate.inputs[0])
    ng.links.new(n_not_gate.outputs["Value"], so.inputs["Skip"])

    # Inside simulation zone: orbital swirl + 4D curl turbulence + radial spring around r=32
    n_pos = ng.nodes.new("GeometryNodeInputPosition")
    n_sep = ng.nodes.new("ShaderNodeSeparateXYZ")
    n_neg_y = ng.nodes.new("ShaderNodeMath")
    n_neg_y.operation = "MULTIPLY"
    n_neg_y.inputs[1].default_value = -1.0
    n_tan = ng.nodes.new("ShaderNodeCombineXYZ")
    n_tan_norm = ng.nodes.new("ShaderNodeVectorMath")
    n_tan_norm.operation = "NORMALIZE"
    n_tan_scale = ng.nodes.new("ShaderNodeVectorMath")
    n_tan_scale.operation = "SCALE"
    n_tan_scale.inputs["Scale"].default_value = 6.5

    n_noise = ng.nodes.new("ShaderNodeTexNoise")
    n_noise.noise_dimensions = "4D"
    n_noise.inputs["Scale"].default_value = 0.14
    n_noise.inputs["Detail"].default_value = 3.0
    n_nsub = ng.nodes.new("ShaderNodeVectorMath")
    n_nsub.operation = "SUBTRACT"
    n_nsub.inputs[1].default_value = (0.5, 0.5, 0.5)
    n_nscale = ng.nodes.new("ShaderNodeVectorMath")
    n_nscale.operation = "SCALE"
    n_nscale.inputs["Scale"].default_value = 11.0

    n_force_sum = ng.nodes.new("ShaderNodeVectorMath")
    n_force_sum.operation = "ADD"

    # Radial spring toward shell midplane r=32
    n_r_len = ng.nodes.new("ShaderNodeVectorMath")
    n_r_len.operation = "LENGTH"
    n_r_err = ng.nodes.new("ShaderNodeMath")
    n_r_err.operation = "SUBTRACT"
    n_r_err.inputs[0].default_value = 32.0
    n_r_norm = ng.nodes.new("ShaderNodeVectorMath")
    n_r_norm.operation = "NORMALIZE"
    n_r_spring = ng.nodes.new("ShaderNodeVectorMath")
    n_r_spring.operation = "SCALE"
    n_r_k = ng.nodes.new("ShaderNodeMath")
    n_r_k.operation = "MULTIPLY"
    n_r_k.inputs[1].default_value = 0.65

    n_force_all = ng.nodes.new("ShaderNodeVectorMath")
    n_force_all.operation = "ADD"

    # Blend Vel = Vel * 0.85 + Force * 0.15
    n_v_damp = ng.nodes.new("ShaderNodeVectorMath")
    n_v_damp.operation = "SCALE"
    n_v_damp.inputs["Scale"].default_value = 0.85
    n_f_blend = ng.nodes.new("ShaderNodeVectorMath")
    n_f_blend.operation = "SCALE"
    n_f_blend.inputs["Scale"].default_value = 0.15
    n_v_new = ng.nodes.new("ShaderNodeVectorMath")
    n_v_new.operation = "ADD"

    n_step = ng.nodes.new("ShaderNodeVectorMath")
    n_step.operation = "SCALE"
    n_setpos = ng.nodes.new("GeometryNodeSetPosition")

    ng.links.new(n_in.outputs["Geometry"], si.inputs["Geometry"])

    ng.links.new(n_pos.outputs["Position"], n_sep.inputs["Vector"])
    ng.links.new(n_sep.outputs["Y"], n_neg_y.inputs[0])
    ng.links.new(n_neg_y.outputs["Value"], n_tan.inputs["X"])
    ng.links.new(n_sep.outputs["X"], n_tan.inputs["Y"])
    ng.links.new(n_tan.outputs["Vector"], n_tan_norm.inputs[0])
    ng.links.new(n_tan_norm.outputs["Vector"], n_tan_scale.inputs[0])

    ng.links.new(n_pos.outputs["Position"], n_noise.inputs["Vector"])
    ng.links.new(n_time.outputs["Seconds"], n_noise.inputs["W"])
    ng.links.new(n_noise.outputs["Color"], n_nsub.inputs[0])
    ng.links.new(n_nsub.outputs["Vector"], n_nscale.inputs[0])
    ng.links.new(n_tan_scale.outputs["Vector"], n_force_sum.inputs[0])
    ng.links.new(n_nscale.outputs["Vector"], n_force_sum.inputs[1])

    ng.links.new(n_pos.outputs["Position"], n_r_len.inputs[0])
    ng.links.new(n_r_len.outputs["Value"], n_r_err.inputs[1])
    ng.links.new(n_r_err.outputs["Value"], n_r_k.inputs[0])
    ng.links.new(n_pos.outputs["Position"], n_r_norm.inputs[0])
    ng.links.new(n_r_norm.outputs["Vector"], n_r_spring.inputs[0])
    ng.links.new(n_r_k.outputs["Value"], n_r_spring.inputs["Scale"])

    ng.links.new(n_force_sum.outputs["Vector"], n_force_all.inputs[0])
    ng.links.new(n_r_spring.outputs["Vector"], n_force_all.inputs[1])

    ng.links.new(si.outputs["Vel"], n_v_damp.inputs[0])
    ng.links.new(n_force_all.outputs["Vector"], n_f_blend.inputs[0])
    ng.links.new(n_v_damp.outputs["Vector"], n_v_new.inputs[0])
    ng.links.new(n_f_blend.outputs["Vector"], n_v_new.inputs[1])

    ng.links.new(n_v_new.outputs["Vector"], n_step.inputs[0])
    ng.links.new(si.outputs["Delta Time"], n_step.inputs["Scale"])
    ng.links.new(si.outputs["Geometry"], n_setpos.inputs["Geometry"])
    ng.links.new(n_step.outputs["Vector"], n_setpos.inputs["Offset"])

    ng.links.new(n_setpos.outputs["Geometry"], so.inputs["Geometry"])
    ng.links.new(n_v_new.outputs["Vector"], so.inputs["Vel"])

    # Instance soft glowing plasma orbs on simulated points
    n_pscale = ng.nodes.new("GeometryNodeInputNamedAttribute")
    n_pscale.data_type = "FLOAT"
    n_pscale.inputs["Name"].default_value = "p_scale"

    n_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_ico.inputs["Radius"].default_value = 0.15
    n_ico.inputs["Subdivisions"].default_value = 2

    n_inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_mat = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat.inputs["Material"].default_value = orb_mat

    ng.links.new(so.outputs["Geometry"], n_inst.inputs["Points"])
    ng.links.new(utils.add_shade_smooth(ng, n_ico.outputs["Mesh"]), n_inst.inputs["Instance"])
    ng.links.new(n_pscale.outputs["Attribute"], n_inst.inputs["Scale"])
    ng.links.new(n_inst.outputs["Instances"], n_mat.inputs["Geometry"])
    ng.links.new(n_mat.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def build(scene, cfg, mode="scaffold"):
    col = utils.ensure_collection("Stage_3_QGP")

    if mode == "scaffold":
        sg = cfg["scaffold_greys"]
        dens_keys = utils.sample_stage_envelope("qgp", cfg, sg["qgp_density"], rest_val=0.0)
        em_keys = utils.sample_stage_envelope("qgp", cfg, sg["qgp_emission"], rest_val=0.0)

        vol_mat = utils.make_shell_volume_material(
            "Stage3_QGP_VolMat",
            inner_r=19.0,
            outer_r=44.5,
            feather=4.0,
            base_color=(0.30, 0.30, 0.32),
            hot_color=(0.76, 0.76, 0.78),
            noise_scale=0.14,
            noise_detail=5.0,
            noise_distortion=1.9,
            noise_speed=2.8,
            density_keyframes=dens_keys,
            emission_keyframes=em_keys,
            cfg=cfg,
        )
        utils.create_volume_sphere("QGP_Plasma_Volume", col, radius=47.0, mat=vol_mat, subdivisions=3)

        qgp_alpha = utils.sample_stage_envelope("qgp", cfg, 1.0, rest_val=0.0)
        fil_mat = utils.make_emissive_material(
            "Stage3_QGP_FilamentMat",
            color_rgb=(0.86, 0.86, 0.90),
            strength=1.4,
            keyframed_strengths=utils.sample_stage_envelope("qgp", cfg, 1.55, rest_val=0.0),
            alpha_weights=qgp_alpha,
        )
        curve_data = _create_swirl_curves("QGP_Swirl_CurveData", count=110, inner_r=20.5, outer_r=43.5)
        fil_obj = bpy.data.objects.new("QGP_Swirl_Filaments", curve_data)
        fil_obj.visible_shadow = False
        utils.link_to_collection(fil_obj, col)
        for f, hidden in ((1, True), (128, True), (129, False), (278, False), (279, True)):
            fil_obj.hide_render = hidden
            fil_obj.keyframe_insert("hide_render", frame=f)

        mod = fil_obj.modifiers.new("QGPFilamentsGN", "NODES")
        mod.node_group = _build_qgp_filaments_gn("QGP_Filaments_GN", fil_mat)

        fil_obj.rotation_euler = (0.0, 0.0, 0.0)
        fil_obj.keyframe_insert("rotation_euler", frame=120)
        fil_obj.rotation_euler = (0.12, -0.08, 0.95)
        fil_obj.keyframe_insert("rotation_euler", frame=280)
        utils.set_fcurve_interpolation(fil_obj, "LINEAR")
        return col

    # Full cinematic look-development mode
    fl = cfg["full_look"]["qgp"]
    c_or = (1.00, 0.34, 0.02)
    c_rd = (0.98, 0.06, 0.10)
    c_vi = (0.62, 0.10, 1.00)

    # 1. Roiling Orange / Red / Violet Volumetric Plasma
    qgp_ramp = [
        (0.18, (0.07, 0.008, 0.14)),
        (0.46, (0.62, 0.025, 0.07)),
        (0.72, (0.95, 0.260, 0.02)),
        (0.92, (1.00, 0.720, 0.24)),
    ]
    dens_keys = utils.sample_stage_envelope("qgp", cfg, fl["shell_density"], rest_val=0.0)
    em_keys = utils.sample_stage_envelope("qgp", cfg, fl["shell_emission"], rest_val=0.0)
    vol_mat = utils.make_rich_volume_material(
        "Stage3_QGP_VolMat",
        inner_r=18.5,
        outer_r=45.0,
        feather=4.2,
        ramp_stops=qgp_ramp,
        noise_scale=0.14,
        noise_detail=4.0,
        noise_distortion=2.4,
        noise_speed=2.6,
        voronoi_scale=0.19,
        voronoi_mix=0.35,
        anisotropy=0.52,
        emission_power=1.45,
        density_keyframes=dens_keys,
        emission_keyframes=em_keys,
        cfg=cfg,
    )
    utils.create_volume_sphere("QGP_Plasma_Volume", col, radius=47.5, mat=vol_mat, subdivisions=3, active_frame_range=(124, 282))

    qgp_alpha = utils.sample_stage_envelope("qgp", cfg, 0.94, rest_val=0.0)

    # 2. Swirling Geometry Nodes Simulation Zone Particles
    orb_ramp = [(0.0, c_or), (0.5, c_rd), (1.0, c_vi)]
    orb_mat = utils.make_plasma_orb_material(
        "Stage3_QGP_OrbMat",
        core_rgb=(1.0, 0.88, 0.65),
        strength=3.8,
        keyframed_strengths=utils.sample_stage_envelope("qgp", cfg, 3.8, rest_val=0.0),
        alpha_weights=qgp_alpha,
        attr_name="color_class",
        attr_ramp=orb_ramp,
        attr_type="INSTANCER",
        power=2.3,
    )
    seed_mesh = _build_qgp_seed_mesh("QGP_Sim_Seeds", fl["particle_count"], cfg)
    sim_obj = bpy.data.objects.new("QGP_Turbulence_Particles", seed_mesh)
    sim_obj.visible_shadow = False
    utils.link_to_collection(sim_obj, col)
    for f, hidden in ((1, True), (124, True), (125, False), (278, False), (279, True)):
        sim_obj.hide_render = hidden
        sim_obj.keyframe_insert("hide_render", frame=f)

    smod = sim_obj.modifiers.new("QGPSimGN", "NODES")
    smod.node_group = _build_qgp_sim_gn("QGP_Turbulence_Sim_GN", orb_mat)

    # 3. 200 Smooth Tapered NURBS Gluon Energy Filaments (filtered away from camera lens)
    fil_ramp = [(0.0, c_or), (0.48, c_rd), (1.0, c_vi)]
    fil_mat = utils.make_emissive_material(
        "Stage3_QGP_FilamentMat",
        strength=2.4,
        keyframed_strengths=utils.sample_stage_envelope("qgp", cfg, 2.4, rest_val=0.0),
        alpha_weights=utils.sample_stage_envelope("qgp", cfg, 0.85, rest_val=0.0),
        attr_name="fil_class",
        attr_ramp=fil_ramp,
        attr_type="GEOMETRY",
    )
    curve_data = _create_swirl_curves(
        "QGP_Swirl_CurveData", count=fl["filament_count"], inner_r=20.0, outer_r=44.0, smooth_nurbs=True, cfg=cfg
    )
    fil_obj = bpy.data.objects.new("QGP_Swirl_Filaments", curve_data)
    fil_obj.visible_shadow = False
    utils.link_to_collection(fil_obj, col)
    for f, hidden in ((1, True), (124, True), (125, False), (278, False), (279, True)):
        fil_obj.hide_render = hidden
        fil_obj.keyframe_insert("hide_render", frame=f)

    fmod = fil_obj.modifiers.new("QGPFilamentsGN", "NODES")
    fmod.node_group = _build_qgp_filaments_gn("QGP_Filaments_GN", fil_mat, taper=True, rad_max=0.044)

    fil_obj.rotation_euler = (0.0, 0.0, 0.0)
    fil_obj.keyframe_insert("rotation_euler", frame=120)
    fil_obj.rotation_euler = (0.14, -0.09, 1.05)
    fil_obj.keyframe_insert("rotation_euler", frame=280)
    utils.set_fcurve_interpolation(fil_obj, "LINEAR")
    return col
