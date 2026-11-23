import bpy
import math
import random
import scene_utils as utils
from mathutils import Vector


def _build_triplet_centers_mesh(name, cfg, hero_count=68, shell_count=96):
    mesh = bpy.data.meshes.new(name)
    rng = random.Random(404)
    verts = []
    snap_times = []
    seeds = []

    world_up = Vector((0.0, 0.0, 1.0))

    for i in range(hero_count):
        u_s = 11.20 + (i / hero_count) * 2.50
        pos, tgt, _, _ = utils.get_camera_pose(u_s, cfg)
        fwd = (tgt - pos).normalized()
        right = fwd.cross(world_up).normalized()
        up = right.cross(fwd).normalized()

        depth = rng.uniform(10.5, 24.0)
        sx = rng.uniform(-0.56, 0.56) * depth
        sy = rng.uniform(-0.33, 0.33) * depth
        p = pos + fwd * depth + right * sx + up * sy
        verts.append((p.x, p.y, p.z))
        snap_times.append(11.35 + ((i % 10) / 10.0) * 1.85 + rng.uniform(-0.08, 0.08))
        seeds.append(rng.uniform(0.0, 1.0))

    for _ in range(shell_count):
        th = rng.uniform(0.0, math.tau)
        cphi = rng.uniform(-0.9, 0.9)
        sphi = math.sqrt(max(0.0, 1.0 - cphi * cphi))
        r = rng.uniform(41.0, 61.0)
        verts.append((r * sphi * math.sin(th), -r * sphi * math.cos(th), r * cphi))
        snap_times.append(rng.uniform(11.15, 13.35))
        seeds.append(rng.uniform(0.0, 1.0))

    mesh.from_pydata(verts, [], [])
    mesh.update()

    attr_snap = mesh.attributes.new("snap_u", "FLOAT", "POINT")
    attr_snap.data.foreach_set("value", snap_times)
    attr_seed = mesh.attributes.new("seed", "FLOAT", "POINT")
    attr_seed.data.foreach_set("value", seeds)
    return mesh


