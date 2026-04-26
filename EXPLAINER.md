# EXPLAINER

Five questions, five answers. Code below is pasted verbatim from the repo.

---

## 1. The State Machine — where it lives & how illegal transitions are blocked

The state machine is one module — `backend/kyc/state_machine.py`. Every
transition in the system goes through `transition()`. No view ever writes
`submission.state = ...` directly.

```python
# backend/kyc/state_machine.py
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted"},
    "submitted": {"under_review"},
    "under_review": {"approved", "rejected", "more_info_requested"},
    "more_info_requested": {"submitted"},
    "approved": set(),   # terminal
    "rejected": set(),   # terminal
}


class IllegalTransition(Exception):
    """Raised when transition() is called with a (current, target) that isn't
    in LEGAL_TRANSITIONS. The custom DRF exception handler maps this to a
    clean 400 with {"error": "illegal_transition", "detail": "..."}."""


def can_transition(current: str, target: str) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, set())


@transaction.atomic
def transition(submission, target_state, *, actor, reason="", assigned_reviewer=None):
    current = submission.state
    if not can_transition(current, target_state):
        raise IllegalTransition(
            f"Cannot move submission from '{current}' to '{target_state}'."
        )

    # State change + side effects all inside one DB transaction.
    submission.state = target_state
    if target_state == SubmissionState.SUBMITTED and submission.submitted_at is None:
        submission.submitted_at = timezone.now()
    if target_state == SubmissionState.REJECTED:
        submission.rejection_reason = reason
    if target_state == SubmissionState.MORE_INFO_REQUESTED:
        submission.info_request_reason = reason
    if assigned_reviewer is not None:
        submission.assigned_reviewer = assigned_reviewer
    submission.save()

    Notification.objects.create(
        merchant=submission.merchant,
        submission=submission,
        event_type=f"state_changed:{current}->{target_state}",
        payload={"reason": reason, "actor_id": getattr(actor, "id", None)},
    )
    _try_send_email(submission, current, target_state, reason)
```

**Why it's safe:**

1. There is exactly one place that touches `submission.state`. Reviewing
   the code for state-related bugs means reading one file.
2. The transition + the audit log + the email all live inside the same
   `@transaction.atomic` block. We never end up with a state change that
   has no notification (or vice versa) because of a half-failed request.
3. Action endpoints wrap the whole thing in `select_for_update()`
   (`backend/kyc/views.py`) so two concurrent reviewers cannot race on the
   same submission.
4. The custom DRF exception handler (`backend/config/exception_handler.py`)
   maps `IllegalTransition` to:

   ```json
   {"error": "illegal_transition", "detail": "Cannot move submission from 'approved' to 'draft'."}
   ```

   with HTTP 400 — same shape as every other API error, so the frontend
   only has one error path to handle.

This is also the test that's required by the assignment:

```python
# backend/kyc/tests/test_state_machine.py
def test_illegal_transition_approved_to_draft(db, merchant_a, reviewer):
    submission = Submission.objects.create(merchant=merchant_a, state="approved")
    with pytest.raises(IllegalTransition):
        transition(submission, "draft", actor=reviewer)
```

---

## 2. The Upload — validation & what happens to a 50 MB file

Validation is in one file: `backend/kyc/validators.py`. The order is
deliberate: cheapest checks first, real magic-byte sniff last.

```python
# backend/kyc/validators.py
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_document_file(file) -> None:
    # 1. Size — no I/O required.
    if file.size > MAX_SIZE_BYTES:
        raise ValidationError(f"File too large ({file.size} bytes, max {MAX_SIZE_BYTES}).")

    # 2. Extension — cheap.
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extension '{ext}' not allowed.")

    # 3. Magic bytes — the real check. Read the first 4 KB and sniff.
    file.seek(0)
    header = file.read(4096)
    file.seek(0)
    detected = _sniff_mime(header)
    if detected not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"File content does not match an allowed type (detected={detected})."
        )
```

I deliberately do **not** trust `file.content_type`. That value comes from
the client and is trivially spoofable — a `curl` request can send any MIME
type it likes.

`_sniff_mime` calls `python-magic` (libmagic) and falls back to a small
hard-coded signature table if libmagic isn't available, so the deployment
never silently turns into "no validation".

**What happens with a 50 MB file?** It never reaches the view. In
`backend/config/settings.py`:

```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024   # 6 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024   # 6 MB
```

When the request body exceeds those limits, Django raises
`RequestDataTooBig` *before* any view runs. The custom exception handler
catches it and returns:

```json
{"error": "request_too_large", "detail": "Uploaded data exceeds the configured limit."}
```

with HTTP 400. So a 50 MB file is rejected at the WSGI layer; a 6 MB file
is rejected by `validate_document_file`'s size check; an `evil.pdf` whose
bytes are actually a Windows EXE is rejected by the magic-byte sniff —
all returning the same clean 400 shape.

---

## 3. The Queue — query that powers the dashboard

