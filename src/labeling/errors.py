class LabelError(RuntimeError):
    """Label 관리 오류의 기본 예외."""


class LabelNotFoundError(LabelError):
    """이미지 Label 문서를 찾을 수 없을 때 발생한다."""


class DuplicateLabelError(LabelError):
    """같은 image_id의 Label 문서가 이미 있을 때 발생한다."""


class AnnotationNotFoundError(LabelError):
    """Annotation을 찾을 수 없을 때 발생한다."""


class DuplicateAnnotationError(LabelError):
    """같은 annotation_id가 이미 있을 때 발생한다."""


class LabelRevisionConflictError(LabelError):
    """낙관적 잠금 revision이 맞지 않을 때 발생한다."""


class LabelStoreError(LabelError):
    """Label 저장소 읽기/쓰기 오류."""
