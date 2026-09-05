from src.schemas import (
    ColorSpace,
    ImageConstraint,
    ImageDType,
    InputKind,
    InputSlotSpec,
)


_UINT8 = [ImageDType.UINT8]
_PHOTO_SPACES = [ColorSpace.BGR, ColorSpace.RGB]
_EDITING_SPACES = [
    ColorSpace.BGR,
    ColorSpace.RGB,
    ColorSpace.BGRA,
    ColorSpace.RGBA,
]


def image_input(
    name: str = "image",
    *,
    color_spaces: list[ColorSpace] | None = None,
    description: str | None = None,
) -> InputSlotSpec:
    return InputSlotSpec(
        name=name,
        kind=InputKind.IMAGE,
        description=description,
        image_constraint=ImageConstraint(
            allowed_color_spaces=color_spaces or [],
            allowed_dtypes=_UINT8,
        ),
    )


def photo_input(name: str = "image") -> InputSlotSpec:
    return image_input(name, color_spaces=_PHOTO_SPACES)


def editing_input(name: str = "image") -> InputSlotSpec:
    return image_input(name, color_spaces=_EDITING_SPACES)


def gray_input(name: str = "image") -> InputSlotSpec:
    return image_input(name, color_spaces=[ColorSpace.GRAY])


def mask_input(name: str = "mask") -> InputSlotSpec:
    return InputSlotSpec(
        name=name,
        kind=InputKind.MASK,
        image_constraint=ImageConstraint(
            allowed_color_spaces=[ColorSpace.GRAY, ColorSpace.BINARY],
            allowed_dtypes=_UINT8,
        ),
    )


def array_input(name: str) -> InputSlotSpec:
    return InputSlotSpec(name=name, kind=InputKind.ARRAY)
