class TinyDecLoaderError(RuntimeError):
    """Base error for loader-related failures."""


class UnsupportedArchitectureError(TinyDecLoaderError):
    """Raised when a binary does not match the expected architecture."""


class AddressNotMappedError(TinyDecLoaderError):
    """Raised when a virtual address range cannot be read from ELF."""


class MainResolutionError(TinyDecLoaderError):
    """Raised when main() cannot be resolved from startup metadata."""
