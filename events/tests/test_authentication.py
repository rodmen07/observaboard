import pytest
from django.test import RequestFactory
from rest_framework.exceptions import AuthenticationFailed

from events.authentication import ApiKeyAuthentication

from .factories import ApiKeyFactory


@pytest.mark.django_db
class TestApiKeyAuthentication:
    def setup_method(self):
        self.auth = ApiKeyAuthentication()
        self.rf = RequestFactory()

    def test_valid_key_authenticates(self):
        api_key = ApiKeyFactory()
        request = self.rf.get("/", HTTP_AUTHORIZATION=f"Api-Key {api_key.key}")
        user, auth = self.auth.authenticate(request)
        assert user.is_authenticated
        assert auth.pk == api_key.pk

    def test_revoked_key_raises(self):
        api_key = ApiKeyFactory(is_active=False)
        request = self.rf.get("/", HTTP_AUTHORIZATION=f"Api-Key {api_key.key}")
        with pytest.raises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_invalid_key_raises(self):
        request = self.rf.get("/", HTTP_AUTHORIZATION="Api-Key invalidkeyvalue")
        with pytest.raises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_missing_header_returns_none(self):
        request = self.rf.get("/")
        result = self.auth.authenticate(request)
        assert result is None

    def test_wrong_scheme_returns_none(self):
        request = self.rf.get("/", HTTP_AUTHORIZATION="Bearer sometoken")
        result = self.auth.authenticate(request)
        assert result is None

    def test_last_used_updated(self):
        api_key = ApiKeyFactory()
        assert api_key.last_used_at is None
        request = self.rf.get("/", HTTP_AUTHORIZATION=f"Api-Key {api_key.key}")
        self.auth.authenticate(request)
        api_key.refresh_from_db()
        assert api_key.last_used_at is not None

    def test_authenticate_header(self):
        request = self.rf.get("/")
        assert self.auth.authenticate_header(request) == "Api-Key"
