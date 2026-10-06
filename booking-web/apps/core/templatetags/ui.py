from datetime import date, datetime, time

from django import template
from django.conf import settings

register = template.Library()


def _safe(parse):
    def f(value):
        try:
            return parse(value) if isinstance(value, str) and value else value
        except ValueError:
            return value
    return f


register.filter("as_date", _safe(lambda v: date.fromisoformat(v[:10])))
register.filter("as_time", _safe(time.fromisoformat))
register.filter("as_datetime", _safe(datetime.fromisoformat))


@register.filter
def media(path):
    """API returns relative media paths; prefix the browser-reachable API media URL."""
    return f"{settings.API_MEDIA_URL.rstrip('/')}/{path.lstrip('/')}" if path else ""


@register.filter
def initials(name):
    return "".join(p[0] for p in (name or "?").split()[:2]).upper()


@register.filter
def get(mapping, key):
    return mapping.get(key) if hasattr(mapping, "get") else None


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Current query string with some params replaced, e.g. {% url_replace page=3 %}."""
    q = context["request"].GET.copy()
    for k, v in kwargs.items():
        q[k] = v
    return q.urlencode()
