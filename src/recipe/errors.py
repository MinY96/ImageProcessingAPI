class RecipeError(RuntimeError):
    """Recipe 관리 오류의 기본 예외."""


class RecipeNotFoundError(RecipeError):
    """Recipe를 찾을 수 없을 때 발생한다."""


class DuplicateRecipeError(RecipeError):
    """같은 이름의 Recipe가 이미 존재할 때 발생한다."""


class ReadonlyRecipeError(RecipeError):
    """기본 제공 Recipe를 수정/삭제하려 할 때 발생한다."""


class RecipeRevisionConflictError(RecipeError):
    """낙관적 잠금 revision이 맞지 않을 때 발생한다."""


class RecipeStoreError(RecipeError):
    """Recipe 저장소 읽기/쓰기 오류."""
