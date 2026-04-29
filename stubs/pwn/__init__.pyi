class _Section:
    header: object

class ELF:
    arch: str
    bits: int
    entry: int
    endian: str
    symbols: dict[str, int | object] | object
    plt: dict[str, int | object] | object
    got: dict[str, int | object] | object

    def __init__(self, path: str, *, checksec: bool = ...) -> None: ...
    def disasm(self, address: int, size: int) -> str: ...
    def get_section_by_name(self, name: str) -> _Section | None: ...
    def read(self, address: int, size: int) -> bytes: ...
