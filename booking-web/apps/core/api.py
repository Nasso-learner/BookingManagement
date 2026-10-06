"""Thin HTTP client for booking-api. Views call these; nothing here touches a database."""
import math

import requests
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404

_session = requests.Session()


class NotAuthenticated(Exception):
    """API rejected our token (expired / revoked). Middleware redirects to login."""


class APIError(Exception):
    def __init__(self, status, data):
        self.status, self.data = status, data if isinstance(data, dict) else {"detail": data}
        super().__init__(self.message)

    @property
    def errors(self):
        """{field: "first message"} for form display."""
        return {k: (v[0] if isinstance(v, list) and v else str(v)) for k, v in self.data.items()}

    @property
    def message(self):
        e = self.errors
        return e.get("detail") or e.get("non_field_errors") or " ".join(f"{v}" for v in e.values()) or "Request failed."


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return fwd.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


def call(request, method, path, *, data=None, params=None, files=None, auth=True):
    headers = {"X-Forwarded-For": client_ip(request)}
    token = getattr(request, "access_token", None)
    if auth and token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs = {"data": data, "files": files} if files else {"json": data}
    try:
        r = _session.request(method, f"{settings.API_BASE_URL}{path}", params=params, headers=headers,
                             timeout=settings.API_TIMEOUT, **kwargs)
    except requests.RequestException:
        raise APIError(503, {"detail": "The booking service is unavailable. Please try again shortly."})
    body = r.json() if r.content and r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code == 401 and auth:
        raise NotAuthenticated()
    if r.status_code == 403 and auth:
        raise PermissionDenied(body.get("detail", ""))
    if r.status_code == 404:
        raise Http404(body.get("detail", "Not found"))
    if r.status_code >= 400:
        raise APIError(r.status_code, body or {"detail": f"Error {r.status_code}"})
    return body


def get(request, path, params=None, **kw):
    return call(request, "GET", path, params=params, **kw)


def post(request, path, data=None, **kw):
    return call(request, "POST", path, data=data, **kw)


def patch(request, path, data=None, **kw):
    return call(request, "PATCH", path, data=data, **kw)


def delete(request, path, **kw):
    return call(request, "DELETE", path, **kw)


def paged(request, path, params=None):
    """GET a DRF-paginated list. Returns (results, pager dict for partials/pagination.html)."""
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        page = 1
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    data = get(request, path, {**params, "page": page})
    count = data.get("count", 0)
    num_pages = max(math.ceil(count / settings.API_PAGE_SIZE), 1)
    pager = {"page": page, "num_pages": num_pages, "count": count, "has_prev": page > 1,
             "has_next": page < num_pages, "range": range(max(1, page - 2), min(num_pages, page + 2) + 1)}
    return data.get("results", []), pager


def upload_files(request, *names):
    """Pull uploaded files off the request in the shape `requests` expects."""
    return {n: (f.name, f.read(), f.content_type) for n in names if (f := request.FILES.get(n))} or None