```python
# backend/kyc/views.py
def _open_queue_qs():
    open_states = (
        SubmissionState.SUBMITTED,
        SubmissionState.UNDER_REVIEW,
        SubmissionState.MORE_INFO_REQUESTED,
    )
    return (
        Submission.objects
        .filter(state__in=open_states)
        .select_related("merchant", "assigned_reviewer")
        .prefetch_related("documents")
        .annotate(
            time_in_queue=ExpressionWrapper(
                Now() - F("submitted_at"), output_field=DurationField(),
            )
        )
        .order_by("submitted_at")
    )
```

And the SLA flag is computed dynamically by the serializer — never stored:

```python
# backend/kyc/serializers.py
def get_is_at_risk(self, obj):
    if obj.submitted_at is None:
        return False
    return (timezone.now() - obj.submitted_at) > timedelta(hours=24)
```

**Why it's written this way:**

- `select_related("merchant", "assigned_reviewer")` collapses the joins
  for the FK columns into a single SQL query — no N+1 across the queue.
- `prefetch_related("documents")` does one extra query per page for all
  the related documents instead of one per submission.
- `annotate(time_in_queue=Now() - F("submitted_at"))` calculates wait
  time in SQL. We *could* expose this directly, but for clarity I render
  the integer seconds in the serializer's `time_in_queue_seconds` method.
- The `(state, submitted_at)` composite index in `kyc/models.py` makes
  the `filter(state__in=...).order_by("submitted_at")` query an index
  scan, not a table scan.
- `is_at_risk` is **never persisted**. That was a hard requirement: a
  stored flag would go stale the second `now()` ticks. Computing it from
  `submitted_at` means it's always current.

---

## 4. The Auth — stopping merchant A from seeing merchant B

The defense is **queryset scoping**, not just permissions. Every merchant
endpoint operates on the caller's own submission only:

```python
# backend/kyc/views.py — merchant submission endpoint
class MerchantSubmissionView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def _get_or_create(self, user):
        # The query is filtered by request.user.merchant — there is no
        # query path that returns another merchant's row.
        submission, _ = Submission.objects.get_or_create(merchant=user)
        return submission
```

```python
# Document delete endpoint — note the second filter, NOT just pk=...
class MerchantDocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def delete(self, request, doc_id):
        submission = get_object_or_404(Submission, merchant=request.user)
        document = get_object_or_404(Document, id=doc_id, submission=submission)
        ...
```

There is **no endpoint** that returns a submission by ID for a merchant —
the merchant API uses `submissions/me/`, which is implicit on the
authenticated user. So merchant A literally has no URL to type that
returns merchant B's record. If they tried to submit a document upload
for some other ID, the `merchant=request.user` filter on `get_object_or_404`
returns 404, not 403, so we don't even leak the existence of the resource.

The reviewer endpoints are gated by `IsReviewer`:

```python
# backend/kyc/permissions.py
class IsReviewer(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_reviewer())
```

Which is enforced as a `permission_classes` on every reviewer view, so a
merchant's token gets a clean 403 from `/api/v1/reviews/...`.

This is verified in `backend/kyc/tests/test_auth.py`:

```python
def test_merchant_cannot_access_reviewer_queue(api_client, merchant_a_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {merchant_a_token}")
    response = api_client.get("/api/v1/reviews/queue/")
    assert response.status_code == 403
```

---

## 5. The AI Audit — one specific buggy thing AI gave me

When I asked Claude for the document-upload validation, the first draft
trusted the client's `content_type`:

```python
# What the AI gave me first (I didn't keep it)
def validate_document_file(file):
    if file.size > 5 * 1024 * 1024:
        raise ValidationError("Too big")
    if file.content_type not in {"application/pdf", "image/jpeg", "image/png"}:
        raise ValidationError("Wrong type")
```

This is *exactly* the kind of insecure pattern AI tends to produce because
`file.content_type` looks safe and reads naturally. It's not safe — that
value is whatever the client put in the multipart `Content-Type` header.
A trivial `curl -F "file=@malware.exe;type=application/pdf"` walks past
this check, and then we've got a `.exe` saved to the merchant's documents
folder.

What I replaced it with — the version in the repo — actually reads the
first 4 KB of the file and asks libmagic what it really is:

```python
# backend/kyc/validators.py — the version that shipped
def validate_document_file(file):
    if file.size > MAX_SIZE_BYTES:
        raise ValidationError("File too large.")

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extension '{ext}' not allowed.")

    file.seek(0)
    header = file.read(4096)
    file.seek(0)
    detected = _sniff_mime(header)        # libmagic, with a small fallback
    if detected not in ALLOWED_MIME_TYPES:
        raise ValidationError("File content does not match an allowed type.")
```

I added a regression test for this in
`backend/kyc/tests/test_uploads.py::test_spoofed_extension_rejected_by_magic_bytes`
— a `.pdf`-named file with EXE bytes is rejected, even when the request's
`Content-Type` says `application/pdf`. That is the test that would have
caught the AI's first draft.

**The lesson:** AI loves to use whatever-looks-most-convenient. For
anything security-adjacent (content type, user identity, authorization
filters), I read the AI's answer with the question "what is the
attacker-controlled input here?" before accepting it.
