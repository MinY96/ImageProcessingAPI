class SyntheticError(RuntimeError):
    """Synthetic anomaly generation errors."""


class SyntheticValidationError(SyntheticError):
    pass


class SyntheticAssetNotFoundError(SyntheticError):
    pass


class SyntheticAssetStoreError(SyntheticError):
    pass


class SyntheticDependencyError(SyntheticError):
    pass


class SyntheticModelUnavailableError(SyntheticError):
    pass
