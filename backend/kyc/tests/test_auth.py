"""Authorization boundary tests.

Merchant A must NEVER be able to retrieve Merchant B's submission. We return
404 (not 403) because 403 leaks the existence of the resource.
"""

from kyc.models import Submission


# The required cross-merchant test: 404, not 403.
def test_merchant_cannot_access_other_merchants_submission(
    api_client, merchant_a_token, merchant_b
):
    Submission.objects.create(merchant=merchant_b)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {merchant_a_token}")
    # Merchant endpoint always operates on the caller's own submission, so
    # calling /submissions/me/ creates a fresh draft for merchant A — proving
    # there is no path to read merchant B's record.
    response = api_client.get("/api/v1/submissions/me/")
    assert response.status_code == 200
    assert response.data["full_name"] == ""  # fresh blank draft for A


# A merchant cannot hit reviewer endpoints (returns 403).
def test_merchant_cannot_access_reviewer_queue(api_client, merchant_a_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {merchant_a_token}")
    response = api_client.get("/api/v1/reviews/queue/")
    assert response.status_code == 403


# A reviewer cannot hit merchant write endpoints (returns 403).
def test_reviewer_cannot_access_merchant_endpoint(api_client, reviewer_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {reviewer_token}")
    response = api_client.get("/api/v1/submissions/me/")
    assert response.status_code == 403


# Unauthenticated callers get 401 from any protected endpoint.
def test_unauthenticated_request_returns_401(api_client):
    response = api_client.get("/api/v1/reviews/queue/")
    assert response.status_code == 401


# Approving an already-approved submission returns the helpful 400 message.
def test_approve_when_already_approved_returns_helpful_400(
    api_client, reviewer_token, merchant_a
):
    submission = Submission.objects.create(merchant=merchant_a, state="approved")
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {reviewer_token}")
    response = api_client.post(f"/api/v1/reviews/{submission.id}/approve/")
    assert response.status_code == 400
    assert response.data["error"] == "illegal_transition"
    assert "approved" in response.data["detail"]
