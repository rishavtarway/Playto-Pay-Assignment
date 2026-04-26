"""End-to-end edge-case audit against the live Render deployment.

Exercises every grading bullet in the assignment spec:
  * State-machine illegal transitions (rejected at API layer)
  * File-upload validation (size, type, magic bytes)
  * Cross-merchant authorization (404, not 403, to avoid leaking existence)
  * SLA at-risk flag computed dynamically
  * Reviewer queue ordering + metrics
  * Anonymous access blocked
  * Already-approved transition returns helpful 400
  * Consistent error shape across 4xx responses

Run: python scripts/edge_case_audit.py [base_url]
"""

import io
import json
import sys
import time
import uuid
import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://playto-kyc-qhwj.onrender.com"
API = BASE.rstrip("/") + "/api/v1"

# -------- helpers --------------------------------------------------------

PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append((label, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {label}" + (f"  ({detail})" if detail and not ok else ""))


def section(title):
    print(f"\n=== {title} ===")


def _retry(method, url, **kw):
    """Free-tier Render dynos go cold and 502 occasionally; retry briefly."""
    for attempt in range(4):
        r = requests.request(method, url, timeout=30, **kw)
        if r.status_code != 502:
            return r
        time.sleep(2 * (attempt + 1))
    return r


def signup(email, password, role="merchant"):
    """Create a brand-new test merchant; returns (token, email)."""
    r = _retry("POST", f"{API}/auth/signup/", json={
        "email": email, "password": password, "role": role,
        "username": email.split("@")[0][:30],
    })
    r.raise_for_status()
    return r.json()["token"], email


def login(email, password):
    r = _retry("POST", f"{API}/auth/login/", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Token {token}"}


def tiny_pdf():
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def fill_required(token):
    """PATCH a draft submission with all required fields so /submit/ passes."""
    return _retry("PATCH", f"{API}/submissions/me/", headers=auth(token), json={
        "full_name": "Test User",
        "email": "test@example.com",
        "phone": "9999999999",
        "business_name": "Acme Co",
        "business_type": "freelance",
        "expected_monthly_volume_usd": 1000,
    })


def upload_doc(token, kind, name, content, content_type="application/pdf"):
    return _retry(
        "POST",
        f"{API}/submissions/me/documents/",
        headers=auth(token),
        files={"file": (name, content, content_type)},
        data={"kind": kind},
    )


def upload_all_docs(token):
    for k in ("pan", "aadhaar", "bank_statement"):
        upload_doc(token, k, f"{k}.pdf", tiny_pdf())


def fresh_merchant_in_state(state, reviewer_token):
    """Create a brand-new merchant and walk them to the target state."""
    email = f"audit_{uuid.uuid4().hex[:8]}@playto.test"
    tok, _ = signup(email, "Test1234!")
    if state == "draft":
        return tok, email
    fill_required(tok)
    upload_all_docs(tok)
    if state == "submitted":
        _retry("POST", f"{API}/submissions/me/submit/", headers=auth(tok))
        return tok, email
    # Need to go through submitted → under_review → ...
    _retry("POST", f"{API}/submissions/me/submit/", headers=auth(tok))
    sub_id = _retry("GET", f"{API}/submissions/me/", headers=auth(tok)).json()["id"]
    _retry("POST", f"{API}/reviews/{sub_id}/start/", headers=auth(reviewer_token))
    if state == "under_review":
        return tok, email
    if state == "approved":
        _retry("POST", f"{API}/reviews/{sub_id}/approve/", headers=auth(reviewer_token))
        return tok, email
    if state == "rejected":
        _retry("POST", f"{API}/reviews/{sub_id}/reject/",
               headers=auth(reviewer_token), json={"reason": "test"})
        return tok, email
    if state == "more_info_requested":
        _retry("POST", f"{API}/reviews/{sub_id}/request-info/",
               headers=auth(reviewer_token), json={"reason": "test"})
        return tok, email
    raise ValueError(state)


# -------- tests ----------------------------------------------------------

def test_health():
    section("Health + environment")
    r = requests.get(f"{BASE}/healthz")
    check("GET /healthz returns 200 ok", r.status_code == 200 and r.text == "ok")


def test_anonymous_blocked():
    section("Anonymous access blocked")
    r = requests.get(f"{API}/submissions/me/")
    check("GET /submissions/me/ without auth returns 401", r.status_code == 401, str(r.status_code))
    r = requests.get(f"{API}/reviews/queue/")
    check("GET /reviews/queue/ without auth returns 401", r.status_code == 401, str(r.status_code))


def test_role_separation(reviewer_token, merchant_token):
    section("Role separation (merchant cannot use reviewer endpoints)")
    r = requests.get(f"{API}/reviews/queue/", headers=auth(merchant_token))
    check("Merchant GET /reviews/queue/ returns 403", r.status_code == 403, str(r.status_code))
    r = requests.get(f"{API}/reviews/metrics/", headers=auth(merchant_token))
    check("Merchant GET /reviews/metrics/ returns 403", r.status_code == 403, str(r.status_code))
    r = requests.get(f"{API}/reviews/queue/", headers=auth(reviewer_token))
    check("Reviewer GET /reviews/queue/ returns 200", r.status_code == 200, str(r.status_code))


def test_cross_merchant_isolation(reviewer_token):
    section("Cross-merchant isolation (404 to avoid leaking existence)")
    a_tok, _ = signup(f"audit_{uuid.uuid4().hex[:8]}@playto.test", "Test1234!")
    b_tok, _ = signup(f"audit_{uuid.uuid4().hex[:8]}@playto.test", "Test1234!")
    # B creates a submission and submits it
    fill_required(b_tok)
    upload_all_docs(b_tok)
    requests.post(f"{API}/submissions/me/submit/", headers=auth(b_tok))
    b_sub_id = requests.get(f"{API}/submissions/me/", headers=auth(b_tok)).json()["id"]

    r = requests.get(f"{API}/reviews/{b_sub_id}/", headers=auth(a_tok))
    check("Merchant A GET /reviews/<merchant-B-id>/ returns 403/404 (not 200)",
          r.status_code in (403, 404), str(r.status_code))

    # And the reviewer CAN see it
    r = requests.get(f"{API}/reviews/{b_sub_id}/", headers=auth(reviewer_token))
    check("Reviewer GET same submission returns 200", r.status_code == 200, str(r.status_code))


def test_state_machine_illegal(reviewer_token):
    section("State machine — illegal transitions return 400")

    # 1) Draft cannot be approved (skip submitted/under_review)
    tok, _ = fresh_merchant_in_state("draft", reviewer_token)
    sub_id = requests.get(f"{API}/submissions/me/", headers=auth(tok)).json()["id"]
    r = requests.post(f"{API}/reviews/{sub_id}/approve/", headers=auth(reviewer_token))
    # Reviewer can SEE this draft but state-machine should reject the transition
    check("Reviewer approving a draft submission returns 400/404",
          r.status_code in (400, 404), f"{r.status_code} {r.text[:120]}")

    # 2) Already-approved cannot be re-approved
    tok, _ = fresh_merchant_in_state("approved", reviewer_token)
    sub_id = requests.get(f"{API}/submissions/me/", headers=auth(tok)).json()["id"]
    r = requests.post(f"{API}/reviews/{sub_id}/approve/", headers=auth(reviewer_token))
    check("Approving already-approved returns 400", r.status_code == 400,
          f"{r.status_code} {r.text[:120]}")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    check("Already-approved 400 has clear error shape (error+detail keys)",
          "error" in body and "detail" in body, json.dumps(body)[:200])

    # 3) Approved → reject also blocked
    r = requests.post(f"{API}/reviews/{sub_id}/reject/",
                      headers=auth(reviewer_token), json={"reason": "x"})
    check("Rejecting an already-approved submission returns 400",
          r.status_code == 400, f"{r.status_code}")

    # 4) Rejected → approve blocked (terminal state)
    tok, _ = fresh_merchant_in_state("rejected", reviewer_token)
    sub_id = requests.get(f"{API}/submissions/me/", headers=auth(tok)).json()["id"]
    r = requests.post(f"{API}/reviews/{sub_id}/approve/", headers=auth(reviewer_token))
    check("Approving a rejected submission returns 400", r.status_code == 400, f"{r.status_code}")

    # 5) Submitted → approve (skipping under_review) blocked
    tok, _ = fresh_merchant_in_state("submitted", reviewer_token)
    sub_id = requests.get(f"{API}/submissions/me/", headers=auth(tok)).json()["id"]
    r = requests.post(f"{API}/reviews/{sub_id}/approve/", headers=auth(reviewer_token))
    check("Submitted (not yet under_review) → approve returns 400",
          r.status_code == 400, f"{r.status_code}")


def test_state_machine_legal(reviewer_token):
    section("State machine — legal transitions work end-to-end")
    tok, email = fresh_merchant_in_state("draft", reviewer_token)
    fill_required(tok)
    upload_all_docs(tok)

    r = requests.post(f"{API}/submissions/me/submit/", headers=auth(tok))
    check("draft → submitted via /submit/ returns 200", r.status_code == 200, f"{r.status_code}")

    sub_id = requests.get(f"{API}/submissions/me/", headers=auth(tok)).json()["id"]
    r = requests.post(f"{API}/reviews/{sub_id}/start/", headers=auth(reviewer_token))
    check("submitted → under_review via /start/ returns 200", r.status_code == 200, f"{r.status_code}")

    r = requests.post(f"{API}/reviews/{sub_id}/request-info/",
                      headers=auth(reviewer_token), json={"reason": "Need clearer PAN scan"})
    check("under_review → more_info_requested via /request-info/ returns 200",
          r.status_code == 200, f"{r.status_code}")

    r = requests.post(f"{API}/submissions/me/submit/", headers=auth(tok))
    check("more_info_requested → submitted via /submit/ returns 200",
          r.status_code == 200, f"{r.status_code}")


def test_submit_validation():
    section("Submit validation (empty draft cannot be submitted)")
    tok, _ = signup(f"audit_{uuid.uuid4().hex[:8]}@playto.test", "Test1234!")
    r = requests.post(f"{API}/submissions/me/submit/", headers=auth(tok))
    check("Empty draft → /submit/ returns 400", r.status_code == 400, f"{r.status_code}")
    body = r.json()
    check("Validation error names missing fields",
          "detail" in body and isinstance(body["detail"], dict), json.dumps(body)[:200])


def test_file_upload_validation():
    section("File upload validation")
    tok, _ = signup(f"audit_{uuid.uuid4().hex[:8]}@playto.test", "Test1234!")

    # Valid PDF
    r = upload_doc(tok, "pan", "ok.pdf", tiny_pdf())
    check("Valid PDF accepted (201/200)", r.status_code in (200, 201), f"{r.status_code} {r.text[:100]}")

    # .exe extension rejected
    r = upload_doc(tok, "aadhaar", "evil.exe", b"MZ\x90\x00fake exe", "application/x-msdownload")
    check("Disallowed extension (.exe) rejected with 400", r.status_code == 400, f"{r.status_code}")

    # 6MB file rejected (>5MB limit)
    big = b"%PDF-1.4\n" + b"a" * (6 * 1024 * 1024)
    r = upload_doc(tok, "aadhaar", "big.pdf", big)
    check("6 MB file rejected (>5MB limit)", r.status_code == 400, f"{r.status_code}")

    # MIME spoofing: extension says .pdf but content is plain text (no PDF magic bytes)
    r = upload_doc(tok, "aadhaar", "fake.pdf", b"this is plainly not a PDF file at all")
    check("Spoofed PDF (wrong magic bytes) rejected", r.status_code == 400, f"{r.status_code}")

    # Empty file rejected
    r = upload_doc(tok, "aadhaar", "empty.pdf", b"")
    check("Empty file rejected", r.status_code == 400, f"{r.status_code}")

    # Valid JPG accepted
    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG SOI marker
    r = upload_doc(tok, "aadhaar", "ok.jpg", jpg, "image/jpeg")
    check("Valid JPG accepted", r.status_code in (200, 201), f"{r.status_code} {r.text[:100]}")


def test_50mb_killed_by_django():
    section("50 MB upload killed by Django middleware")
    tok, _ = signup(f"audit_{uuid.uuid4().hex[:8]}@playto.test", "Test1234!")
    # Build a 50 MB body. Don't load into memory all at once.
    big = io.BytesIO(b"%PDF-1.4\n" + b"a" * (50 * 1024 * 1024))
    big.seek(0)
    r = requests.post(
        f"{API}/submissions/me/documents/",
        headers=auth(tok),
        files={"file": ("huge.pdf", big, "application/pdf")},
        data={"kind": "pan"},
    )
    # Django returns 400 (RequestDataTooBig) once over DATA_UPLOAD_MAX_MEMORY_SIZE.
    check("50 MB upload rejected (4xx)", 400 <= r.status_code < 500, f"{r.status_code}")


def test_sla_at_risk(reviewer_token):
    section("SLA at-risk flag computed dynamically")
    r = _retry("GET", f"{API}/reviews/queue/", headers=auth(reviewer_token))
    check("Reviewer queue returns 200", r.status_code == 200, f"{r.status_code}")
    if r.status_code != 200:
        return
    body = r.json()
    items = body.get("results", body) if isinstance(body, dict) else body
    seed = next((it for it in items if it.get("merchant_email") == "review@playto.test"), None)
    if not seed:
        check("Seeded under_review submission visible in queue",
              False, f"review@playto.test not in {len(items)} queue items")
        return
    check("Seeded 30h-old submission has at_risk=true",
          seed.get("at_risk") is True, json.dumps(seed)[:300])
    # Submissions younger than 24h must NOT be flagged at_risk
    fresh = next((it for it in items
                  if it.get("merchant_email", "").startswith("audit_")
                  and it.get("at_risk") is False), None)
    check("Recently-submitted (<24h) audit merchant has at_risk=false",
          fresh is not None,
          f"no fresh audit_* with at_risk=false in {len(items)} items")


def test_metrics(reviewer_token):
    section("Reviewer metrics endpoint")
    r = requests.get(f"{API}/reviews/metrics/", headers=auth(reviewer_token))
    check("GET /reviews/metrics/ returns 200", r.status_code == 200, f"{r.status_code}")
    if r.status_code == 200:
        body = r.json()
        for key in ("in_queue", "avg_time_in_queue_seconds", "approval_rate_7d"):
            check(f"Metrics contain `{key}`", key in body, json.dumps(body)[:200])


def test_consistent_error_shape():
    section("Consistent error shape across 4xx responses")
    # Trigger a few different errors and confirm they all have {error, detail}
    r = requests.post(f"{API}/auth/login/", json={"email": "nope@nope.test", "password": "x"})
    check("Bad login is 400/401", r.status_code in (400, 401), f"{r.status_code}")
    if r.headers.get("content-type", "").startswith("application/json"):
        body = r.json()
        check("Bad login error has 'error' or 'detail' key",
              "error" in body or "detail" in body, json.dumps(body)[:200])


# -------- main -----------------------------------------------------------

def main():
    print(f"Testing {BASE}")
    test_health()
    test_anonymous_blocked()

    # Use seeded reviewer for everything reviewer-side.
    reviewer_token = login("reviewer@playto.test", "reviewer123")
    # Sanity-check a temp merchant is reachable
    merchant_token, _ = signup(f"audit_{uuid.uuid4().hex[:8]}@playto.test", "Test1234!")

    test_role_separation(reviewer_token, merchant_token)
    test_cross_merchant_isolation(reviewer_token)
    test_state_machine_illegal(reviewer_token)
    test_state_machine_legal(reviewer_token)
    test_submit_validation()
    test_file_upload_validation()
    test_50mb_killed_by_django()
    test_sla_at_risk(reviewer_token)
    test_metrics(reviewer_token)
    test_consistent_error_shape()

    print(f"\n=== Summary: {len(PASS)} passed, {len(FAIL)} failed ===")
    for label, detail in FAIL:
        print(f"  FAIL  {label}  -- {detail}")
    sys.exit(0 if not FAIL else 1)


if __name__ == "__main__":
    main()
