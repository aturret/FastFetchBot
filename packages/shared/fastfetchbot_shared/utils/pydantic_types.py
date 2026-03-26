from typing import Annotated, Optional

from pydantic import BeforeValidator


def _parse_comma_list(v: str | list[str]) -> list[str]:
    """Parse a comma-separated string into a list of stripped, non-empty strings."""
    if isinstance(v, list):
        return v
    return [x.strip() for x in v.split(",") if x.strip()] if v else []


def _parse_optional_comma_list(v: str | list[str] | None) -> Optional[list[str]]:
    """Parse a comma-separated string into a list, returning None for empty input."""
    if v is None:
        return None
    if isinstance(v, list):
        return v or None
    result = [x.strip() for x in v.split(",") if x.strip()]
    return result or None


CommaSeparatedList = Annotated[list[str], BeforeValidator(_parse_comma_list)]
OptionalCommaSeparatedList = Annotated[
    Optional[list[str]], BeforeValidator(_parse_optional_comma_list)
]
