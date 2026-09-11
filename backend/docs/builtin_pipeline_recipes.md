# Built-in Pipeline Recipes

`create_default_pipelines()`는 사용자 Pipeline Editor의 예제·템플릿으로 활용할 수
있는 20개의 `PipelineSpec`을 반환합니다. FastAPI 기본 애플리케이션에서는 모두
`PipelineCatalog`에 등록되므로 다음 endpoint에서 조회할 수 있습니다.

```text
GET /api/v1/pipelines
GET /api/v1/pipelines/{pipeline_name}
POST /api/v1/pipelines/{pipeline_name}/execute
```

## 사진 편집 Recipe

| 이름 | 필수 입력 | 처리 단계 | 출력 |
|---|---|---|---|
| `natural_enhance` | `image` | edge preserve → detail → tone → color | `image` |
| `film_look` | `image` | tone → color → vignette → grain | `image` |
| `cinematic_3d_lut` | `image`, `lut` | tone → color → 3D LUT → vignette → grain | `image` |
| `vintage_1d_lut` | `image`, `lut` | tone → color → 1D LUT → vignette → grain | `image` |
| `clean_portrait` | `image` | edge preserve → tone → color → vignette | `image` |
| `comic_style` | `image` | edge preserve → color quantization → stylization | `image` |
| `pencil_sketch` | `image` | edge preserve → pencil sketch | `gray`, `color` |
| `dramatic_detail` | `image` | detail → tone → color → vignette | `image` |

`cinematic_3d_lut.lut`는 `(N,N,N,3)` RGB cube이고 `vintage_1d_lut.lut`는
`(256,)` 또는 `(256,channels)` 배열입니다. API에서는 multipart payload의
`inputs`에 JSON 배열로 전달할 수 있으며, 큰 LUT는 향후 Asset Registry의
`asset_id`로 binding하는 방식을 권장합니다.

## 문서·검사·검출 Recipe

| 이름 | 필수 입력 | 처리 단계 | 주요 출력 |
|---|---|---|---|
| `edge_thumbnail` | `image` | gray → blur → resize → Canny | `edges` |
| `document_otsu` | `image` | gray → blur → Otsu → close | `image` |
| `document_adaptive` | `image` | gray → bilateral → adaptive threshold → open → close | `image` |
| `binary_mask_cleanup` | `mask` | open → close | `mask` |
| `general_edge_detection` | `image` | gray → CLAHE → blur → Canny → close | `edges` |
| `sem_profile_edges` | `image` | gray → CLAHE → bilateral → Scharr-X → threshold → close | `profile_mask`, `gradient` |
| `reference_difference` | `reference`, `current` | absdiff → blur → threshold → cleanup → contours | `difference`, `mask`, `annotated`, `contours`, `features` |
| `line_detection` | `image` | gray → blur → Canny → Hough lines | `image`, `lines`, `edges` |
| `circle_detection` | `image` | gray → median → Hough circles | `image`, `circles` |
| `color_segmentation` | `image` | edge preserve → K-Means | `image`, `labels`, `centers`, `compactness` |

`reference_difference`는 `reference`와 `current`가 모두 GRAY uint8이며 크기,
dtype, color space가 같아야 합니다. SEM recipe의 고정 threshold는 시작값이므로
장비·배율·밝기 조건별로 복제하여 조정하는 것을 권장합니다.

## 합성 Recipe

| 이름 | 필수 입력 | 처리 단계 | 출력 |
|---|---|---|---|
| `masked_local_enhancement` | BGR `image`, `mask` | detail → tone → mask blend | `image` |
| `seamless_composite` | `source`, `destination`, source 크기 `mask` | seamless clone | `image` |

`seamless_composite`의 기본 중심은 `(320, 240)`입니다. 대상 이미지 크기와 source
영역에 맞게 Recipe의 `center_x`, `center_y`를 수정해야 합니다. 사용자 프로그램에
Pipeline parameter binding을 추가하면 이 좌표를 실행 시 입력받도록 확장할 수
있습니다.

## Python 사용 예시

```python
from src.pipeline import PipelineCatalog, PipelineExecutor, create_default_pipelines
from src.registry import create_default_registry

executor = PipelineExecutor(create_default_registry())
catalog = PipelineCatalog(executor)

for recipe in create_default_pipelines():
    catalog.register(recipe)

recipe = catalog.get_spec("sem_profile_edges")
result = executor.execute(
    pipeline=recipe,
    inputs={"image": image},
    retain_intermediates=True,
)
```

## 사용자 Recipe로 전환할 때의 원칙

- Built-in recipe는 수정하지 않고 복제하여 새 `name`과 `version`을 부여합니다.
- 저장하기 전에 `PipelineExecutor.compile()`로 현재 Registry와 호환되는지
  검증합니다.
- `retain_intermediates=True`는 미리보기와 디버깅에서만 사용합니다.
- LUT, kernel, model처럼 큰 값은 JSON에 직접 넣기보다 별도 asset으로 관리합니다.
- Recipe 파일을 불러올 때도 operation 삭제나 parameter 변경에 대비해 재검증합니다.
