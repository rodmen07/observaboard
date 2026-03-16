from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    """
    Authenticate via `Authorization: Api-Key <key>` header.
    On success returns (request.user=None, auth=api_key_instance) so that
    permission classes can still allow the request via IsAuthenticated by
    treating a valid API key as authenticated.
    """

    keyword = "Api-Key"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(self.keyword + " "):
            return None  # not our scheme — let the next authenticator try

        raw_key = auth_header[len(self.keyword) + 1:].strip()
        try:
            api_key = ApiKey.objects.get(key=raw_key, is_active=True)
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid or revoked API key.")

        api_key.last_used_at = timezone.now()
        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=api_key.last_used_at)

        # Return (user, auth). DRF treats non-None auth as authenticated.
        # We return a sentinel user so IsAuthenticated passes.
        return (self._make_api_key_user(api_key), api_key)

    def _make_api_key_user(self, api_key):
        """Return a lightweight object that satisfies is_authenticated."""
        class ApiKeyUser:
            is_authenticated = True
            is_active = True
            pk = None

            def __init__(self, name):
                self.username = f"api-key:{name}"

        return ApiKeyUser(api_key.name)

    def authenticate_header(self, request):
        return self.keyword
