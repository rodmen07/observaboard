import pytest


@pytest.fixture(autouse=True)
def _test_settings(settings):
    """Override production settings that break in CI without collectstatic / HTTPS."""
    settings.SECURE_SSL_REDIRECT = False
    settings.STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
