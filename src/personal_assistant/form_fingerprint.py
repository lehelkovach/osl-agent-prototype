"""
Deterministic, text-only fingerprinting for HTML forms.

This is intentionally lightweight (no external HTML parser dependency) so it can
run in constrained environments and be used in unit tests/benchmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse
import re


_ATTR_RE = re.compile(r"""(\w[\w:-]*)\s*=\s*(['"])(.*?)\2""", re.IGNORECASE | re.DOTALL)


def _domain_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _path_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).path or "").strip()
    except Exception:
        return ""


def _tokenize(s: str) -> List[str]:
    # Keep alphanum tokens; split on anything else.
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t]


def _extract_tags(html: str, tag: str) -> List[str]:
    # Naive but deterministic extraction of tags; enough for fingerprints.
    return re.findall(rf"<\s*{re.escape(tag)}\b([^>]*)>", html or "", flags=re.IGNORECASE)


def _extract_attr_map(tag_attrs: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for m in _ATTR_RE.finditer(tag_attrs or ""):
        k = m.group(1).lower()
        v = (m.group(3) or "").strip()
        if k and v:
            attrs[k] = v
    return attrs


@dataclass(frozen=True)
class FormFingerprint:
    v: int
    domain: str
    path: str
    tokens: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {"v": self.v, "domain": self.domain, "path": self.path, "tokens": list(self.tokens)}


def compute_form_fingerprint(url: Optional[str], html: str) -> FormFingerprint:
    """
    Produce a compact fingerprint for form matching.

    Signals included:
    - url domain/path
    - input/button attribute tokens: type/name/id/autocomplete/placeholder/aria-label
    """
    domain = _domain_from_url(url)
    path = _path_from_url(url)

    tokens: Set[str] = set()
    # Tokenize url components lightly (helps grouping).
    tokens.update(_tokenize(domain))
    tokens.update(_tokenize(path))

    for attrs_str in _extract_tags(html, "input"):
        attrs = _extract_attr_map(attrs_str)
        for k in ("type", "name", "id", "autocomplete", "placeholder", "aria-label"):
            if k in attrs:
                tokens.update(_tokenize(attrs[k]))

    for attrs_str in _extract_tags(html, "button"):
        attrs = _extract_attr_map(attrs_str)
        for k in ("type", "name", "id", "aria-label"):
            if k in attrs:
                tokens.update(_tokenize(attrs[k]))

    # Keep deterministic ordering.
    token_list = sorted(tokens)
    return FormFingerprint(v=1, domain=domain, path=path, tokens=token_list)

