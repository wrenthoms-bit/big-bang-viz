import bpy
import math
import scene_utils as utils


def _build_lattice_mesh(name, grid_n=6, spacing=3.8):
    mesh = bpy.data.meshes.new(name)
    verts = []
    edges = []
    half = ((grid_n - 1) * spacing) * 0.5

    def vidx(ix, iy, iz):
        return (ix * grid_n + iy) * grid_n + iz

    for ix in range(grid_n):
        for iy in range(grid_n):
            for iz in range(grid_n):
                verts.append((ix * spacing - half, iy * spacing - half, iz * spacing - half))

    for ix in range(grid_n):
        for iy in range(grid_n):
            for iz in range(grid_n):
                cur = vidx(ix, iy, iz)
                if ix < grid_n - 1:
                    edges.append((cur, vidx(ix + 1, iy, iz)))
                if iy < grid_n - 1:
                    edges.append((cur, vidx(ix, iy + 1, iz)))
                if iz < grid_n - 1:
                    edges.append((cur, vidx(ix, iy, iz + 1)))

    mesh.from_pydata(verts, edges, [])
    mesh.update()
    return mesh


def _build_inflation_lattice_gn(name, beam_mat, node_mat, cfg, resample_count=6, beam_rad=0.045, node_rad=0.14, node_subdiv=1):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n_in = ng.nodes.new("NodeGroupInput")
    n_out = ng.nodes.new("NodeGroupOutput")

    n_pos = ng.nodes.new("GeometryNodeInputPosition")
    n_time = ng.nodes.new("GeometryNodeInputSceneTime")

    # Freeze temporal phase evolution after u ~ 3.2s so quantum ripples lock into stretched space
    n_freeze = ng.nodes.new("ShaderNodeMapRange")
    n_freeze.inputs["From Min"].default_value = 2.0
    n_freeze.inputs["From Max"].default_value = 3.8
    n_freeze.inputs["To Min"].default_value = 1.0
    n_freeze.inputs["To Max"].default_value = 0.08

    n_w_mul = ng.nodes.new("ShaderNodeMath")
    n_w_mul.operation = "MULTIPLY"

    n_noise = ng.nodes.new("ShaderNodeTexNoise")
    n_noise.noise_dimensions = "4D"
    n_noise.inputs["Scale"].default_value = 0.22
    n_noise.inputs["Detail"].default_value = 2.0

    n_sub = ng.nodes.new("ShaderNodeVectorMath")
    n_sub.operation = "SUBTRACT"
    n_sub.inputs[1].default_value = (0.5, 0.5, 0.5)

    n_disp_scale = ng.nodes.new("ShaderNodeVectorMath")
    n_disp_scale.operation = "SCALE"
    n_disp_scale.inputs["Scale"].default_value = 1.45

    n_setpos = ng.nodes.new("GeometryNodeSetPosition")

    # Store ripple_crest on points BEFORE CurveToMesh so shaders modulate cyan -> violet-white crests
    n_store = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    n_store.domain = "POINT"
    n_store.data_type = "FLOAT"
    n_store.inputs["Name"].default_value = "ripple_crest"

    # Convert edges to subdivided curved beams so ripples bend smoothly along each grid line
    n_m2c = ng.nodes.new("GeometryNodeMeshToCurve")
    n_res = ng.nodes.new("GeometryNodeResampleCurve")
    n_res.inputs["Count"].default_value = resample_count

    n_prof = ng.nodes.new("GeometryNodeCurvePrimitiveCircle")
    n_prof.inputs["Resolution"].default_value = 5
    n_prof.inputs["Radius"].default_value = beam_rad

    n_c2m = ng.nodes.new("GeometryNodeCurveToMesh")
    n_c2m.inputs["Fill Caps"].default_value = False

    n_mat_beam = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat_beam.inputs["Material"].default_value = beam_mat

    # Glowing nodes at lattice intersections
    n_node_ico = ng.nodes.new("GeometryNodeMeshIcoSphere")
    n_node_ico.inputs["Radius"].default_value = node_rad
    n_node_ico.inputs["Subdivisions"].default_value = node_subdiv

    n_inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
    n_mat_node = ng.nodes.new("GeometryNodeSetMaterial")
    n_mat_node.inputs["Material"].default_value = node_mat

    n_join = ng.nodes.new("GeometryNodeJoinGeometry")

    ng.links.new(n_time.outputs["Seconds"], n_freeze.inputs["Value"])
    ng.links.new(n_time.outputs["Seconds"], n_w_mul.inputs[0])
    ng.links.new(n_freeze.outputs["Result"], n_w_mul.inputs[1])

    ng.links.new(n_pos.outputs["Position"], n_noise.inputs["Vector"])
    ng.links.new(n_w_mul.outputs["Value"], n_noise.inputs["W"])
    ng.links.new(n_noise.outputs["Color"], n_sub.inputs[0])
    ng.links.new(n_sub.outputs["Vector"], n_disp_scale.inputs[0])

    # Evaluate ripple displacement AFTER resampling curves so every curve bends organically
    ng.links.new(n_in.outputs["Geometry"], n_m2c.inputs["Mesh"])
    ng.links.new(n_m2c.outputs["Curve"], n_res.inputs["Curve"])
    ng.links.new(n_res.outputs["Curve"], n_setpos.inputs["Geometry"])
    ng.links.new(n_disp_scale.outputs["Vector"], n_setpos.inputs["Offset"])

    ng.links.new(n_setpos.outputs["Geometry"], n_store.inputs["Geometry"])
    ng.links.new(n_noise.outputs["Fac"], n_store.inputs["Value"])

    ng.links.new(n_store.outputs["Geometry"], n_c2m.inputs["Curve"])
    ng.links.new(n_prof.outputs["Curve"], n_c2m.inputs["Profile Curve"])
    ng.links.new(utils.add_shade_smooth(ng, n_c2m.outputs["Mesh"]), n_mat_beam.inputs["Geometry"])

    # Also apply same displacement & crest attribute to original vertex nodes
    n_setpos_pts = ng.nodes.new("GeometryNodeSetPosition")
    n_store_pts = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    n_store_pts.domain = "POINT"
    n_store_pts.data_type = "FLOAT"
    n_store_pts.inputs["Name"].default_value = "ripple_crest"

    ng.links.new(n_in.outputs["Geometry"], n_setpos_pts.inputs["Geometry"])
    ng.links.new(n_disp_scale.outputs["Vector"], n_setpos_pts.inputs["Offset"])
    ng.links.new(n_setpos_pts.outputs["Geometry"], n_store_pts.inputs["Geometry"])
    ng.links.new(n_noise.outputs["Fac"], n_store_pts.inputs["Value"])

    ng.links.new(n_store_pts.outputs["Geometry"], n_inst.inputs["Points"])
    ng.links.new(utils.add_shade_smooth(ng, n_node_ico.outputs["Mesh"]), n_inst.inputs["Instance"])
    ng.links.new(n_inst.outputs["Instances"], n_mat_node.inputs["Geometry"])

    ng.links.new(n_mat_beam.outputs["Geometry"], n_join.inputs["Geometry"])
    ng.links.new(n_mat_node.outputs["Geometry"], n_join.inputs["Geometry"])
    ng.links.new(n_join.outputs["Geometry"], n_out.inputs["Geometry"])
    return ng


