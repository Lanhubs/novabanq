# NovaBanq Backend — Status

**Last updated:** September 24, 2026
**Scope:** Hackathon MVP — authentication and identity verification complete; money movement pending.

---

## How to Use This Document

- ✅ **Done and Verified** — working, tested, committed
- ❌ **Not Started** — planned but untouched

There are no open items. When one appears, add a ⚠️ section above ❌.

---

## ✅ Done and Verified

### Foundation
- FastAPI app boots cleanly (`uvicorn app.main:app --reload`)
- Firebase Admin SDK connects to project `novabanq-ec947`
- Config layer with multi-source Firebase credentials (base64 / JSON / file)
- Exception handling with `{success, data, error}` envelope
- Firestore access layer with `run_atomic` transaction helper
- API versioning at `/api/v1`
- Health endpoint returns expected shape
- Deployed and live at https://novabanq-api.onrender.com

### Authentication
- Firebase ID token verification via `verify_id_token`
- `get_current_uid`, `get_current_claims`, `get_current_user`, `require_user` dependencies
- Sync dependencies (event-loop safe)
- Test suite `tests/test_auth.py` passes 6 tests, 2 skipped (need real OTP code)

### Users feature
- `POST /users/me` — creates profile, gated on email verification
- `GET /users/me` — returns profile
- `PATCH /users/me/names` — updates names, locked after identity verification
- `GET /users/me/tag/check` — checks tag availability with suffix
- `POST /users/me/tag` — claims a @tag with atomic uniqueness
- `POST /users/me/phone/verify` — marks phone as verified
- `POST /users/me/pin` — sets PIN (bcrypt hashed)
- `POST /users/me/pin/verify` — verifies with 5-attempt lockout (20 min)
- `POST /users/me/pin/reset` — clears PIN after Firebase Phone Auth
- Name fields (first, middle, last) required at signup
- Google sign-in bypass — skips email OTP if provider is `google.com`
- `email_verified`, `phone_verified`, `identity_verified` flags

### Account Numbers
- Repository + service with atomic reservation via Firestore transaction
- Uses `secrets.randbelow` (cryptographically secure)
- Retry loop on collision
- **10-digit numeric format** (2-digit country prefix + 8 random digits)
- No prefix letters — placeholder until real NUBANs are issued via Flutterwave

### Tags
- Repository + service with atomic reservation
- Tag uniqueness enforced at DB level
- Format: lowercase letters, numbers, underscores only
- **Country suffix appended server-side** — user claims `david323`, backend stores `david323.ng`
- Suffix derived from the user's profile country, never from the request
- Client-supplied suffixes are stripped before storage
- Availability check endpoint at `GET /users/me/tag/check` — read-only, debounced on the frontend

### Email OTP
- Repository (Firestore-backed, SHA-256 hashed codes, expiry, attempts)
- Service (generate, hash, cooldown, verify, durable verified marker)
- Brevo integration (delivery works — verified by test)
- Email templates with layout wrapper

### PIN
- bcrypt hashing (cost factor 12)
- Lockout at 5 failed attempts for 20 minutes
- Constants: `PIN_LENGTH=5`, `PIN_MAX_ATTEMPTS=5`, `PIN_LOCKOUT_MINUTES=20`

### Identity Module (KYC) — COMPLETE
**Provider interface** (`app/infra/identity/base.py`)
- `IdentityProvider` abstract class with two methods: `verify_bvn_with_face`, `verify_national_id`
- `IdentityResult` and `VerifiedPerson` dataclasses — frozen, PII-redacted `__repr__`, hashable
- `VerificationStatus` enum: `VERIFIED`, `REJECTED`, `WATCHLISTED`, `NOT_FOUND`
- `IdentityProviderError` — pickle-safe, chains `__cause__`
- `__post_init__` validates status coercion, confidence range, and PII scoping (person only on VERIFIED)

**Real adapter** (`app/infra/identity/african_kyc.py`)
- Talks to `POST /identitypass/verification/bvn_w_face`
- Handles response codes `00`, `01`, `02`, `03`, `07`
- Strict watchlist parsing — fails closed
- Non-2xx and provider outages raise `IdentityProviderError`
- Image validation: HTTPS URL, data URI, or raw base64
- BVN validation: 11 ASCII digits

