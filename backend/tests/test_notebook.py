import ast
import json
from pathlib import Path


NOTEBOOK_PATH = (
    Path(__file__).parents[1]
    / "notebooks"
    / "api_preprocessing_demo.ipynb"
)


def test_api_demo_notebook_is_valid_and_unexecuted():
    notebook = json.loads(
        NOTEBOOK_PATH.read_text(encoding="utf-8")
    )

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"

    code_cells = [
        cell
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    ]
    assert code_cells

    for index, cell in enumerate(code_cells, start=1):
        ast.parse(
            "".join(cell["source"]),
            filename=f"notebook-cell-{index}",
        )
        assert cell["execution_count"] is None
        assert cell["outputs"] == []


def test_api_demo_notebook_covers_operation_and_pipeline():
    source = NOTEBOOK_PATH.read_text(encoding="utf-8")

    assert "execute_operation" in source
    assert "execute_pipeline" in source
    assert "gaussian_blur" in source
    assert "canny" in source
    assert "resize" in source
    assert "edge_thumbnail" in source
