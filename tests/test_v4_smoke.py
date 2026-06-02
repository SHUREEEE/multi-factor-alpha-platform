"""Smoke tests for the reserved V4 namespace."""


def test_v4_module_namespace_reserved():
    import src.portfolio.v4 as v4

    assert "V4 namespace reserved" in (v4.__doc__ or "")
