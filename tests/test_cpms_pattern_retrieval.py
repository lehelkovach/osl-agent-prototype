from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.form_fingerprint import compute_form_fingerprint


def _prov():
    return Provenance(source="user", ts="2026-01-01T00:00:00Z", confidence=1.0, trace_id="t")


def test_compute_form_fingerprint_is_deterministic():
    url = "https://example.com/login"
    html = "<form><input type='email' name='email'><input type='password' id='pwd'></form>"
    fp1 = compute_form_fingerprint(url=url, html=html).to_dict()
    fp2 = compute_form_fingerprint(url=url, html=html).to_dict()
    assert fp1 == fp2
    assert fp1["domain"] == "example.com"
    assert "email" in fp1["tokens"]
    assert "password" in fp1["tokens"]


def test_find_best_cpms_pattern_prefers_same_domain_and_overlap():
    mem = MockMemoryTools()
    ksg = KnowShowGoAPI(mem, embed_fn=lambda _: [0.1, 0.2])  # stable embedding, not important for this test

    url_a = "https://example.com/login"
    html_a = "<form><input type='email' name='email'><input type='password' name='password'></form>"
    fp_a = compute_form_fingerprint(url=url_a, html=html_a).to_dict()
    pattern_a = Node(
        kind="Concept",
        labels=["Pattern", "example.com:login"],
        props={
            "name": "example.com:login",
            "source": "cpms",
            "pattern_data": {
                "form_type": "login",
                "fields": [{"type": "email", "selector": "input[type='email']"}],
                "fingerprint": fp_a,
            },
        },
    )
    mem.upsert(pattern_a, _prov(), embedding_request=False)

    url_b = "https://other.com/signin"
    html_b = "<form><input type='text' name='user'><input type='password' name='pass'></form>"
    fp_b = compute_form_fingerprint(url=url_b, html=html_b).to_dict()
    pattern_b = Node(
        kind="Concept",
        labels=["Pattern", "other.com:login"],
        props={
            "name": "other.com:login",
            "source": "cpms",
            "pattern_data": {
                "form_type": "login",
                "fields": [{"type": "email", "selector": "input[name='user']"}],
                "fingerprint": fp_b,
            },
        },
    )
    mem.upsert(pattern_b, _prov(), embedding_request=False)

    # Query: a near-variant of example.com/login should pick pattern_a.
    html_query = "<form><input type='email' name='email_address'><input type='password' name='password'></form>"
    results = ksg.find_best_cpms_pattern(url=url_a, html=html_query, form_type="login", top_k=1)
    assert results, "Expected a best-match result"
    best = results[0]
    assert best["pattern_data"]["fingerprint"]["domain"] == "example.com"
    assert best["concept"]["props"]["name"] == "example.com:login"