**Mock adapter** (`app/infra/identity/mock.py`)
- Deterministic — same BVN produces the same person
- Sentinel BVNs: `00000000000` → REJECTED, `99999999999` → WATCHLISTED, `11111111111` → NOT_FOUND
- `is_usable_in_production = False` — factory refuses it in production
- Validation rules identical to the real adapter

**Cloudinary client** (`app/infra/cloudinary_client.py`)
- `generate_upload_signature` — signed payload for direct upload, pins `folder` and `access_mode=authenticated`
- `delete_asset` — best-effort cleanup, never raises
- `build_authenticated_url` — signed URL for the provider to fetch

**Identity feature** (`app/features/identity/`)
- `repository.py` — Firestore writes to `identity_verifications/{uid}`, stores masked BVN only
- `schemas.py` — `VerifyIdentityRequest`, `VerifyIdentityResponse`, `UploadSignatureResponse`
- `service.py` — provider factory (refuses mock in production), orchestration, Cloudinary cleanup via `BackgroundTasks`
- `router.py` — `GET /identity/upload-signature`, `POST /identity/verify`
- Endpoint count: 13 total

**Tests** (`tests/test_mock_parity.py`)
- 34 tests — validator parity between mock and real adapter, sentinel BVNs, determinism, PII scoping, input rejection
- Full suite: 40 passed, 2 skipped (real OTP code)

### Documentation
- `README.md` — full API contract for the Flutter dev
  - All endpoints documented with request/response examples
  - Success and error responses for PIN verify and reset
  - Phone mismatch error updated to `422 PHONE_MISMATCH`
  - Tag suffix behavior documented (client sends base name)
  - `GET /users/me/tag/check` endpoint documented
  - Account number format updated to 10-digit numeric
  - Error codes table includes `PHONE_MISMATCH` and identity codes
  - Identity endpoints (`GET /identity/upload-signature`, `POST /identity/verify`) documented
- `FRONTEND_AUTH_GUIDE.md` — detailed Firebase Auth implementation guide
  - Email/password signup flow
  - Google Sign-In setup and implementation
  - Phone verification with SMS OTP
  - Test phone numbers for local testing
  - Token handling and refresh
  - Common errors and fixes
  - Cloudinary direct upload flow for the KYC selfie
  - Identity verification status handling
- `STATUS.md` — this file

---

## ❌ Not Started

### Money Movement
- Accounts (`GET /accounts/me` with balances)
- Currency (rates, corridors, seed data)
- Funding (demo deposits + webhook)
- Virtual accounts (Flutterwave integration)
- Ledger (atomic money movement — the core)
- Transfers (quote + execute)
- Transactions (history)

### Supporting Features
- Notifications (welcome + badge)
- Avatar upload (uses the same Cloudinary client already built)

---

## Working Order (Do Not Deviate)

1. ✅ Foundation — FastAPI, Firebase, Firestore, config, exceptions
2. ✅ Authentication — Firebase token verification, email OTP, PIN
3. ✅ Users feature — profile, names, tag, phone, PIN
4. ✅ Account number format — 10 digits numeric
5. ✅ @tag country suffix — appended server-side
6. ✅ Identity module — interface, real + mock adapters, Cloudinary client, service, router, tests
7. ✅ Documentation — README, FRONTEND_AUTH_GUIDE, STATUS
8. **Now:** accounts → currency → funding → virtual accounts → ledger → transfers → transactions
9. **Finally** notifications, avatar upload

---

## Known Limitations (Document for Judges)

- Country is immutable after signup (no endpoint to change it)
- Account numbers are 10-digit placeholders. Real NUBANs come from Flutterwave when the virtual accounts module ships.
- BVN verification returns sandbox test data in dev, not real user data
- Face match confidence is 0.04 in sandbox (real threshold is 0.70)
- Firestore security rules not yet written (client never writes directly, so backend-only access is safe for now)
- No API-level rate limiting beyond OTP/PIN cooldowns
- No distributed tracing or structured logging beyond standard Python logger
- No real-time tag availability push — frontend must debounce `GET /users/me/tag/check` calls
- Email OTP delivery depends on Brevo — if Brevo sandbox stalls, tests will time out
- Cloudinary cleanup is best-effort; a failed delete leaves the asset in place
- Provider factory refuses the mock adapter in production, but a misconfiguration could still pick the wrong real provider if the name is wrong