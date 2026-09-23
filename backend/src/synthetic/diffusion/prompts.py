from __future__ import annotations

from dataclasses import dataclass

from ..errors import SyntheticValidationError


_DEFAULT_NEGATIVE_PROMPT = (
    "extra hoses, extra connectors, new objects, hands, tools, text, labels, "
    "changed equipment, missing parts, severe deformation, large rupture, "
    "heavy flooding, large splash, smoke, cartoon, CGI, different camera angle, "
    "different lighting, blurry, low quality"
)


@dataclass(frozen=True, slots=True)
class DiffusionPromptPresetData:
    key: str
    display_name: str
    prompt: str
    negative_prompt: str = _DEFAULT_NEGATIVE_PROMPT


_PROMPT_PRESETS = {
    item.key: item
    for item in [
        DiffusionPromptPresetData(
            key="micro_seepage",
            display_name="Micro seepage",
            prompt=(
                "close-up of an industrial hose connection, very small clear liquid seepage "
                "from the joint, subtle glossy wetness and tiny transparent droplets, realistic "
                "industrial CCTV image, same lighting and camera perspective, localized defect "
                "only, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="small_joint_leak",
            display_name="Small joint leak",
            prompt=(
                "close-up of an industrial hose coupling, a small clear liquid leak coming from "
                "the connection gap, several transparent droplets and subtle reflective wetness "
                "around the joint, same equipment, same lighting and perspective, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="small_pooling",
            display_name="Small liquid pooling",
            prompt=(
                "close-up of an industrial hose connector, a small amount of clear liquid "
                "accumulated around the base of the connection, shallow glossy pooling with "
                "realistic reflections, same lighting and camera perspective, localized defect "
                "only, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="hairline_tear",
            display_name="Hairline tear",
            prompt=(
                "close-up of a flexible industrial hose near its connector, a very small hairline "
                "tear in the hose surface, subtle material separation, same hose shape and "
                "surrounding equipment, realistic CCTV lighting, localized defect only, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="tear_with_seepage",
            display_name="Tear with seepage",
            prompt=(
                "close-up of a flexible hose near a metal connector, a slight tear in the hose with "
                "clear liquid slowly seeping from the damaged area, subtle glossy wetness around "
                "the tear, realistic industrial CCTV image, localized defect only, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="tear_with_pooling",
            display_name="Tear with pooling",
            prompt=(
                "close-up of an industrial hose joint, a small tear near the connection and clear "
                "liquid accumulating below the damaged area, shallow reflective pooling and subtle "
                "droplets, same equipment and lighting, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="forming_droplet",
            display_name="Forming droplet",
            prompt=(
                "close-up of an industrial hose connection, one small transparent liquid droplet "
                "forming at the lower edge of the joint, realistic glossy reflection, same lighting "
                "and camera perspective, localized change only, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="downward_drip",
            display_name="Downward drip",
            prompt=(
                "close-up of an industrial hose coupling, a thin clear liquid leak running downward "
                "from the connection with a few small droplets, subtle wet trail and realistic "
                "reflections, same equipment and perspective, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="wet_halo",
            display_name="Wet halo",
            prompt=(
                "close-up of a hose connector in industrial equipment, subtle clear liquid wetness "
                "spreading locally around the connection, a thin glossy wet halo with faint "
                "reflections, no major deformation, same lighting and perspective, photorealistic"
            ),
        ),
        DiffusionPromptPresetData(
            key="small_pressure_leak",
            display_name="Small pressure leak",
            prompt=(
                "close-up of an industrial hose connection, a tiny narrow stream of clear liquid "
                "escaping from a small gap in the joint, localized fine spray and wet reflection "
                "near the connection only, same equipment and camera perspective, photorealistic"
            ),
        ),
    ]
}


def list_prompt_presets() -> list[DiffusionPromptPresetData]:
    return list(_PROMPT_PRESETS.values())


def resolve_prompt_preset(key: str) -> DiffusionPromptPresetData:
    try:
        return _PROMPT_PRESETS[key]
    except KeyError as exc:
        raise SyntheticValidationError(
            f"unknown diffusion prompt preset '{key}'; choose one of {sorted(_PROMPT_PRESETS)}"
        ) from exc
