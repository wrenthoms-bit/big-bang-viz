import bpy
import math
import random
import scene_utils as utils
from mathutils import Vector


def _build_pair_centers_mesh(name, cfg, hero_count=76, shell_count=76):
    mesh = bpy.data.meshes.new(name)
    rng = random.Random(505)
    verts = []
    annih_times = []
    seeds = []
    world_up = Vector((0.0, 0.0, 1.0))

    for i in range(hero_count):
        u_s = 14.10 + (i / hero_count) * 1.55
        pos, tgt, _, _ = utils.get_camera_pose(u_s, cfg)
        fwd = (tgt - pos).normalized()
        right = fwd.cross(world_up).normalized()
        up = right.cross(fwd).normalized()

        depth = rng.uniform(16.8, 31.0)
        sx = rng.uniform(-0.56, 0.56) * depth
        sy = rng.uniform(-0.32, 0.32) * depth
        p = pos + fwd * depth + right * sx + up * sy
        verts.append((p.x, p.y, p.z))
        annih_times.append(14.20 + ((i % 12) / 12.0) * 1.45 + rng.uniform(-0.06, 0.06))
        seeds.append(rng.uniform(0.0, 1.0))

    for _ in range(shell_count):
        th = rng.uniform(0.0, math.tau)
        cphi = rng.uniform(-0.9, 0.9)
        sphi = math.sqrt(max(0.0, 1.0 - cphi * cphi))
        r = rng.uniform(59.0, 79.0)
        verts.append((r * sphi * math.sin(th), -r * sphi * math.cos(th), r * cphi))
        annih_times.append(rng.uniform(14.15, 15.65))
        seeds.append(rng.uniform(0.0, 1.0))

    mesh.from_pydata(verts, [], [])
    mesh.update()

    attr_ann = mesh.attributes.new("annih_u", "FLOAT", "POINT")
    attr_ann.data.foreach_set("value", annih_times)
    attr_seed = mesh.attributes.new("seed", "FLOAT", "POINT")
    attr_seed.data.foreach_set("value", seeds)
    return mesh


def _build_remnant_mesh(name, cfg):
    mesh = bpy.data.meshes.new(name)
    rng = random.Random(515)
    verts = []
    world_up = Vector((0.0, 0.0, 1.0))

    for i in range(22):
        if i < 12:
            pos, tgt, _, _ = utils.get_camera_pose(15.65, cfg)
            fwd = (tgt - pos).normalized()
            right = fwd.cross(world_up).normalized()
            up = right.cross(fwd).normalized()
            depth = rng.uniform(10.0, 24.0)
            p = pos + fwd * depth + right * rng.uniform(-0.5, 0.5) * depth + up * rng.uniform(-0.3, 0.3) * depth
            verts.append((p.x, p.y, p.z))
        else:
            th = rng.uniform(0.0, math.tau)
            cphi = rng.uniform(-0.8, 0.8)
            sphi = math.sqrt(max(0.0, 1.0 - cphi * cphi))
            r = rng.uniform(60.0, 78.0)
            verts.append((r * sphi * math.sin(th), -r * sphi * math.cos(th), r * cphi))

    mesh.from_pydata(verts, [], [])
    mesh.update()
    return mesh


