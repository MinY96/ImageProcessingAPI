from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download/export Stable Diffusion 1.5 Inpainting to OpenVINO IR for local use."
    )
    parser.add_argument(
        "--model-id",
        default="stable-diffusion-v1-5/stable-diffusion-inpainting",
        help="Hugging Face model id or local Diffusers model directory.",
    )
    parser.add_argument(
        "--output-root",
        default=".image_processing_data/models/diffusion/sd15_openvino_inpaint",
        help="Root used by the API provider.",
    )
    parser.add_argument("--input-size", type=int, default=512)
    parser.add_argument(
        "--device",
        default="CPU",
        help="Compile smoke-test device: CPU, GPU, AUTO, GPU.0, ...",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Do not access Hugging Face; only use an already cached/local source model.",
    )
    parser.add_argument(
        "--compile-test",
        action="store_true",
        help="Compile the exported model once after export to verify the selected OpenVINO device.",
    )
    parser.add_argument(
        "--force-export",
        action="store_true",
        help="Re-export even when a prepared OpenVINO model already exists.",
    )
    return parser.parse_args()


def pipeline_class():
    try:
        from optimum.intel import OVPipelineForInpainting

        return OVPipelineForInpainting
    except (ImportError, AttributeError):
        from optimum.intel import OVStableDiffusionInpaintPipeline

        return OVStableDiffusionInpaintPipeline


def export_dir(output_root: Path, model_id: str, input_size: int) -> Path:
    safe_name = model_id.replace("/", "__").replace("\\", "__")
    return output_root / "exported" / f"{safe_name}_{input_size}x{input_size}"


def looks_exported(path: Path) -> bool:
    return (path / "model_index.json").is_file() and any(path.rglob("openvino_model.xml"))


def reshape_if_supported(pipe, input_size: int) -> None:
    if hasattr(pipe, "reshape"):
        pipe.reshape(
            batch_size=1,
            height=input_size,
            width=input_size,
            num_images_per_prompt=1,
        )


def main() -> None:
    args = parse_args()
    if args.input_size < 64 or args.input_size > 2048 or args.input_size % 8 != 0:
        raise SystemExit("--input-size must be 64..2048 and divisible by 8")

    PipelineClass = pipeline_class()
    target = export_dir(Path(args.output_root), args.model_id, args.input_size)

    print(f"Source model : {args.model_id}")
    print(f"Output       : {target}")
    print(f"Input size   : {args.input_size}x{args.input_size}")

    if looks_exported(target) and not args.force_export:
        print("Prepared OpenVINO model already exists; loading local export.")
        pipe = PipelineClass.from_pretrained(
            str(target),
            device=args.device,
            compile=False,
            local_files_only=True,
        )
        reshape_if_supported(pipe, args.input_size)
    else:
        target.mkdir(parents=True, exist_ok=True)
        pipe = PipelineClass.from_pretrained(
            args.model_id,
            export=True,
            compile=False,
            device=args.device,
            local_files_only=args.local_files_only,
        )
        reshape_if_supported(pipe, args.input_size)
        pipe.save_pretrained(str(target))
        print("Saved OpenVINO model.")

    if args.compile_test:
        if hasattr(pipe, "compile"):
            pipe.compile()
        print(f"Compile test succeeded on device={args.device}.")


if __name__ == "__main__":
    main()
