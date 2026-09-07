from pathlib import Path

from pydantic import Field

from src.schemas.base import BaseSchema


class ApiSettings(BaseSchema):
    api_prefix: str = "/api/v1"

    recipe_store_dir: Path = Path(".image_processing_data/recipes")
    label_store_dir: Path = Path(".image_processing_data/labels")

    max_upload_files: int = Field(default=8, ge=1, le=64)
    max_upload_bytes_per_file: int = Field(
        default=25 * 1024 * 1024,
        ge=1024,
    )
    max_image_pixels: int = Field(
        default=64_000_000,
        ge=1,
    )
    max_total_decoded_bytes: int = Field(
        default=512 * 1024 * 1024,
        ge=1024,
    )
    max_json_binary_bytes: int = Field(
        default=32 * 1024 * 1024,
        ge=1024,
    )
    max_zip_binary_bytes: int = Field(
        default=128 * 1024 * 1024,
        ge=1024,
    )
    max_inline_array_items: int = Field(
        default=100_000,
        ge=1,
    )