def _build_hadronization_gn(name, quark_mat, strut_mat, halo_mat=None):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")

    n_snap = ng.nodes.new("GeometryNodeInputNamedAttribute")
    n_snap.data_type = "FLOAT"
    n_snap.inputs["Name"].default_value = "snap_u"

    n_seed = ng.nodes.new("GeometryNodeInputNamedAttribute")
    n_seed.data_type = "FLOAT"
    n_seed.inputs["Name"].default_value = "seed"

    n_time = ng.nodes.new("GeometryNodeInputSceneTime")

    n_add = ng.nodes.new("ShaderNodeMath")
    n_add.operation = "ADD"
    n_add.inputs[1].default_value = 0.55

    n_map = ng.nodes.new("ShaderNodeMapRange")
    n_map.interpolation_type = "SMOOTHSTEP"
    n_map.inputs["To Min"].default_value = 2.10
    n_map.inputs["To Max"].default_value = 0.42

    n_spin_mul = ng.nodes.new("ShaderNodeMath")
    n_spin_mul.operation = "MULTIPLY"
    n_spin_mul.inputs[1].default_value = 1.9

    n_seed_mul = ng.nodes.new("ShaderNodeMath")
    n_seed_mul.operation = "MULTIPLY"
    n_seed_mul.inputs[1].default_value = math.tau

    n_spin_add = ng.nodes.new("ShaderNodeMath")
    n_spin_add.operation = "ADD"

    n_tilt_x = ng.nodes.new("ShaderNodeMath")
    n_tilt_x.operation = "MULTIPLY"
    n_tilt_x.inputs[1].default_value = 3.1

    n_tilt_y = ng.nodes.new("ShaderNodeMath")
    n_tilt_y.operation = "MULTIPLY"
    n_tilt_y.inputs[1].default_value = 4.7

    n_rot_xyz = ng.nodes.new("ShaderNodeCombineXYZ")

    n_tri = ng.nodes.new("GeometryNodeMeshCircle")
    n_tri.inputs["Vertices"].default_value = 3
    n_tri.inputs["Radius"].default_value = 1.0
    n_tri.fill_type = "NONE"

    n_inst_tri = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_realize = ng.nodes.new("GeometryNodeRealizeInstances")

    # Store quark_id = (Index % 3) / 2.0 on realized triangle corners so all 3 quarks get distinct warm hues
    n_idx = ng.nodes.new("GeometryNodeInputIndex")
    n_mod3 = ng.nodes.new("ShaderNodeMath")
    n_mod3.operation = "MODULO"
    n_mod3.inputs[1].default_value = 3.0
    n_div2 = ng.nodes.new("ShaderNodeMath")
    n_div2.operation = "DIVIDE"
    n_div2.inputs[1].default_value = 2.0

    n_store_qid = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    n_store_qid.domain = "POINT"
    n_store_qid.data_type = "FLOAT"
    n_store_qid.inputs["Name"].default_value = "quark_id"

    n_q_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_q_ico.inputs["Radius"].default_value = 0.20 if halo_mat else 0.22
    n_q_ico.inputs["Subdivisions"].default_value = 3 if halo_mat else 2

    n_inst_quarks = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_mat_quarks = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat_quarks.inputs["Material"].default_value = quark_mat

    n_m2c = ng.nodes.new("GeometryNodeMeshToCurve")
    n_prof = ng.nodes.new("GeometryNodeCurvePrimitiveCircle")
    n_prof.inputs["Resolution"].default_value = 6
    n_prof.inputs["Radius"].default_value = 0.024 if halo_mat else 0.038
    n_c2m = ng.nodes.new("GeometryNodeCurveToMesh")
    n_mat_struts = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat_struts.inputs["Material"].default_value = strut_mat

    n_join = ng.nodes.new("GeometryNodeJoinGeometry")

    ng.links.new(n_snap.outputs["Attribute"], n_add.inputs[0])
    ng.links.new(n_time.outputs["Seconds"], n_map.inputs["Value"])
    ng.links.new(n_snap.outputs["Attribute"], n_map.inputs["From Min"])
    ng.links.new(n_add.outputs["Value"], n_map.inputs["From Max"])

    ng.links.new(n_time.outputs["Seconds"], n_spin_mul.inputs[0])
    ng.links.new(n_seed.outputs["Attribute"], n_seed_mul.inputs[0])
    ng.links.new(n_spin_mul.outputs["Value"], n_spin_add.inputs[0])
    ng.links.new(n_seed_mul.outputs["Value"], n_spin_add.inputs[1])
    ng.links.new(n_seed.outputs["Attribute"], n_tilt_x.inputs[0])
    ng.links.new(n_seed.outputs["Attribute"], n_tilt_y.inputs[0])
    ng.links.new(n_tilt_x.outputs["Value"], n_rot_xyz.inputs["X"])
    ng.links.new(n_tilt_y.outputs["Value"], n_rot_xyz.inputs["Y"])
    ng.links.new(n_spin_add.outputs["Value"], n_rot_xyz.inputs["Z"])

    ng.links.new(n_in.outputs["Geometry"], n_inst_tri.inputs["Points"])
    ng.links.new(n_tri.outputs["Mesh"], n_inst_tri.inputs["Instance"])
    ng.links.new(n_rot_xyz.outputs["Vector"], n_inst_tri.inputs["Rotation"])
    ng.links.new(n_map.outputs["Result"], n_inst_tri.inputs["Scale"])
    ng.links.new(n_inst_tri.outputs["Instances"], n_realize.inputs["Geometry"])

    ng.links.new(n_idx.outputs["Index"], n_mod3.inputs[0])
    ng.links.new(n_mod3.outputs["Value"], n_div2.inputs[0])
    ng.links.new(n_realize.outputs["Geometry"], n_store_qid.inputs["Geometry"])
    ng.links.new(n_div2.outputs["Value"], n_store_qid.inputs["Value"])

    ng.links.new(n_store_qid.outputs["Geometry"], n_inst_quarks.inputs["Points"])
    ng.links.new(utils.add_shade_smooth(ng, n_q_ico.outputs["Mesh"]), n_inst_quarks.inputs["Instance"])
    ng.links.new(n_inst_quarks.outputs["Instances"], n_mat_quarks.inputs["Geometry"])

    ng.links.new(n_realize.outputs["Geometry"], n_m2c.inputs["Mesh"])
    ng.links.new(n_m2c.outputs["Curve"], n_c2m.inputs["Curve"])
    ng.links.new(n_prof.outputs["Curve"], n_c2m.inputs["Profile Curve"])
    ng.links.new(utils.add_shade_smooth(ng, n_c2m.outputs["Mesh"]), n_mat_struts.inputs["Geometry"])

    ng.links.new(n_mat_quarks.outputs["Geometry"], n_join.inputs["Geometry"])
    ng.links.new(n_mat_struts.outputs["Geometry"], n_join.inputs["Geometry"])

    if halo_mat is not None:
        # Confinement halo swells softly once triplet snaps shut [snap_u + 0.15, snap_u + 0.55] -> [0, 0.62]
        n_h0 = ng.nodes.new("ShaderNodeMath")
        n_h0.operation = "ADD"
        n_h0.inputs[1].default_value = 0.15
        n_h1 = ng.nodes.new("ShaderNodeMath")
        n_h1.operation = "ADD"
        n_h1.inputs[1].default_value = 0.55
        n_hmap = ng.nodes.new("ShaderNodeMapRange")
        n_hmap.interpolation_type = "SMOOTHSTEP"
        n_hmap.inputs["To Min"].default_value = 0.0
        n_hmap.inputs["To Max"].default_value = 0.62

        n_h_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
        n_h_ico.inputs["Radius"].default_value = 1.0
        n_h_ico.inputs["Subdivisions"].default_value = 3
        n_inst_halo = ng.nodes.new("GeometryNodeInstanceOnPoints")
        n_mat_halo = ng.nodes.new("GeometryNodeSetMaterial")
        n_mat_halo.inputs["Material"].default_value = halo_mat

        ng.links.new(n_snap.outputs["Attribute"], n_h0.inputs[0])
        ng.links.new(n_snap.outputs["Attribute"], n_h1.inputs[0])
        ng.links.new(n_time.outputs["Seconds"], n_hmap.inputs["Value"])
        ng.links.new(n_h0.outputs["Value"], n_hmap.inputs["From Min"])
        ng.links.new(n_h1.outputs["Value"], n_hmap.inputs["From Max"])
        ng.links.new(n_in.outputs["Geometry"], n_inst_halo.inputs["Points"])
        ng.links.new(utils.add_shade_smooth(ng, n_h_ico.outputs["Mesh"]), n_inst_halo.inputs["Instance"])
        ng.links.new(n_hmap.outputs["Result"], n_inst_halo.inputs["Scale"])
        ng.links.new(n_inst_halo.outputs["Instances"], n_mat_halo.inputs["Geometry"])
        ng.links.new(n_mat_halo.outputs["Geometry"], n_join.inputs["Geometry"])

    ng.links.new(n_join.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def build(scene, cfg, mode="scaffold"):
    col = utils.ensure_collection("Stage_4_Hadrons")

    if mode == "scaffold":
        sg = cfg["scaffold_greys"]
        dens_keys = utils.sample_stage_envelope("hadrons", cfg, sg["hadrons_density"], rest_val=0.0)
        em_keys = utils.sample_stage_envelope("hadrons", cfg, sg["hadrons_emission"], rest_val=0.0)

        vol_mat = utils.make_shell_volume_material(
            "Stage4_Hadrons_VolMat",
            inner_r=38.0,
            outer_r=63.0,
            feather=4.5,
            base_color=(0.34, 0.34, 0.36),
            hot_color=(0.68, 0.68, 0.72),
            noise_scale=0.11,
            noise_detail=4.0,
            noise_distortion=0.75,
            noise_speed=1.6,
            density_keyframes=dens_keys,
            emission_keyframes=em_keys,
            cfg=cfg,
        )
        utils.create_volume_sphere("Hadrons_Shell_Volume", col, radius=65.5, mat=vol_mat, subdivisions=3)

        had_alpha = utils.sample_stage_envelope("hadrons", cfg, 1.0, rest_val=0.0)
        quark_mat = utils.make_emissive_material(
            "Stage4_Quark_Mat",
            color_rgb=(0.94, 0.94, 0.98),
            strength=2.2,
            keyframed_strengths=utils.sample_stage_envelope("hadrons", cfg, 2.4, rest_val=0.0),
            alpha_weights=had_alpha,
        )
        strut_mat = utils.make_emissive_material(
            "Stage4_GluonStrut_Mat",
            color_rgb=(0.74, 0.74, 0.78),
            strength=1.4,
            keyframed_strengths=utils.sample_stage_envelope("hadrons", cfg, 1.5, rest_val=0.0),
            alpha_weights=had_alpha,
        )
        centers_mesh = _build_triplet_centers_mesh("Hadrons_Triplet_Centers", cfg)
        tri_obj = bpy.data.objects.new("Hadrons_Triplets", centers_mesh)
        tri_obj.visible_shadow = False
        utils.link_to_collection(tri_obj, col)
        for f, hidden in ((1, True), (248, True), (249, False), (348, False), (349, True)):
            tri_obj.hide_render = hidden
            tri_obj.keyframe_insert("hide_render", frame=f)

        mod = tri_obj.modifiers.new("HadronizationGN", "NODES")
        mod.node_group = _build_hadronization_gn("Hadronization_GN", quark_mat, strut_mat)
        return col

    # Full cinematic look-development mode
    fl = cfg["full_look"]["hadrons"]

    had_ramp = [
        (0.18, (0.14, 0.025, 0.008)),
        (0.46, (0.48, 0.120, 0.020)),
        (0.74, (0.85, 0.360, 0.060)),
        (0.92, (1.00, 0.760, 0.280)),
    ]
    dens_keys = utils.sample_stage_envelope("hadrons", cfg, fl["shell_density"], rest_val=0.0)
    em_keys = utils.sample_stage_envelope("hadrons", cfg, fl["shell_emission"], rest_val=0.0)
    vol_mat = utils.make_rich_volume_material(
        "Stage4_Hadrons_VolMat",
        inner_r=38.0,
        outer_r=63.5,
        feather=4.5,
        ramp_stops=had_ramp,
        noise_scale=0.10,
        noise_detail=4.0,
        noise_distortion=0.8,
        noise_speed=1.4,
        voronoi_scale=0.14,
        voronoi_mix=0.35,
        anisotropy=0.45,
        emission_power=1.3,
        density_keyframes=dens_keys,
        emission_keyframes=em_keys,
        cfg=cfg,
    )
    utils.create_volume_sphere("Hadrons_Shell_Volume", col, radius=66.0, mat=vol_mat, subdivisions=3, active_frame_range=(246, 352))

    had_alpha = utils.sample_stage_envelope("hadrons", cfg, 0.96, rest_val=0.0)
    q_ramp = [
        (0.0, (1.00, 0.24, 0.02)),
        (0.5, (1.00, 0.78, 0.16)),
        (1.0, (1.00, 0.12, 0.42)),
    ]
    quark_mat = utils.make_plasma_orb_material(
        "Stage4_Quark_Mat",
        core_rgb=(1.0, 0.96, 0.86),
        strength=3.4,
        keyframed_strengths=utils.sample_stage_envelope("hadrons", cfg, 3.4, rest_val=0.0),
        alpha_weights=had_alpha,
        attr_name="quark_id",
        attr_ramp=q_ramp,
        attr_type="INSTANCER",
        power=2.5,
    )
    strut_mat = utils.make_emissive_material(
        "Stage4_GluonStrut_Mat",
        color_rgb=(1.0, 0.56, 0.12),
        strength=1.8,
        keyframed_strengths=utils.sample_stage_envelope("hadrons", cfg, 1.8, rest_val=0.0),
        alpha_weights=utils.sample_stage_envelope("hadrons", cfg, 0.78, rest_val=0.0),
    )
    halo_mat = utils.make_plasma_orb_material(
        "Stage4_ConfinementHalo_Mat",
        core_rgb=(1.0, 0.84, 0.42),
        edge_rgb=(1.0, 0.38, 0.06),
        strength=1.1,
        keyframed_strengths=utils.sample_stage_envelope("hadrons", cfg, 1.1, rest_val=0.0),
        alpha_weights=utils.sample_stage_envelope("hadrons", cfg, 0.20, rest_val=0.0),
        power=3.4,
    )

    centers_mesh = _build_triplet_centers_mesh(
        "Hadrons_Triplet_Centers", cfg, hero_count=fl["hero_triplets"], shell_count=fl["shell_triplets"]
    )
    tri_obj = bpy.data.objects.new("Hadrons_Triplets", centers_mesh)
    tri_obj.visible_shadow = False
    utils.link_to_collection(tri_obj, col)
    for f, hidden in ((1, True), (248, True), (249, False), (348, False), (349, True)):
        tri_obj.hide_render = hidden
        tri_obj.keyframe_insert("hide_render", frame=f)

    mod = tri_obj.modifiers.new("HadronizationGN", "NODES")
    mod.node_group = _build_hadronization_gn("Hadronization_GN", quark_mat, strut_mat, halo_mat=halo_mat)
    return col
