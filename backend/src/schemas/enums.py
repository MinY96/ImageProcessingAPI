# src/schemas/enums.py

from enum import StrEnum


class ParameterType(StrEnum):
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    CATEGORY = "category"


class ConstraintType(StrEnum):
    LESS_THAN = "less_than"
    LESS_THAN_EQUAL = "less_than_equal"

    GREATER_THAN = "greater_than"
    GREATER_THAN_EQUAL = "greater_than_equal"

    MUTUALLY_EXCLUSIVE = "mutually_exclusive"
    REQUIRE_TOGETHER = "require_together"
    EXACTLY_ONE_GROUP = "exactly_one_group"
    CONDITIONAL_REQUIRED = "conditional_required"


class PipelineReferenceType(StrEnum):
    PIPELINE_INPUT = "pipeline_input"
    STEP_OUTPUT = "step_output"


class ColorSpace(StrEnum):
    GRAY = "gray"
    BINARY = "binary"

    BGR = "bgr"
    RGB = "rgb"

    HSV = "hsv"
    LAB = "lab"

    BGRA = "bgra"
    RGBA = "rgba"

    UNKNOWN = "unknown"


class ImageDType(StrEnum):
    UINT8 = "uint8"
    UINT16 = "uint16"

    INT16 = "int16"
    INT32 = "int32"

    FLOAT32 = "float32"
    FLOAT64 = "float64"


class OperationCategory(StrEnum):
    ADJUSTMENT = "adjustment"
    ANNOTATION = "annotation"
    COLOR = "color"
    CLASSIFICATION = "classification"
    COMPOSITING = "compositing"
    GEOMETRY = "geometry"

    THRESHOLD = "threshold"
    FILTERING = "filtering"
    MORPHOLOGY = "morphology"

    GRADIENT = "gradient"
    EDGE = "edge"

    CONTOUR = "contour"
    HISTOGRAM = "histogram"

    TRANSFORM = "transform"
    MATCHING = "matching"
    FEATURE = "feature"
    REGISTRATION = "registration"
    EFFECTS = "effects"

    DETECTION = "detection"
    SEGMENTATION = "segmentation"


class InputKind(StrEnum):
    IMAGE = "image"
    MASK = "mask"
    TEMPLATE = "template"

    MARKERS = "markers"
    CONTOURS = "contours"
    POINTS = "points"

    ARRAY = "array"
    MODEL = "model"


class OutputKind(StrEnum):
    IMAGE = "image"
    MASK = "mask"

    ARRAY = "array"
    CONTOURS = "contours"

    METRICS = "metrics"
    SCALAR = "scalar"