def _build_annihilation_gn(name, pair_mat, flash_mat, shock_mat=None):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")

    n_ann = ng.nodes.new("GeometryNodeInputNamedAttribute")
    n_ann.data_type = "FLOAT"
    n_ann.inputs["Name"].default_value = "annih_u"

    n_seed = ng.nodes.new("GeometryNodeInputNamedAttribute")
    n_seed.data_type = "FLOAT"
    n_seed.inputs["Name"].default_value = "seed"

    n_time = ng.nodes.new("GeometryNodeInputSceneTime")

    n_sub_pre = ng.nodes.new("ShaderNodeMath")
    n_sub_pre.operation = "SUBTRACT"
    n_sub_pre.inputs[1].default_value = 0.85

    n_pair_scale = ng.nodes.new("ShaderNodeMapRange")
    n_pair_scale.inputs["To Min"].default_value = 1.45
    n_pair_scale.inputs["To Max"].default_value = 0.0

    n_spin_mul = ng.nodes.new("ShaderNodeMath")
    n_spin_mul.operation = "MULTIPLY"
    n_spin_mul.inputs[1].default_value = 4.6
    n_seed_mul = ng.nodes.new("ShaderNodeMath")
    n_seed_mul.operation = "MULTIPLY"
    n_seed_mul.inputs[1].default_value = math.tau
    n_spin_add = ng.nodes.new("ShaderNodeMath")
    n_spin_add.operation = "ADD"
    n_rot_xyz = ng.nodes.new("ShaderNodeCombineXYZ")

    n_dipole = ng.nodes.new("GeometryNodeMeshLine")
    n_dipole.mode = "END_POINTS"
    n_dipole.count_mode = "TOTAL"
    n_dipole.inputs["Count"].default_value = 2
    n_dipole.inputs["Start Location"].default_value = (-1.0, 0.0, 0.0)
    n_dipole.inputs["Offset"].default_value = (1.0, 0.0, 0.0)

    n_inst_dipole = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_real_dipole = ng.nodes.new("GeometryNodeRealizeInstances")

    # Store side_id = Index % 2 (0.0 = matter gold, 1.0 = antimatter cyan)
    n_idx = ng.nodes.new("GeometryNodeInputIndex")
    n_mod2 = ng.nodes.new("ShaderNodeMath")
    n_mod2.operation = "MODULO"
    n_mod2.inputs[1].default_value = 2.0
    n_store_side = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    n_store_side.domain = "POINT"
    n_store_side.data_type = "FLOAT"
    n_store_side.inputs["Name"].default_value = "side_id"

    n_p_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_p_ico.inputs["Radius"].default_value = 0.20 if shock_mat else 0.24
    n_p_ico.inputs["Subdivisions"].default_value = 3 if shock_mat else 2

    n_alive = ng.nodes.new("ShaderNodeMath")
    n_alive.operation = "LESS_THAN"
    n_inst_particles = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_mat_pairs = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat_pairs.inputs["Material"].default_value = pair_mat

    # Flash age = (t - annih_u) / 0.38
    n_age_sub = ng.nodes.new("ShaderNodeMath")
    n_age_sub.operation = "SUBTRACT"
    n_age_div = ng.nodes.new("ShaderNodeMath")
    n_age_div.operation = "DIVIDE"
    n_age_div.inputs[1].default_value = 0.38

    n_gt0 = ng.nodes.new("ShaderNodeMath")
    n_gt0.operation = "GREATER_THAN"
    n_gt0.inputs[1].default_value = 0.0
    n_lt1 = ng.nodes.new("ShaderNodeMath")
    n_lt1.operation = "LESS_THAN"
    n_lt1.inputs[1].default_value = 1.0
    n_in_win = ng.nodes.new("ShaderNodeMath")
    n_in_win.operation = "MULTIPLY"

    n_pi_mul = ng.nodes.new("ShaderNodeMath")
    n_pi_mul.operation = "MULTIPLY"
    n_pi_mul.inputs[1].default_value = math.pi
    n_sin = ng.nodes.new("ShaderNodeMath")
    n_sin.operation = "SINE"
    n_flash_amp = ng.nodes.new("ShaderNodeMath")
    n_flash_amp.operation = "MULTIPLY"
    n_flash_amp.inputs[1].default_value = 0.36 if shock_mat else 0.85
    n_flash_scale = ng.nodes.new("ShaderNodeMath")
    n_flash_scale.operation = "MULTIPLY"

    n_flash_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_flash_ico.inputs["Radius"].default_value = 1.0
    n_flash_ico.inputs["Subdivisions"].default_value = 4 if shock_mat else 3

    n_inst_flash = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_mat_flash = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat_flash.inputs["Material"].default_value = flash_mat

    n_join = ng.nodes.new("GeometryNodeJoinGeometry")

    ng.links.new(n_ann.outputs["Attribute"], n_sub_pre.inputs[0])
    ng.links.new(n_time.outputs["Seconds"], n_pair_scale.inputs["Value"])
    ng.links.new(n_sub_pre.outputs["Value"], n_pair_scale.inputs["From Min"])
    ng.links.new(n_ann.outputs["Attribute"], n_pair_scale.inputs["From Max"])

    ng.links.new(n_time.outputs["Seconds"], n_spin_mul.inputs[0])
    ng.links.new(n_seed.outputs["Attribute"], n_seed_mul.inputs[0])
    ng.links.new(n_spin_mul.outputs["Value"], n_spin_add.inputs[0])
    ng.links.new(n_seed_mul.outputs["Value"], n_spin_add.inputs[1])
    ng.links.new(n_seed_mul.outputs["Value"], n_rot_xyz.inputs["X"])
    ng.links.new(n_spin_add.outputs["Value"], n_rot_xyz.inputs["Z"])

    ng.links.new(n_in.outputs["Geometry"], n_inst_dipole.inputs["Points"])
    ng.links.new(n_dipole.outputs["Mesh"], n_inst_dipole.inputs["Instance"])
    ng.links.new(n_rot_xyz.outputs["Vector"], n_inst_dipole.inputs["Rotation"])
    ng.links.new(n_pair_scale.outputs["Result"], n_inst_dipole.inputs["Scale"])
    ng.links.new(n_inst_dipole.outputs["Instances"], n_real_dipole.inputs["Geometry"])

    ng.links.new(n_idx.outputs["Index"], n_mod2.inputs[0])
    ng.links.new(n_real_dipole.outputs["Geometry"], n_store_side.inputs["Geometry"])
    ng.links.new(n_mod2.outputs["Value"], n_store_side.inputs["Value"])

    ng.links.new(n_time.outputs["Seconds"], n_alive.inputs[0])
    ng.links.new(n_ann.outputs["Attribute"], n_alive.inputs[1])
    ng.links.new(n_store_side.outputs["Geometry"], n_inst_particles.inputs["Points"])
    ng.links.new(utils.add_shade_smooth(ng, n_p_ico.outputs["Mesh"]), n_inst_particles.inputs["Instance"])
    ng.links.new(n_alive.outputs["Value"], n_inst_particles.inputs["Selection"])
    ng.links.new(n_inst_particles.outputs["Instances"], n_mat_pairs.inputs["Geometry"])

    ng.links.new(n_time.outputs["Seconds"], n_age_sub.inputs[0])
    ng.links.new(n_ann.outputs["Attribute"], n_age_sub.inputs[1])
    ng.links.new(n_age_sub.outputs["Value"], n_age_div.inputs[0])
    ng.links.new(n_age_div.outputs["Value"], n_gt0.inputs[0])
    ng.links.new(n_age_div.outputs["Value"], n_lt1.inputs[0])
    ng.links.new(n_gt0.outputs["Value"], n_in_win.inputs[0])
    ng.links.new(n_lt1.outputs["Value"], n_in_win.inputs[1])
    ng.links.new(n_age_div.outputs["Value"], n_pi_mul.inputs[0])
    ng.links.new(n_pi_mul.outputs["Value"], n_sin.inputs[0])
    ng.links.new(n_sin.outputs["Value"], n_flash_amp.inputs[0])
    ng.links.new(n_flash_amp.outputs["Value"], n_flash_scale.inputs[0])
    ng.links.new(n_in_win.outputs["Value"], n_flash_scale.inputs[1])

    ng.links.new(n_in.outputs["Geometry"], n_inst_flash.inputs["Points"])
    ng.links.new(utils.add_shade_smooth(ng, n_flash_ico.outputs["Mesh"]), n_inst_flash.inputs["Instance"])
    ng.links.new(n_in_win.outputs["Value"], n_inst_flash.inputs["Selection"])
    ng.links.new(n_flash_scale.outputs["Value"], n_inst_flash.inputs["Scale"])
    ng.links.new(n_inst_flash.outputs["Instances"], n_mat_flash.inputs["Geometry"])

    ng.links.new(n_mat_pairs.outputs["Geometry"], n_join.inputs["Geometry"])
    ng.links.new(n_mat_flash.outputs["Geometry"], n_join.inputs["Geometry"])

    if shock_mat is not None:
        # Soft dissolving shockwave aura: 0.18 + age * 0.72 (0.18 -> 0.90)
        n_sh_map = ng.nodes.new("ShaderNodeMapRange")
        n_sh_map.inputs["From Min"].default_value = 0.0
        n_sh_map.inputs["From Max"].default_value = 1.0
        n_sh_map.inputs["To Min"].default_value = 0.18
        n_sh_map.inputs["To Max"].default_value = 0.90

        n_sh_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
        n_sh_ico.inputs["Radius"].default_value = 1.0
        n_sh_ico.inputs["Subdivisions"].default_value = 4
        n_inst_sh = ng.nodes.new("GeometryNodeInstanceOnPoints")
        n_mat_sh = ng.nodes.new("GeometryNodeSetMaterial")
        n_mat_sh.inputs["Material"].default_value = shock_mat

        ng.links.new(n_age_div.outputs["Value"], n_sh_map.inputs["Value"])
        ng.links.new(n_in.outputs["Geometry"], n_inst_sh.inputs["Points"])
        ng.links.new(utils.add_shade_smooth(ng, n_sh_ico.outputs["Mesh"]), n_inst_sh.inputs["Instance"])
        ng.links.new(n_in_win.outputs["Value"], n_inst_sh.inputs["Selection"])
        ng.links.new(n_sh_map.outputs["Result"], n_inst_sh.inputs["Scale"])
        ng.links.new(n_inst_sh.outputs["Instances"], n_mat_sh.inputs["Geometry"])
        ng.links.new(n_mat_sh.outputs["Geometry"], n_join.inputs["Geometry"])

    ng.links.new(n_join.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def _build_remnant_gn(name, rem_mat):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")
    n_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_ico.inputs["Radius"].default_value = 0.26
    n_ico.inputs["Subdivisions"].default_value = 3
    n_inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_mat = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat.inputs["Material"].default_value = rem_mat
    ng.links.new(n_in.outputs["Geometry"], n_inst.inputs["Points"])
    ng.links.new(utils.add_shade_smooth(ng, n_ico.outputs["Mesh"]), n_inst.inputs["Instance"])
    ng.links.new(n_inst.outputs["Instances"], n_mat.inputs["Geometry"])
    ng.links.new(n_mat.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def build(scene, cfg, mode="scaffold"):
    col = utils.ensure_collection("Stage_5_Matter")

    if mode == "scaffold":
        sg = cfg["scaffold_greys"]
        dens_keys = utils.sample_stage_envelope("matter", cfg, sg["matter_density"], rest_val=0.0)
        em_keys = utils.sample_stage_envelope("matter", cfg, sg["matter_emission"], rest_val=0.0)

        vol_mat = utils.make_shell_volume_material(
            "Stage5_Matter_VolMat",
            inner_r=57.0,
            outer_r=81.0,
            feather=4.5,
            base_color=(0.38, 0.38, 0.40),
            hot_color=(0.85, 0.85, 0.88),
            noise_scale=0.09,
            noise_detail=4.0,
            noise_distortion=0.6,
            noise_speed=1.8,
            density_keyframes=dens_keys,
            emission_keyframes=em_keys,
            cfg=cfg,
        )
        utils.create_volume_sphere("Matter_Shell_Volume", col, radius=84.0, mat=vol_mat, subdivisions=3)

        mat_alpha = utils.sample_stage_envelope("matter", cfg, 1.0, rest_val=0.0)
        pair_mat = utils.make_emissive_material(
            "Stage5_Pair_Mat",
            color_rgb=(0.82, 0.82, 0.86),
            strength=1.6,
            keyframed_strengths=utils.sample_stage_envelope("matter", cfg, 1.8, rest_val=0.0),
            alpha_weights=mat_alpha,
        )
        flash_mat = utils.make_emissive_material(
            "Stage5_Flash_Mat",
            color_rgb=(0.98, 0.98, 1.0),
            strength=3.2,
            keyframed_strengths=utils.sample_stage_envelope("matter", cfg, 3.6, rest_val=0.0),
            alpha_weights=mat_alpha,
        )
        pair_mesh = _build_pair_centers_mesh("Matter_Pair_Centers", cfg)
        pair_obj = bpy.data.objects.new("Matter_Annihilation_Pairs", pair_mesh)
        pair_obj.visible_shadow = False
        utils.link_to_collection(pair_obj, col)
        for f, hidden in ((1, True), (323, True), (324, False), (398, False), (399, True)):
            pair_obj.hide_render = hidden
            pair_obj.keyframe_insert("hide_render", frame=f)
        mod = pair_obj.modifiers.new("AnnihilationGN", "NODES")
        mod.node_group = _build_annihilation_gn("Annihilation_GN", pair_mat, flash_mat)

        rem_mat = utils.make_emissive_material(
            "Stage5_Remnant_Mat",
            color_rgb=(0.92, 0.92, 0.96),
            strength=1.9,
            keyframed_strengths=utils.sample_stage_envelope("matter", cfg, 2.0, rest_val=0.0),
            alpha_weights=mat_alpha,
        )
        rem_mesh = _build_remnant_mesh("Matter_Remnant_Points", cfg)
        rem_obj = bpy.data.objects.new("Matter_Sparse_Remnant", rem_mesh)
        rem_obj.visible_shadow = False
        utils.link_to_collection(rem_obj, col)
        for f, hidden in ((1, True), (323, True), (324, False), (398, False), (399, True)):
            rem_obj.hide_render = hidden
            rem_obj.keyframe_insert("hide_render", frame=f)
        rmod = rem_obj.modifiers.new("RemnantGN", "NODES")
        rmod.node_group = _build_remnant_gn("Remnant_GN", rem_mat)
        return col

    # Full cinematic look-development mode
    fl = cfg["full_look"]["matter"]
    dp = cfg.get("depth_pass", {})
    depth_on = bool(dp.get("enabled", False))
    dp_m = dp.get("matter", {}) if depth_on else {}
    c_gold = (1.00, 0.48, 0.04)
    c_cyan = (0.06, 0.78, 1.00)
    c_flash = (1.00, 0.94, 0.80)

    if depth_on:
        matter_ramp = [
            (0.14, (0.04, 0.008, 0.002)),
            (0.46, (0.66, 0.220, 0.030)),
            (0.74, (0.98, 0.520, 0.100)),
            (0.94, (1.00, 0.860, 0.460)),
        ]
        shell_dens_peak = dp_m.get("shell_density", fl["shell_density"])
        shell_em_peak = dp_m.get("shell_emission", fl["shell_emission"])
    else:
        matter_ramp = [
            (0.16, (0.20, 0.040, 0.008)),
            (0.46, (0.66, 0.220, 0.030)),
            (0.74, (0.98, 0.520, 0.100)),
            (0.94, (1.00, 0.860, 0.460)),
        ]
        shell_dens_peak = fl["shell_density"]
        shell_em_peak = fl["shell_emission"]

    dens_keys = utils.sample_stage_envelope("matter", cfg, shell_dens_peak, rest_val=0.0)
    em_keys = utils.sample_stage_envelope("matter", cfg, shell_em_peak, rest_val=0.0)
    vol_mat = utils.make_rich_volume_material(
        "Stage5_Matter_VolMat",
        inner_r=57.0,
        outer_r=81.5,
        feather=4.5,
        ramp_stops=matter_ramp,
        noise_scale=0.09,
        noise_detail=4.0,
        noise_distortion=0.65,
        noise_speed=1.8,
        voronoi_scale=0.12,
        voronoi_mix=0.28,
        anisotropy=0.45,
        emission_power=1.30,
        density_keyframes=dens_keys,
        emission_keyframes=em_keys,
        cfg=cfg,
        depth_cfg=dp_m if depth_on else None,
    )
    utils.create_volume_sphere("Matter_Shell_Volume", col, radius=84.5, mat=vol_mat, subdivisions=3, active_frame_range=(322, 402))

    if depth_on and dp_m.get("fg_bokeh_count", 0) > 0:
        utils.build_foreground_drifters(
            "Matter_FG_Bokeh",
            col,
            cfg,
            stage_key="matter",
            u_start=13.8,
            u_end=16.2,
            hide_frames=((1, True), (323, True), (324, False), (398, False), (399, True)),
            core_rgb=(1.0, 0.94, 0.74),
            edge_rgb=(1.0, 0.50, 0.10),
            count=dp_m["fg_bokeh_count"],
            seed=515,
            strength=2.2,
            alpha_peak=0.58,
        )

    mat_alpha = utils.sample_stage_envelope("matter", cfg, 0.96, rest_val=0.0)
    pair_ramp = [(0.0, c_gold), (1.0, c_cyan)]
    pair_mat = utils.make_plasma_orb_material(
        "Stage5_Pair_Mat",
        core_rgb=(1.0, 0.94, 0.85),
        strength=2.8,
        keyframed_strengths=utils.sample_stage_envelope("matter", cfg, 2.8, rest_val=0.0),
        alpha_weights=mat_alpha,
        attr_name="side_id",
        attr_ramp=pair_ramp,
        attr_type="INSTANCER",
        power=3.4,
    )
    flash_mat = utils.make_plasma_orb_material(
        "Stage5_Flash_Mat",
        core_rgb=c_flash,
        edge_rgb=(1.0, 0.44, 0.08),
        strength=fl["flash_emission"],
        keyframed_strengths=utils.sample_stage_envelope("matter", cfg, fl["flash_emission"], rest_val=0.0),
        alpha_weights=mat_alpha,
        power=4.8,
    )
    shock_mat = utils.make_shockwave_shell_material(
        "Stage5_Shockwave_Mat",
        color_rgb=(1.0, 0.62, 0.16),
        strength=1.5,
        alpha_weights=utils.sample_stage_envelope("matter", cfg, 0.28, rest_val=0.0),
    )

    pair_mesh = _build_pair_centers_mesh(
        "Matter_Pair_Centers", cfg, hero_count=fl["hero_pairs"], shell_count=fl["shell_pairs"]
    )
    pair_obj = bpy.data.objects.new("Matter_Annihilation_Pairs", pair_mesh)
    pair_obj.visible_shadow = False
    utils.link_to_collection(pair_obj, col)
    for f, hidden in ((1, True), (323, True), (324, False), (398, False), (399, True)):
        pair_obj.hide_render = hidden
        pair_obj.keyframe_insert("hide_render", frame=f)
    mod = pair_obj.modifiers.new("AnnihilationGN", "NODES")
    mod.node_group = _build_annihilation_gn("Annihilation_GN", pair_mat, flash_mat, shock_mat=shock_mat)

    rem_mat = utils.make_plasma_orb_material(
        "Stage5_Remnant_Mat",
        core_rgb=(1.0, 0.94, 0.80),
        edge_rgb=c_gold,
        strength=2.8,
        keyframed_strengths=utils.sample_stage_envelope("matter", cfg, 2.8, rest_val=0.0),
        alpha_weights=mat_alpha,
        power=3.4,
    )
    rem_mesh = _build_remnant_mesh("Matter_Remnant_Points", cfg)
    rem_obj = bpy.data.objects.new("Matter_Sparse_Remnant", rem_mesh)
    rem_obj.visible_shadow = False
    utils.link_to_collection(rem_obj, col)
    for f, hidden in ((1, True), (323, True), (324, False), (398, False), (399, True)):
        rem_obj.hide_render = hidden
        rem_obj.keyframe_insert("hide_render", frame=f)
    rmod = rem_obj.modifiers.new("RemnantGN", "NODES")
    rmod.node_group = _build_remnant_gn("Remnant_GN", rem_mat)
    return col
