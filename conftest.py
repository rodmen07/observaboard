import pytest


@pytest.fixture(autouse=True)
def _test_settings(settings):
    """Override production settings that break in CI without HTTPS."""
    settings.SECURE_SSL_REDIRECT = False
