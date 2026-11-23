import bpy
import scene_utils as utils


def _build_planck_foam_gn(name, mat, density_val=0.85, radius_sphere=6.2, point_radius=0.09, subdiv=1):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")

    n_sphere = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_sphere.inputs["Radius"].default_value = radius_sphere
    n_sphere.inputs["Subdivisions"].default_value = 3

    n_m2v = ng.nodes.new("GeometryNodeMeshToVolume")
    n_m2v.inputs["Voxel Amount"].default_value = 28.0
    n_m2v.inputs["Density"].default_value = 1.0

    n_dist = ng.nodes.new("GeometryNodeDistributePointsInVolume")
    n_dist.inputs["Density"].default_value = density_val
    n_dist.inputs["Seed"].default_value = 11

    n_time = ng.nodes.new("GeometryNodeInputSceneTime")
    n_pos = ng.nodes.new("GeometryNodeInputPosition")

    n_noise = ng.nodes.new("ShaderNodeTexNoise")
    n_noise.noise_dimensions = "4D"
    n_noise.inputs["Scale"].default_value = 0.45
    n_noise.inputs["Detail"].default_value = 2.0

    n_tscale = ng.nodes.new("ShaderNodeMath")
    n_tscale.operation = "MULTIPLY"
    n_tscale.inputs[1].default_value = 1.8

    n_vsub = ng.nodes.new("ShaderNodeVectorMath")
    n_vsub.operation = "SUBTRACT"
    n_vsub.inputs[1].default_value = (0.5, 0.5, 0.5)

    n_vscale = ng.nodes.new("ShaderNodeVectorMath")
    n_vscale.operation = "SCALE"
    n_vscale.inputs["Scale"].default_value = 1.6

    n_setpos = ng.nodes.new("GeometryNodeSetPosition")

    n_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_ico.inputs["Radius"].default_value = point_radius
    n_ico.inputs["Subdivisions"].default_value = subdiv

    n_flicker = ng.nodes.new("ShaderNodeMapRange")
    n_flicker.inputs["From Min"].default_value = 0.36
    n_flicker.inputs["From Max"].default_value = 0.72
    n_flicker.inputs["To Min"].default_value = 0.0
    n_flicker.inputs["To Max"].default_value = 1.45

    n_inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_setmat = ng.nodes.new("GeometryNodeSetMaterial")
    n_setmat.inputs["Material"].default_value = mat

    ng.links.new(n_sphere.outputs["Mesh"], n_m2v.inputs["Mesh"])
    ng.links.new(n_m2v.outputs["Volume"], n_dist.inputs["Volume"])
    ng.links.new(n_time.outputs["Seconds"], n_tscale.inputs[0])
    ng.links.new(n_pos.outputs["Position"], n_noise.inputs["Vector"])
    ng.links.new(n_tscale.outputs["Value"], n_noise.inputs["W"])
    ng.links.new(n_noise.outputs["Color"], n_vsub.inputs[0])
    ng.links.new(n_vsub.outputs["Vector"], n_vscale.inputs[0])
    ng.links.new(n_dist.outputs["Points"], n_setpos.inputs["Geometry"])
    ng.links.new(n_vscale.outputs["Vector"], n_setpos.inputs["Offset"])
    ng.links.new(n_noise.outputs["Fac"], n_flicker.inputs["Value"])
    ng.links.new(n_setpos.outputs["Geometry"], n_inst.inputs["Points"])
    ng.links.new(utils.add_shade_smooth(ng, n_ico.outputs["Mesh"]), n_inst.inputs["Instance"])
    ng.links.new(n_flicker.outputs["Result"], n_inst.inputs["Scale"])
    ng.links.new(n_inst.outputs["Instances"], n_setmat.inputs["Geometry"])
    ng.links.new(n_setmat.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def build(scene, cfg, mode="scaffold"):
    col = utils.ensure_collection("Stage_1_Planck")

    if mode == "scaffold":
        sg = cfg["scaffold_greys"]
        dens_keys = utils.sample_stage_envelope("planck", cfg, sg["planck_shell_density"], rest_val=0.008)
        em_keys = utils.sample_stage_envelope("planck", cfg, sg["planck_core_emission"], rest_val=0.06)

        vol_mat = utils.make_shell_volume_material(
            "Stage1_Planck_VolMat",
            inner_r=0.0,
            outer_r=5.2,
            feather=2.0,
            base_color=(0.62, 0.62, 0.64),
            hot_color=(0.95, 0.95, 0.98),
            noise_scale=0.45,
            noise_detail=5.0,
            noise_distortion=1.1,
            noise_speed=2.6,
            density_keyframes=dens_keys,
            emission_keyframes=em_keys,
            cfg=cfg,
        )
        utils.create_volume_sphere("Planck_Core_Volume", col, radius=6.8, mat=vol_mat, subdivisions=3)

        foam_alpha = utils.sample_stage_envelope("planck", cfg, 1.0, rest_val=0.0)
        foam_strengths = utils.sample_stage_envelope("planck", cfg, 2.2, rest_val=0.0)
        foam_mat = utils.make_emissive_material(
            "Stage1_Planck_FoamMat",
            color_rgb=(0.94, 0.94, 0.98),
            strength=2.0,
            keyframed_strengths=foam_strengths,
            alpha_weights=foam_alpha,
        )
        mesh = bpy.data.meshes.new("Planck_Foam_Mesh")
        foam_obj = bpy.data.objects.new("Planck_Quantum_Foam", mesh)
        foam_obj.visible_shadow = False
        utils.link_to_collection(foam_obj, col)
        for f, hidden in ((1, False), (74, False), (75, True)):
            foam_obj.hide_render = hidden
            foam_obj.keyframe_insert("hide_render", frame=f)

        mod = foam_obj.modifiers.new("QuantumFoamGN", "NODES")
        mod.node_group = _build_planck_foam_gn("Planck_Foam_GN", foam_mat, density_val=0.85, radius_sphere=6.2, point_radius=0.09, subdiv=1)
        return col

    # Full cinematic look-development mode
    fl = cfg["full_look"]["planck"]

    # 1. Incandescent Inner Planck Core (blinding blue-white heart inside sapphire plasma)
    core_ramp = [
        (0.14, (0.03, 0.12, 0.64)),
        (0.42, (0.12, 0.44, 0.96)),
        (0.68, (0.56, 0.85, 1.00)),
        (0.88, (1.00, 1.00, 1.00)),
    ]
    core_dens = utils.sample_stage_envelope("planck", cfg, fl["core_density"], rest_val=0.0)
    core_em = utils.sample_stage_envelope("planck", cfg, fl["core_emission"], rest_val=0.0)
    core_mat = utils.make_rich_volume_material(
        "Stage1_Planck_CoreVolMat",
        inner_r=0.0,
        outer_r=3.6,
        feather=1.6,
        ramp_stops=core_ramp,
        noise_scale=0.52,
        noise_detail=4.0,
        noise_distortion=1.4,
        noise_speed=2.6,
        voronoi_scale=0.65,
        voronoi_mix=0.28,
        anisotropy=0.45,
        emission_power=1.45,
        density_keyframes=core_dens,
        emission_keyframes=core_em,
        cfg=cfg,
    )
    utils.create_volume_sphere("Planck_Core_Volume", col, radius=4.8, mat=core_mat, subdivisions=3, active_frame_range=(1, 175))

    # 2. Outer Turbulent Sapphire-Cyan Corona
    corona_ramp = [
        (0.18, (0.012, 0.045, 0.30)),
        (0.50, (0.060, 0.220, 0.78)),
        (0.76, (0.240, 0.620, 1.00)),
        (0.94, (0.780, 0.920, 1.00)),
    ]
    cor_dens = utils.sample_stage_envelope("planck", cfg, fl["corona_density"], rest_val=0.0)
    cor_em = utils.sample_stage_envelope("planck", cfg, fl["corona_emission"], rest_val=0.0)
    corona_mat = utils.make_rich_volume_material(
        "Stage1_Planck_CoronaVolMat",
        inner_r=2.0,
        outer_r=11.5,
        feather=3.2,
        ramp_stops=corona_ramp,
        noise_scale=0.22,
        noise_detail=4.0,
        noise_distortion=1.2,
        noise_speed=2.1,
        voronoi_scale=0.30,
        voronoi_mix=0.32,
        anisotropy=0.50,
        emission_power=1.35,
        density_keyframes=cor_dens,
        emission_keyframes=cor_em,
        cfg=cfg,
    )
    utils.create_volume_sphere("Planck_Corona_Volume", col, radius=13.0, mat=corona_mat, subdivisions=3, active_frame_range=(1, 175))

    # 3. Soft Fresnel Plasma Sparks (Quantum Foam)
    foam_alpha = utils.sample_stage_envelope("planck", cfg, 0.92, rest_val=0.0)
    foam_strengths = utils.sample_stage_envelope("planck", cfg, 2.6, rest_val=0.0)
    foam_mat = utils.make_plasma_orb_material(
        "Stage1_Planck_FoamMat",
        core_rgb=(1.0, 1.0, 1.0),
        edge_rgb=(0.14, 0.60, 1.0),
        strength=2.6,
        keyframed_strengths=foam_strengths,
        alpha_weights=foam_alpha,
        power=2.6,
    )
    mesh = bpy.data.meshes.new("Planck_Foam_Mesh")
    foam_obj = bpy.data.objects.new("Planck_Quantum_Foam", mesh)
    foam_obj.visible_shadow = False
    utils.link_to_collection(foam_obj, col)
    for f, hidden in ((1, False), (74, False), (75, True)):
        foam_obj.hide_render = hidden
        foam_obj.keyframe_insert("hide_render", frame=f)

    mod = foam_obj.modifiers.new("QuantumFoamGN", "NODES")
    mod.node_group = _build_planck_foam_gn(
        "Planck_Foam_GN",
        foam_mat,
        density_val=fl["foam_count_density"],
        radius_sphere=7.2,
        point_radius=0.075,
        subdiv=2,
    )
    return col
