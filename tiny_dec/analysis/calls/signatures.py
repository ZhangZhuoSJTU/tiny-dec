"""Curated external-signature hints used by stage-8 call modeling.

Variadic functions (printf, scanf, etc.) only model their fixed parameters.
Additional variadic arguments passed in a1-a7 are not captured here; the
call model will under-report arguments at these call sites.
"""

from __future__ import annotations

from tiny_dec.analysis.calls.models import KnownExternalSignature

_SIGNATURES_BY_NAME = {
    "abort": KnownExternalSignature(name="abort", no_return=True),
    "calloc": KnownExternalSignature(
        name="calloc",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "exit": KnownExternalSignature(
        name="exit",
        parameter_registers=(10,),
        no_return=True,
    ),
    "free": KnownExternalSignature(
        name="free",
        parameter_registers=(10,),
    ),
    "malloc": KnownExternalSignature(
        name="malloc",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "memcmp": KnownExternalSignature(
        name="memcmp",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "memcpy": KnownExternalSignature(
        name="memcpy",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "memmove": KnownExternalSignature(
        name="memmove",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "memset": KnownExternalSignature(
        name="memset",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "puts": KnownExternalSignature(
        name="puts",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "realloc": KnownExternalSignature(
        name="realloc",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "strcmp": KnownExternalSignature(
        name="strcmp",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "strcpy": KnownExternalSignature(
        name="strcpy",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "strlen": KnownExternalSignature(
        name="strlen",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "strncpy": KnownExternalSignature(
        name="strncpy",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "strcat": KnownExternalSignature(
        name="strcat",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "strncat": KnownExternalSignature(
        name="strncat",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "strncmp": KnownExternalSignature(
        name="strncmp",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "printf": KnownExternalSignature(
        name="printf",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "fprintf": KnownExternalSignature(
        name="fprintf",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "sprintf": KnownExternalSignature(
        name="sprintf",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "snprintf": KnownExternalSignature(
        name="snprintf",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "scanf": KnownExternalSignature(
        name="scanf",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "sscanf": KnownExternalSignature(
        name="sscanf",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "atoi": KnownExternalSignature(
        name="atoi",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "atol": KnownExternalSignature(
        name="atol",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "strtol": KnownExternalSignature(
        name="strtol",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "strtoul": KnownExternalSignature(
        name="strtoul",
        parameter_registers=(10, 11, 12),
        return_registers=(10,),
    ),
    "qsort": KnownExternalSignature(
        name="qsort",
        parameter_registers=(10, 11, 12, 13),
    ),
    "bsearch": KnownExternalSignature(
        name="bsearch",
        parameter_registers=(10, 11, 12, 13, 14),
        return_registers=(10,),
    ),
    "fopen": KnownExternalSignature(
        name="fopen",
        parameter_registers=(10, 11),
        return_registers=(10,),
    ),
    "fclose": KnownExternalSignature(
        name="fclose",
        parameter_registers=(10,),
        return_registers=(10,),
    ),
    "fread": KnownExternalSignature(
        name="fread",
        parameter_registers=(10, 11, 12, 13),
        return_registers=(10,),
    ),
    "fwrite": KnownExternalSignature(
        name="fwrite",
        parameter_registers=(10, 11, 12, 13),
        return_registers=(10,),
    ),
    "_exit": KnownExternalSignature(
        name="_exit",
        parameter_registers=(10,),
        no_return=True,
    ),
    "__assert_fail": KnownExternalSignature(
        name="__assert_fail",
        parameter_registers=(10, 11, 12, 13),
        no_return=True,
    ),
}


def normalize_external_name(name: str) -> str:
    return name.split("@", 1)[0]


def lookup_known_external_signature(
    name: str | None,
) -> KnownExternalSignature | None:
    if not name:
        return None
    return _SIGNATURES_BY_NAME.get(normalize_external_name(name))
