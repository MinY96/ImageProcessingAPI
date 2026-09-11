from src.pipeline.references import pipeline_input, step_output
from src.schemas import PipelineSpec, PipelineStepSpec

from .common import array_input, editing_input, photo_input


def create_editing_recipes() -> list[PipelineSpec]:
    return [
        PipelineSpec(
            name="natural_enhance",
            display_name="Natural Enhance",
            description="경계를 보존하며 디테일, 명암과 색감을 자연스럽게 개선합니다.",
            inputs=[photo_input()],
            steps=[
                PipelineStepSpec(
                    id="smooth",
                    operation="edge_preserving_filter",
                    inputs={"image": pipeline_input("image")},
                    params={"method": "recursive", "sigma_s": 45.0, "sigma_r": 0.35},
                ),
                PipelineStepSpec(
                    id="detail",
                    operation="detail_enhance",
                    inputs={"image": step_output("smooth")},
                    params={"sigma_s": 8.0, "sigma_r": 0.12},
                ),
                PipelineStepSpec(
                    id="tone",
                    operation="adjust_tone",
                    inputs={"image": step_output("detail")},
                    params={"exposure": 0.1, "contrast": 1.06, "brightness": 0.01},
                ),
                PipelineStepSpec(
                    id="color",
                    operation="adjust_color",
                    inputs={"image": step_output("tone")},
                    params={"saturation": 1.02, "vibrance": 0.15},
                ),
            ],
            outputs={"image": step_output("color")},
        ),
        PipelineSpec(
            name="film_look",
            display_name="Film Look",
            description="부드러운 명암, 따뜻한 색감, vignette와 grain을 적용합니다.",
            inputs=[editing_input()],
            steps=[
                PipelineStepSpec(
                    id="tone",
                    operation="adjust_tone",
                    inputs={"image": pipeline_input("image")},
                    params={"contrast": 0.9, "brightness": 0.04, "gamma": 0.95},
                ),
                PipelineStepSpec(
                    id="color",
                    operation="adjust_color",
                    inputs={"image": step_output("tone")},
                    params={"saturation": 0.9, "vibrance": 0.15, "temperature": 0.12},
                ),
                PipelineStepSpec(
                    id="vignette",
                    operation="vignette",
                    inputs={"image": step_output("color")},
                    params={"strength": 0.35, "radius": 0.9, "softness": 0.6},
                ),
                PipelineStepSpec(
                    id="grain",
                    operation="add_grain",
                    inputs={"image": step_output("vignette")},
                    params={"amount": 0.03, "grain_size": 2, "random_seed": 42},
                ),
            ],
            outputs={"image": step_output("grain")},
        ),
        PipelineSpec(
            name="cinematic_3d_lut",
            display_name="Cinematic 3D LUT",
            description="명암과 색상을 보정한 뒤 외부 RGB 3D LUT를 적용합니다.",
            inputs=[editing_input(), array_input("lut")],
            steps=[
                PipelineStepSpec(
                    id="tone",
                    operation="adjust_tone",
                    inputs={"image": pipeline_input("image")},
                    params={"contrast": 1.08, "brightness": -0.01, "gamma": 0.95},
                ),
                PipelineStepSpec(
                    id="color",
                    operation="adjust_color",
                    inputs={"image": step_output("tone")},
                    params={"saturation": 0.92, "vibrance": 0.1},
                ),
                PipelineStepSpec(
                    id="lut",
                    operation="apply_3d_lut",
                    inputs={"image": step_output("color"), "lut": pipeline_input("lut")},
                    params={"interpolation": "trilinear", "intensity": 0.75},
                ),
                PipelineStepSpec(
                    id="vignette",
                    operation="vignette",
                    inputs={"image": step_output("lut")},
                    params={"strength": 0.25, "radius": 0.95, "softness": 0.65},
                ),
                PipelineStepSpec(
                    id="grain",
                    operation="add_grain",
                    inputs={"image": step_output("vignette")},
                    params={"amount": 0.02, "grain_size": 2, "random_seed": 42},
                ),
            ],
            outputs={"image": step_output("grain")},
        ),
        PipelineSpec(
            name="vintage_1d_lut",
            display_name="Vintage 1D LUT",
            description="저대비 warm tone과 외부 1D LUT로 빈티지 색감을 만듭니다.",
            inputs=[editing_input(), array_input("lut")],
            steps=[
                PipelineStepSpec(
                    id="tone",
                    operation="adjust_tone",
                    inputs={"image": pipeline_input("image")},
                    params={"contrast": 0.82, "brightness": 0.06, "gamma": 1.05},
                ),
                PipelineStepSpec(
                    id="color",
                    operation="adjust_color",
                    inputs={"image": step_output("tone")},
                    params={
                        "hue_shift": -5.0,
                        "saturation": 0.78,
                        "vibrance": -0.1,
                        "temperature": 0.18,
                        "tint": 0.05,
                    },
                ),
                PipelineStepSpec(
                    id="lut",
                    operation="apply_lut",
                    inputs={"image": step_output("color"), "lut": pipeline_input("lut")},
                    params={"intensity": 0.65},
                ),
                PipelineStepSpec(
                    id="vignette",
                    operation="vignette",
                    inputs={"image": step_output("lut")},
                    params={"strength": 0.25, "radius": 0.9},
                ),
                PipelineStepSpec(
                    id="grain",
                    operation="add_grain",
                    inputs={"image": step_output("vignette")},
                    params={"amount": 0.04, "grain_size": 2, "random_seed": 42},
                ),
            ],
            outputs={"image": step_output("grain")},
        ),
        PipelineSpec(
            name="clean_portrait",
            display_name="Clean Portrait",
            description="경계 보존 평활화와 절제된 색·명암 보정을 적용합니다.",
            inputs=[photo_input()],
            steps=[
                PipelineStepSpec(
                    id="smooth",
                    operation="edge_preserving_filter",
                    inputs={"image": pipeline_input("image")},
                    params={"method": "recursive", "sigma_s": 50.0, "sigma_r": 0.35},
                ),
                PipelineStepSpec(
                    id="tone",
                    operation="adjust_tone",
                    inputs={"image": step_output("smooth")},
                    params={"exposure": 0.15, "contrast": 1.05, "brightness": 0.02},
                ),
                PipelineStepSpec(
                    id="color",
                    operation="adjust_color",
                    inputs={"image": step_output("tone")},
                    params={"vibrance": 0.2, "temperature": 0.08, "tint": 0.03},
                ),
                PipelineStepSpec(
                    id="vignette",
                    operation="vignette",
                    inputs={"image": step_output("color")},
                    params={"strength": 0.15, "radius": 1.05, "softness": 0.7},
                ),
            ],
            outputs={"image": step_output("vignette")},
        ),
        PipelineSpec(
            name="comic_style",
            display_name="Comic Style",
            description="경계를 보존하고 색상을 단순화한 뒤 stylization을 적용합니다.",
            inputs=[photo_input()],
            steps=[
                PipelineStepSpec(
                    id="smooth",
                    operation="edge_preserving_filter",
                    inputs={"image": pipeline_input("image")},
                    params={"method": "normalized", "sigma_s": 40.0, "sigma_r": 0.3},
                ),
                PipelineStepSpec(
                    id="quantize",
                    operation="color_quantization",
                    inputs={"image": step_output("smooth")},
                    params={"colors": 8, "sample_size": 50_000, "attempts": 2},
                ),
                PipelineStepSpec(
                    id="stylize",
                    operation="stylization",
                    inputs={"image": step_output("quantize", "image")},
                    params={"sigma_s": 55.0, "sigma_r": 0.4},
                ),
            ],
            outputs={"image": step_output("stylize")},
        ),
        PipelineSpec(
            name="pencil_sketch",
            display_name="Pencil Sketch",
            description="노이즈를 완화하고 흑백·컬러 연필 스케치를 함께 반환합니다.",
            inputs=[photo_input()],
            steps=[
                PipelineStepSpec(
                    id="smooth",
                    operation="edge_preserving_filter",
                    inputs={"image": pipeline_input("image")},
                    params={"method": "recursive", "sigma_s": 35.0, "sigma_r": 0.25},
                ),
                PipelineStepSpec(
                    id="sketch",
                    operation="pencil_sketch",
                    inputs={"image": step_output("smooth")},
                    params={"sigma_s": 60.0, "sigma_r": 0.07, "shade_factor": 0.02},
                ),
            ],
            outputs={
                "gray": step_output("sketch", "gray"),
                "color": step_output("sketch", "color"),
            },
        ),
        PipelineSpec(
            name="dramatic_detail",
            display_name="Dramatic Detail",
            description="디테일과 대비, vibrance를 강하게 강조합니다.",
            inputs=[photo_input()],
            steps=[
                PipelineStepSpec(
                    id="detail",
                    operation="detail_enhance",
                    inputs={"image": pipeline_input("image")},
                    params={"sigma_s": 12.0, "sigma_r": 0.2},
                ),
                PipelineStepSpec(
                    id="tone",
                    operation="adjust_tone",
                    inputs={"image": step_output("detail")},
                    params={"contrast": 1.25, "brightness": -0.01, "gamma": 0.9},
                ),
                PipelineStepSpec(
                    id="color",
                    operation="adjust_color",
                    inputs={"image": step_output("tone")},
                    params={"saturation": 1.05, "vibrance": 0.35},
                ),
                PipelineStepSpec(
                    id="vignette",
                    operation="vignette",
                    inputs={"image": step_output("color")},
                    params={"strength": 0.25, "radius": 0.9},
                ),
            ],
            outputs={"image": step_output("vignette")},
        ),
    ]
