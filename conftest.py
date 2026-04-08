import pytest


@pytest.fixture(autouse=True)
def _disable_ssl_redirect(settings):
    """Disable SECURE_SSL_REDIRECT during tests so the test client doesn't get 301s."""
    settings.SECURE_SSL_REDIRECT = False
