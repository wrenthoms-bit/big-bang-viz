import bpy
from mathutils import Vector
import scene_utils as utils


def _make_emissive_mat(name, color_rgba):
    mat = bpy.data.materials.new(name)
    mat.surface_render_method = "BLENDED"
    nt = mat.node_tree
    nt.nodes.clear()
    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
    n_mix = nt.nodes.new("ShaderNodeMixShader")
    n_trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    n_em = nt.nodes.new("ShaderNodeEmission")
    n_em.inputs["Color"].default_value = (color_rgba[0], color_rgba[1], color_rgba[2], 1.0)
    n_em.inputs["Strength"].default_value = 1.0
    n_mix.inputs["Fac"].default_value = color_rgba[3]

    nt.links.new(n_trans.outputs["BSDF"], n_mix.inputs[1])
    nt.links.new(n_em.outputs["Emission"], n_mix.inputs[2])
    nt.links.new(n_mix.outputs["Shader"], n_out.inputs["Surface"])
    return mat


def _make_backdrop_plate(name, col, w, h, loc, mat):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (w, h, 1.0)
    obj.data.materials.append(mat)
    utils.link_to_collection(obj, col)
    return obj


def _make_text_obj(name, col, body, size, loc, font, mat, align_x="LEFT", align_y="TOP"):
    curve = bpy.data.curves.new(name=name, type="FONT")
    curve.body = body
    curve.size = size
    curve.font = font
    curve.align_x = align_x
    curve.align_y = align_y
    curve.space_line = 1.25
    obj = bpy.data.objects.new(name, curve)
    obj.location = loc
    obj.data.materials.append(mat)
    utils.link_to_collection(obj, col)
    return obj