def build(scene, cfg, mode="scaffold"):
    col = utils.ensure_collection("Stage_2_Inflation")

    if mode == "scaffold":
        sg = cfg["scaffold_greys"]
        dens_keys = utils.sample_stage_envelope("inflation", cfg, sg["inflation_density"], rest_val=0.0)
        em_keys = utils.sample_stage_envelope("inflation", cfg, sg["inflation_emission"], rest_val=0.0)

        vol_mat = utils.make_shell_volume_material(
            "Stage2_Inflation_VolMat",
            inner_r=5.5,
            outer_r=24.5,
            feather=3.0,
            base_color=(0.38, 0.38, 0.40),
            hot_color=(0.72, 0.72, 0.76),
            noise_scale=0.18,
            noise_detail=4.0,
            noise_distortion=0.45,
            noise_speed=0.9,
            density_keyframes=dens_keys,
            emission_keyframes=em_keys,
            cfg=cfg,
        )
        utils.create_volume_sphere("Inflation_Shell_Volume", col, radius=26.5, mat=vol_mat, subdivisions=3)

        inf_alpha = utils.sample_stage_envelope("inflation", cfg, 1.0, rest_val=0.0)
        beam_mat = utils.make_emissive_material(
            "Stage2_Lattice_BeamMat",
            color_rgb=(0.82, 0.82, 0.86),
            strength=1.4,
            keyframed_strengths=utils.sample_stage_envelope("inflation", cfg, 1.6, rest_val=0.0),
            alpha_weights=inf_alpha,
        )
        node_mat = utils.make_emissive_material(
            "Stage2_Lattice_NodeMat",
            color_rgb=(0.96, 0.96, 1.0),
            strength=2.2,
            keyframed_strengths=utils.sample_stage_envelope("inflation", cfg, 2.4, rest_val=0.0),
            alpha_weights=inf_alpha,
        )
        gn_group = _build_inflation_lattice_gn("Inflation_Lattice_GN", beam_mat, node_mat, cfg)
        octaves = (0.55, 1.15)
        grid_n, spacing = 6, 4.2
    else:
        fl = cfg["full_look"]["inflation"]
        shell_ramp = [
            (0.18, (0.012, 0.035, 0.20)),
            (0.48, (0.040, 0.140, 0.56)),
            (0.74, (0.120, 0.400, 0.90)),
            (0.92, (0.480, 0.360, 0.95)),
        ]
        dens_keys = utils.sample_stage_envelope("inflation", cfg, fl["shell_density"], rest_val=0.0)
        em_keys = utils.sample_stage_envelope("inflation", cfg, fl["shell_emission"], rest_val=0.0)
        vol_mat = utils.make_rich_volume_material(
            "Stage2_Inflation_VolMat",
            inner_r=5.5,
            outer_r=26.0,
            feather=3.5,
            ramp_stops=shell_ramp,
            noise_scale=0.14,
            noise_detail=4.0,
            noise_distortion=0.5,
            noise_speed=0.75,
            voronoi_scale=0.16,
            voronoi_mix=0.35,
            anisotropy=0.45,
            emission_power=1.3,
            density_keyframes=dens_keys,
            emission_keyframes=em_keys,
            cfg=cfg,
        )
        utils.create_volume_sphere("Inflation_Shell_Volume", col, radius=28.0, mat=vol_mat, subdivisions=3, active_frame_range=(34, 172))

        inf_alpha = utils.sample_stage_envelope("inflation", cfg, 0.90, rest_val=0.0)
        crest_ramp = [
            (0.28, (0.06, 0.48, 1.00)),
            (0.55, (0.28, 0.78, 1.00)),
            (0.74, (0.76, 0.78, 1.00)),
            (0.88, (0.90, 0.42, 1.00)),
        ]
        beam_mat = utils.make_emissive_material(
            "Stage2_Lattice_BeamMat",
            strength=fl["beam_emission"],
            keyframed_strengths=utils.sample_stage_envelope("inflation", cfg, fl["beam_emission"], rest_val=0.0),
            alpha_weights=inf_alpha,
            attr_name="ripple_crest",
            attr_ramp=crest_ramp,
            attr_type="GEOMETRY",
        )
        node_mat = utils.make_plasma_orb_material(
            "Stage2_Lattice_NodeMat",
            core_rgb=(1.0, 0.98, 1.0),
            strength=fl["node_emission"],
            keyframed_strengths=utils.sample_stage_envelope("inflation", cfg, fl["node_emission"], rest_val=0.0),
            alpha_weights=inf_alpha,
            attr_name="ripple_crest",
            attr_ramp=crest_ramp,
            attr_type="INSTANCER",
            power=2.4,
        )
        gn_group = _build_inflation_lattice_gn(
            "Inflation_Lattice_GN", beam_mat, node_mat, cfg, resample_count=10, beam_rad=0.022, node_rad=0.11, node_subdiv=2
        )
        octaves = (0.38, 0.72, 1.25)
        grid_n, spacing = 7, 3.8

    for oct_idx, scale_mult in enumerate(octaves):
        mesh = _build_lattice_mesh(f"Inflation_Lattice_Mesh_{oct_idx}", grid_n=grid_n, spacing=spacing)
        obj = bpy.data.objects.new(f"Inflation_Lattice_{oct_idx}", mesh)
        obj.visible_shadow = False
        utils.link_to_collection(obj, col)

        mod = obj.modifiers.new("InflationGN", "NODES")
        mod.node_group = gn_group

        for f, hidden in ((1, True), (35, True), (36, False), (165, False), (166, True)):
            obj.hide_render = hidden
            obj.keyframe_insert("hide_render", frame=f)

        for f in range(36, 169, 6):
            t = max(0.0, (f - 42) / 102.0)
            s = scale_mult * math.pow(2.0, t * 1.85)
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)
        utils.set_fcurve_interpolation(obj, "BEZIER")

    return col
