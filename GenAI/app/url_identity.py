from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import hashlib

def canonical_url(value):
    if not isinstance(value, str):
        return None
    try:
        p = urlsplit(value.strip())
        if p.scheme.lower() not in ("http", "https") or not p.hostname or p.username or p.password:
            return None
        host = p.hostname.lower()
        if ":" in host:
            host = "[" + host + "]"
        port = p.port
        if port and (p.scheme.lower(), port) not in (("http", 80), ("https", 443)):
            host += ":" + str(port)
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
        return urlunsplit((p.scheme.lower(), host, p.path or "/", urlencode(query), ""))
    except ValueError:
        return None

def url_key(value):
    normalized = canonical_url(value)
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else None
