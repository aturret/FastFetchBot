from fastfetchbot_shared.utils.number import positive_int


def test_positive_int_accepts_positive_ints_and_numeric_strings():
    assert positive_int(12) == 12
    assert positive_int("12") == 12
    assert positive_int("12.4") == 12
    assert positive_int("12.5") == 12


def test_positive_int_rejects_non_positive_bool_and_invalid_values():
    assert positive_int(0) is None
    assert positive_int(-1) is None
    assert positive_int(True) is None
    assert positive_int(False) is None
    assert positive_int(None) is None
    assert positive_int("not-a-number") is None
