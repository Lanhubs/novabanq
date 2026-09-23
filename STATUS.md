# NovaBanq Backend — Status

**Last updated:** September 23, 2026
**Scope:** Hackathon MVP — authentication complete, identity module pending.

---

## How to Use This Document

- ✅ **Done and Verified** — working, tested, committed
- ⚠️ **Agreed but Not Implemented** — decision made, code not written yet
- 🔧 **In Progress** — being worked on right now
- ❌ **Not Started** — planned but untouched

Do not start a new item while anything is in ⚠️ or 🔧. Finish the open items first.

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

### Prembly Integration
- Sandbox credentials verified working
- BVN + Face endpoint tested successfully (returned test data)
- Response shape confirmed: `response_code`, `verification.status`, `watchListed`, `firstName`, `lastName`, `face_data.confidence`

---

## ⚠️ Agreed but Not Implemented

### 1. Fix README gaps
**Current state:** README exists but is missing several sections that the Flutter dev needs.
**Files to change:**
- `README.md` — add missing success response for `POST /users/me/pin/verify`
- `README.md` — add full spec for `POST /users/me/pin/reset`
- `README.md` — update `403 VALIDATION_ERROR` → `422 PHONE_MISMATCH` for phone mismatch
- `README.md` — document the tag suffix behavior (client sends base name, backend appends suffix)
- `README.md` — document `GET /users/me/tag/check` endpoint
- `README.md` — update example account number from `NB0172094612` to `0172094612`
- `README.md` — update error codes table with `PHONE_MISMATCH` and identity codes

### 2. Rotate exposed credentials
**Current state:** Prembly sandbox keys were pasted in chat.
**Action:**
- Firebase service account key already rotated ✅
- Prembly `test_pk_...` and `test_sk_...` still need rotation
- Rotate from Prembly dashboard before going live

### 3. Run full test suite with real OTP
**Current state:** Two tests are skipped because they require the real OTP code.
**Action:**
- Send an OTP via `POST /otp/email/send`
- Read the code from the email inbox
- Set `OTP_CODE` env var and run `pytest tests/test_auth.py -v -s`
- Confirm all 8 tests pass, 0 skipped

---

## 🔧 In Progress

**Nothing.** All work paused until the ⚠️ items are cleared.

---

## ❌ Not Started

### Identity Module (KYC)
**Files created but empty:**
- `app/infra/identity/` — base.py, schemas.py, african_kyc.py, mock.py
- `app/features/identity/` — repository.py, schemas.py, service.py, router.py
**Old providers folder** (`app/features/identity/providers/`) still exists and needs deletion.

**Design agreed:**
- Single endpoint `POST /identity/verify-bvn-face` takes BVN + face image
- Provider selected via `KYC_PROVIDER` env var (`mock` or `african_kyc`)
- On success, flips `identity_verified: true` on the user profile
- Names are locked once identity_verified is true

### Other Features
- Accounts (`GET /accounts/me` with balances)
- Currency (rates, corridors, seed data)
- Funding (demo deposits + webhook)
- Ledger (atomic money movement — the core)
- Transfers (quote + execute)
- Transactions (history)
- Virtual accounts (Flutterwave integration)
- Notifications (welcome + badge)
- Avatar upload (Cloudinary, signed direct upload)

---

## Working Order (Do Not Deviate)

1. ✅ **Fix account number format** — remove `NB`, make 10 digits numeric
2. ✅ **Fix @tag country suffix** — append suffix from profile country
3. ⚠️ **Fix README gaps** — all the missing sections listed above
4. ⚠️ **Rotate Prembly keys** — before any live integration
5. ⚠️ **Run full test suite** with real OTP — confirm all 8 pass
6. **Commit each fix separately** — one commit per item, no batching
7. **Build identity module** — after the above are clean
8. **Then** accounts → currency → funding → ledger → transfers

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