def build_hud_scene(cfg, mode="scaffold"):
    if "HUD_Scene" in bpy.data.scenes:
        bpy.data.scenes.remove(bpy.data.scenes["HUD_Scene"])

    hud_scene = bpy.data.scenes.new("HUD_Scene")
    hud_scene.frame_start = cfg["timeline"]["frame_start"]
    hud_scene.frame_end = cfg["timeline"]["frame_end"]
    hud_scene.render.fps = cfg["timeline"]["fps"]
    hud_scene.render.engine = "BLENDER_EEVEE"
    hud_scene.render.film_transparent = True
    hud_scene.eevee.taa_render_samples = 16
    hud_scene.eevee.use_raytracing = False
    hud_scene.eevee.use_volumetric_shadows = False
    hud_scene.view_settings.view_transform = "Standard"
    hud_scene.view_settings.look = "None"

    # Clear world light so film_transparent produces pure alpha over HUD cards
    w = bpy.data.worlds.new("HUD_World")
    hud_scene.world = w
    w.node_tree.nodes.clear()
    w.node_tree.nodes.new("ShaderNodeOutputWorld")

    col = bpy.data.collections.new("HUD_Elements")
    hud_scene.collection.children.link(col)

    # 16:9 orthographic plane: X in [-8.0, +8.0], Y in [-4.5, +4.5]
    cam_data = bpy.data.cameras.new("HUD_Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 16.0
    cam_data.clip_start = 0.1
    cam_data.clip_end = 20.0
    cam_data.dof.use_dof = False
    cam_obj = bpy.data.objects.new("HUD_Camera", cam_data)
    cam_obj.location = (0.0, 0.0, 5.0)
    cam_obj.rotation_euler = (0.0, 0.0, 0.0)
    col.objects.link(cam_obj)
    hud_scene.camera = cam_obj

    font_sans = bpy.data.fonts.load(cfg["hud"]["font_sans"], check_existing=True)
    font_mono = bpy.data.fonts.load(cfg["hud"]["font_mono"], check_existing=True)

    mat_bg = _make_emissive_mat("HUD_Plate_Mat", (0.035, 0.042, 0.068, 0.76))
    mat_white = _make_emissive_mat("HUD_White_Mat", (1.0, 1.0, 1.0, 0.98))
    mat_muted = _make_emissive_mat("HUD_Muted_Mat", (0.78, 0.86, 0.96, 0.85))
    mat_caption_bg = _make_emissive_mat("HUD_Caption_Bg_Mat", (0.035, 0.042, 0.068, 0.76))
    mat_caption_txt = _make_emissive_mat("HUD_Caption_Txt_Mat", (0.98, 0.99, 1.0, 0.96))
    mat_stage_bg = _make_emissive_mat("HUD_Stage_Bg_Mat", (0.035, 0.042, 0.068, 0.74))
    mat_stage_meta = _make_emissive_mat("HUD_Stage_Meta_Mat", (0.78, 0.86, 0.96, 0.85))
    mat_stage_title = _make_emissive_mat("HUD_Stage_Title_Mat", (1.0, 1.0, 1.0, 0.99))
    mat_stage_sub = _make_emissive_mat("HUD_Stage_Sub_Mat", (0.92, 0.96, 1.0, 0.94))

    # Top-left telemetry panel
    _make_backdrop_plate("HUD_Telemetry_Bg", col, 5.75, 1.22, (-4.82, 3.56, 0.0), mat_bg)
    _make_text_obj("HUD_Clock_Label", col, "TIME AFTER BIG BANG", 0.165, (-7.42, 3.98, 0.05), font_sans, mat_muted)
    txt_clock = _make_text_obj("HUD_Clock_Value", col, "10⁻⁴³ s", 0.30, (-7.42, 3.64, 0.05), font_mono, mat_white)

    _make_text_obj("HUD_Temp_Label", col, "TEMPERATURE", 0.165, (-4.38, 3.98, 0.05), font_sans, mat_muted)
    txt_temp = _make_text_obj("HUD_Temp_Value", col, "~1.4 × 10³² K", 0.30, (-4.38, 3.64, 0.05), font_mono, mat_white)

    # Top-right opening concept caption (visible f001-f108)
    cap_bg = _make_backdrop_plate("HUD_Caption_Bg", col, 5.95, 1.12, (4.70, 3.62, 0.0), mat_caption_bg)
    txt_cap = _make_text_obj(
        "HUD_Caption_Text",
        col,
        cfg["opening_caption"]["text"],
        0.185,
        (1.92, 3.96, 0.05),
        font_sans,
        mat_caption_txt,
    )

    # Optional scaffold frame/time tag (top-center, cleanly separated from left & right panels)
    txt_scaffold_tag = None
    if mode == "scaffold" and cfg["hud"].get("show_frame_counter_in_scaffold", True):
        _make_backdrop_plate("HUD_Scaffold_Bg", col, 2.75, 0.54, (-0.18, 3.92, 0.0), mat_bg)
        txt_scaffold_tag = _make_text_obj(
            "HUD_Scaffold_Tag",
            col,
            "SCAFFOLD | f001 | 00.00s",
            0.175,
            (-0.18, 4.02, 0.05),
            font_mono,
            mat_white,
            align_x="CENTER",
        )

    # Lower-third stage label
    stg_bg = _make_backdrop_plate("HUD_Stage_Bg", col, 9.2, 1.56, (0.0, -3.38, 0.0), mat_stage_bg)
    txt_stage_meta = _make_text_obj(
        "HUD_Stage_Meta", col, "STAGE 1 / 6   •   ~10⁻⁴³ s", 0.195, (0.0, -2.76, 0.05), font_mono, mat_stage_meta, align_x="CENTER"
    )
    txt_stage_title = _make_text_obj(
        "HUD_Stage_Title", col, "PLANCK ERA", 0.42, (0.0, -3.14, 0.05), font_sans, mat_stage_title, align_x="CENTER"
    )
    txt_stage_sub = _make_text_obj(
        "HUD_Stage_Subtitle", col, "Physics unknown.", 0.225, (0.0, -3.68, 0.05), font_sans, mat_stage_sub, align_x="CENTER"
    )

    if mode != "scaffold":
        # Clean right-aligned caption spacing when no scaffold badge is present
        cap_bg.location = (4.65, 3.62, 0.0)
        cap_bg.scale = (6.15, 1.12, 1.0)
        txt_cap.location = (1.76, 3.96, 0.05)

    # Store references as custom properties / dictionary lookup via update_hud_for_frame
    update_hud_for_frame(hud_scene, cfg, cfg["timeline"]["frame_start"], mode=mode)
    return hud_scene


def _set_mat_alpha(mat, alpha):
    for node in mat.node_tree.nodes:
        if node.type == "MIX_SHADER":
            node.inputs["Fac"].default_value = alpha
            break


def update_hud_for_frame(hud_scene, cfg, frame, mode="scaffold"):
    u = utils.frame_to_seconds(frame, cfg)
    objs = hud_scene.objects

    objs["HUD_Clock_Value"].data.body = utils.get_physical_time(u, cfg)
    objs["HUD_Temp_Value"].data.body = utils.get_temperature(u, cfg)

    if "HUD_Scaffold_Tag" in objs:
        objs["HUD_Scaffold_Tag"].data.body = f"SCAFFOLD | f{frame:03d} | {u:05.2f}s"

    # Opening caption fade
    cap_cfg = cfg["opening_caption"]
    cap_alpha = 1.0 - utils.smoothstep(
        cap_cfg["end_frame"] - cap_cfg["fade_frames"], cap_cfg["end_frame"], frame
    )
    cap_vis = cap_alpha > 0.01
    objs["HUD_Caption_Bg"].hide_render = not cap_vis
    objs["HUD_Caption_Text"].hide_render = not cap_vis
    if cap_vis:
        _set_mat_alpha(bpy.data.materials["HUD_Caption_Bg_Mat"], 0.76 * cap_alpha)
        _set_mat_alpha(bpy.data.materials["HUD_Caption_Txt_Mat"], 0.96 * cap_alpha)

    # Stage label
    active = utils.get_active_stage(u, cfg)
    st = active["stage"]
    op = active["opacity"]
    stg_vis = op > 0.01
    for key in ("HUD_Stage_Bg", "HUD_Stage_Meta", "HUD_Stage_Title", "HUD_Stage_Subtitle"):
        objs[key].hide_render = not stg_vis

    if stg_vis:
        objs["HUD_Stage_Meta"].data.body = f"STAGE {active['index'] + 1} / {len(cfg['stages'])}   •   {st['epoch']}"
        objs["HUD_Stage_Title"].data.body = st["title"]
        objs["HUD_Stage_Subtitle"].data.body = active["subtitle"]
        _set_mat_alpha(bpy.data.materials["HUD_Stage_Bg_Mat"], 0.74 * op)
        _set_mat_alpha(bpy.data.materials["HUD_Stage_Meta_Mat"], 0.85 * op)
        _set_mat_alpha(bpy.data.materials["HUD_Stage_Title_Mat"], 0.99 * op)
        _set_mat_alpha(bpy.data.materials["HUD_Stage_Sub_Mat"], 0.94 * op)
