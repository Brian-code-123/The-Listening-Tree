import pytest
from starlette.requests import Request

from app.core.session import safe_redirect_target


def _request(referer: str | None, host: str = "app.example.com") -> Request:
    headers = [(b"host", host.encode())]
    if referer is not None:
        headers.append((b"referer", referer.encode()))
    return Request({
        "type": "http", "method": "GET", "scheme": "https", "path": "/set_language/en",
        "query_string": b"", "headers": headers, "server": (host, 443),
    })


@pytest.mark.parametrize("referer, expected", [
    (None, "/"),                                            # no Referer at all
    ("https://app.example.com/profile", "/profile"),        # same host, allowed page
    ("https://app.example.com/hk_guide?x=1", "/hk_guide"),  # query string is dropped
    ("https://app.example.com/admin", "/"),                 # same host, page not on the allowlist
    ("https://evil.example.net/profile", "/"),              # other host: never followed (open redirect)
    ("https://app.example.com.evil.net/profile", "/"),      # look-alike host
    ("https://app.example.com//evil.net", "/"),             # scheme-relative path trick
    ("https://app.example.com/\\evil.net", "/"),            # backslash path trick
    ("javascript:alert(1)", "/"),                           # non-http Referer
    ("http://[::1", "/"),                                   # malformed URL
])
def test_safe_redirect_target_only_returns_known_local_pages(referer, expected):
    assert safe_redirect_target(_request(referer)) == expected
