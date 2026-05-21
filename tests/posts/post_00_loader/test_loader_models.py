from tiny_dec.loader.models import ExternalFunction, MainResolution, SectionLayout


def test_section_layout_end_address() -> None:
    section = SectionLayout(name=".text", virtual_address=0x10000, size=0x120)
    assert section.end_address == 0x10120


def test_external_function_model_fields() -> None:
    fn = ExternalFunction(
        name="puts",
        plt_address=0x10020,
        got_address=0x12000,
        symbol_address=None,
    )
    assert fn.name == "puts"
    assert fn.plt_address == 0x10020
    assert fn.got_address == 0x12000
    assert fn.symbol_address is None


def test_main_resolution_model_fields() -> None:
    resolution = MainResolution(
        address=0x10150,
        source="symbol_table",
        entrypoint=0x10000,
    )
    assert resolution.address == 0x10150
    assert resolution.source == "symbol_table"
    assert resolution.entrypoint == 0x10000


def test_section_layout_pretty_line_is_deterministic() -> None:
    section = SectionLayout(name=".text", virtual_address=0x1010, size=0x20)
    assert section.to_pretty_line() == ".text    vaddr=0x1010 size=0x20 end=0x1030"


def test_external_function_pretty_line_uses_placeholder_for_missing_addresses() -> None:
    fn = ExternalFunction(
        name="puts",
        plt_address=0x10020,
        got_address=None,
        symbol_address=None,
    )
    assert (
        fn.to_pretty_line()
        == "puts                             plt=     0x10020 got=           - sym=           -"
    )


def test_main_resolution_pretty_line_when_unresolved() -> None:
    resolution = MainResolution(address=None, source="unresolved", entrypoint=0x10000)
    assert (
        resolution.to_pretty_line()
        == "main: <unresolved> (source=unresolved, entrypoint=0x10000)"
    )
