import random
from urllib.parse import urlparse, parse_qs


def _seed_from_url(url: str) -> int:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    seed_vals = qs.get("seed") or qs.get("page") or []
    try:
        return int(seed_vals[0])
    except Exception:
        return 42


def _rand_field(rng, base: str, variants: list[str]) -> dict:
    name = rng.choice(variants)
    return {
        "id": f"{name}-{rng.randint(100,999)}",
        "name": name,
        "placeholder": rng.choice([name, name.capitalize(), f"{base}"]),
    }


def build_form_html(url: str, kind: str) -> str:
    """
    Generate deterministic-but-randomized HTML based on URL seed and form kind.
    kind: login | billing | card | survey
    """
    rng = random.Random(_seed_from_url(url))
    fields = []
    if kind == "login":
        fields = [
            _rand_field(rng, "email", ["email", "user", "username", "usr"]),
            _rand_field(rng, "password", ["password", "pass", "pwd"]),
        ]
    elif kind == "billing":
        variants = {
            "givenName": ["givenName", "first", "fname"],
            "familyName": ["familyName", "last", "lname", "surname"],
            "address": ["address", "addr", "address1"],
            "city": ["city", "town"],
            "state": ["state", "province", "region"],
            "postalCode": ["postalCode", "zip", "postcode"],
            "country": ["country", "nation"],
        }
        for base, var in variants.items():
            fields.append(_rand_field(rng, base, var))
    elif kind == "card":
        variants = {
            "cardNumber": ["cardNumber", "ccnum", "cc-number"],
            "cardExpiry": ["cardExpiry", "exp", "expiry"],
            "cardCvv": ["cardCvv", "cvv", "cvc"],
            "billingAddress": ["billingAddress", "billAddr", "billing"],
        }
        for base, var in variants.items():
            fields.append(_rand_field(rng, base, var))
    elif kind == "survey":
        for i in range(3):
            fields.append(_rand_field(rng, f"q{i+1}", [f"q{i+1}", f"question{i+1}", f"q{i+1}_text"]))
    rng.shuffle(fields)
    inputs = "\n".join(
        f'<input type="text" id="{f["id"]}" name="{f["name"]}" placeholder="{f["placeholder"]}" />' for f in fields
    )
    return f"<!DOCTYPE html><html><body><form>{inputs}<button id='submit' type='submit'>Submit</button></form></body></html>"
