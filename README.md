```markdown
# NovaBanq Backend API

Pan-African payments platform — backend API for the NovaBanq mobile application.

* **Live API:** [https://novabanq-api.onrender.com](https://novabanq-api.onrender.com)
* **Interactive Docs (Swagger):** [https://novabanq-api.onrender.com/docs](https://novabanq-api.onrender.com/docs)
* **Health Check:** [https://novabanq-api.onrender.com/health](https://novabanq-api.onrender.com/health)

---

## Frontend Integration Guide

This section contains everything required to integrate the NovaBanq mobile app (Flutter) with the backend services.

### 1. Base URL

```text
[https://novabanq-api.onrender.com/api/v1](https://novabanq-api.onrender.com/api/v1)

```

All relative paths listed below should be appended to this base URL.

---

### 2. Authentication

Every protected endpoint requires a valid **Firebase ID Token** in the request header:

```http
Authorization: Bearer <firebase_id_token>
Content-Type: application/json

```

#### Token Retrieval (Flutter)

```dart
final user = FirebaseAuth.instance.currentUser;
final token = await user?.getIdToken();

```

> **Note:** Firebase ID tokens expire after **1 hour**. Always call `getIdToken()` fresh prior to issuing an API request rather than caching the token string. The Firebase SDK handles token refreshes automatically.

The backend verifies the token against Firebase on every request. Missing, expired, or invalid tokens yield a `401 Unauthorized` error accompanied by an explicit error code (`AUTH_REQUIRED` or `AUTH_INVALID`).

---

### 3. Response Envelope Structure

All API responses follow a standard envelope model regardless of status:

#### Success Response

```json
{
  "success": true,
  "data": { ... },
  "error": null
}

```

#### Error Response

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description.",
    "details": {}
  }
}

```

> **Implementation Recommendation:** Implement a single global network response handler in your Flutter application that checks `success` and parses either `data` or `error` uniformly.

---

### 4. HTTP Status Codes

| Status | Code Meaning | Context |
| --- | --- | --- |
| `200` | OK | Success |
| `201` | Created | Resource successfully created (Profile, PIN, etc.) |
| `400` | Bad Request | Malformed JSON payload or invalid request body |
| `401` | Unauthorized | Missing, invalid, or expired authorization token |
| `403` | Forbidden | Authenticated, but lacking permission (e.g., email not verified) |
| `404` | Not Found | Resource does not exist (e.g., user profile not found) |
| `409` | Conflict | Resource conflict (e.g., tag already taken, PIN already set) |
| `422` | Unprocessable Entity | Validation failure or business rule violation |
| `429` | Too Many Requests | Rate limited (e.g., PIN locked out, OTP cooldown active) |
| `500` | Internal Error | Server-side execution exception |

---

### 5. Error Code Matrix

Programmatically switch application logic on `error.code`. Avoid relying on `error.message` for business logic decisions.

| Error Code | Description | Recommended Client Action |
| --- | --- | --- |
| `AUTH_REQUIRED` | Authorization header omitted | Redirect to authentication/login flow |
| `AUTH_INVALID` | Token invalid or expired | Refresh token via Firebase SDK, then retry |
| `USER_NOT_FOUND` | No database profile linked to Firebase UID | Route user to profile registration flow |
| `USER_ALREADY_EXISTS` | Profile entry already exists | Route user directly to home/dashboard |
| `EMAIL_NOT_VERIFIED` | Email OTP step incomplete | Direct user to email verification screen |
| `VALIDATION_ERROR` | Request payload validation failed | Highlight affected fields in UI |
| `TAG_TAKEN` | Requested `@tag` is unavailable | Prompt user to select an alternative `@tag` |
| `TAG_INVALID` | Tag formatting rules failed | Display formatting requirements |
| `OTP_INVALID` | Incorrect or stale OTP input | Prompt for correct verification code |
| `OTP_EXPIRED` | Verification code expired | Present option to request new OTP |
| `OTP_TOO_MANY_ATTEMPTS` | Maximum code validation attempts reached | Force new code request |
| `OTP_RESEND_TOO_SOON` | Requesting code within cooldown window | Disable action button, show countdown timer |
| `PIN_ALREADY_SET` | Account PIN already exists | Route to PIN verification or reset workflow |
| `PIN_INVALID` | Provided PIN is incorrect or unset | Prompt for correct PIN |
| `PIN_LOCKED` | Account locked from excessive failed attempts | Block PIN input, render lockout countdown |
| `EMAIL_DELIVERY_FAILED` | Outbound email transmission failed | Provide inline retry control |
| `INTERNAL_ERROR` | Unhandled backend exception | Show system exception notice and log error |

---

### 6. Endpoint Reference

#### Onboarding Workflow

**Step 1: Sign Up (Firebase Auth Client-Side)**

* Execute via client SDK: `createUserWithEmailAndPassword(email, password)`. Backend interaction is not required for this step.

**Step 2: Dispatch Email Verification OTP**

```http
POST /otp/email/send
Authorization: Bearer <token>
Content-Type: application/json

{}

```

* **Sample Response:**
```json
{
  "success": true,
  "data": {
    "sent": true,
    "expires_in_seconds": 600,
    "resend_available_in_seconds": 10
  },
  "error": null
}

```


* *Note: The recipient address is derived directly from the Firebase session. Do not send email in payload.*

**Step 3: Confirm Email OTP**

```http
POST /otp/email/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "code": "123456"
}

```

* **Sample Response:**
```json
{
  "success": true,
  "data": { "verified": true },
  "error": null
}

```



**Step 4: Create Initial Profile**

```http
POST /users/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "first_name": "David",
  "middle_name": "Chukwuemeka",
  "last_name": "Okafor",
  "country": "NG",
  "phone": "+2348012345678"
}

```

* **Sample Response (`201 Created`):**
```json
{
  "success": true,
  "data": {
    "uid": "WPg41qswdZbxSe1X5McIYJlbEn92",
    "first_name": "David",
    "middle_name": "Chukwuemeka",
    "last_name": "Okafor",
    "tag": null,
    "country": "NG",
    "currency": "NGN",
    "phone": "+2348012345678",
    "email": "user@example.com",
    "email_verified": true,
    "phone_verified": false,
    "identity_verified": false,
    "account_number": "NB0172094612",
    "pin_set": false,
    "avatar_url": null,
    "created_at": "2026-09-23T15:04:44.12Z"
  },
  "error": null
}

```



> **Important:** Returns `403 EMAIL_NOT_VERIFIED` if Step 3 was bypassed. (Note: Google Federated Auth bypasses OTP naturally and proceeds directly).

**Step 5: Claim `@tag**`

```http
POST /users/me/tag
Authorization: Bearer <token>
Content-Type: application/json

{
  "tag": "david"
}

```

* Format validation requires `^[a-z0-9_]+$`. Automatic lowercase normalization is executed. Response outputs the updated profile object.

**Step 6: Configure Transaction PIN**

```http
POST /users/me/pin
Authorization: Bearer <token>
Content-Type: application/json

{
  "pin": "48392"
}

```

* **Sample Response (`201 Created`):**
```json
{
  "success": true,
  "data": { "pin_set": true },
  "error": null
}

```


* Requirements: Exactly **5 digits**. Sequential or repeating series (e.g., `11111`) are rejected.

---

#### Verification & User Management Endpoints

**Verify PIN (Pre-Transaction Gate)**

```http
POST /users/me/pin/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "pin": "48392"
}

```

* *5 consecutive failure attempts yield `429 PIN_LOCKED` triggering a mandatory 20-minute lockout.*

**Reset Transaction PIN**

* Requires prior verification via Firebase Phone Auth. Submit fresh Firebase ID token containing `phone_number` claim:

```http
POST /users/me/pin/reset
Authorization: Bearer <token>

```

**Verify Phone Number (Post-Onboarding)**

```http
POST /users/me/phone/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "phone_number": "+2348012345678"
}

```

**Fetch Profile Info**

```http
GET /users/me
Authorization: Bearer <token>

```

**Update Legal Name** *(Allowed only prior to completing formal identity verification)*

```http
PATCH /users/me/names
Authorization: Bearer <token>
Content-Type: application/json

{
  "first_name": "David",
  "middle_name": "Chukwuemeka",
  "last_name": "Okafor"
}

```

---

### 7. Client Onboarding State Sequence

```text
[Standard Email Registration Path]
1. Firebase client.signUp(email, password)
2. POST /otp/email/send                      --> 200 OK
3. User enters input code from email
4. POST /otp/email/verify                    --> 200 OK
5. POST /users/me                            --> 201 Created (Generates profile + account_number)
6. POST /users/me/tag                        --> 200 OK (Claims handle)
7. POST /users/me/pin                        --> 201 Created (Sets 5-digit PIN)
8. Navigate to App Home Screen

[Google OAuth Registration Path]
1. Firebase client.signInWithCredential()
2. POST /users/me                            --> 201 Created (Skips OTP verification)
3. POST /users/me/tag                        --> 200 OK
4. POST /users/me/pin                        --> 201 Created
5. Navigate to App Home Screen

```

> **Client UI Guidance (Google Auth):** Always prompt the user to confirm/enter their official First, Middle, and Last name manually during Step 2. Legal names must match identity verification documents (KYC).

---

### 8. Integration & Testing Workflows

#### Interactive Swagger UI

Navigate to [https://novabanq-api.onrender.com/docs](https://novabanq-api.onrender.com/docs?utm_source=gemini) to perform manual endpoint verification.

1. Generate a valid user token via the client SDK or direct Firebase Auth API endpoint.
2. Select **Authorize** (top right) in Swagger UI.
3. Paste token string into the authorization input dialog and confirm.

#### Terminal Token Generation Command

```bash
curl -X POST "[https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=YOUR_FIREBASE_WEB_API_KEY](https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=YOUR_FIREBASE_WEB_API_KEY)" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@novabanq.dev","password":"test1234","returnSecureToken":true}'

```

Extract `idToken` from response body to pass within authentication headers.

---

### 9. Environment Capabilities (Hackathon Scope)

| Feature Subsystem | Status | Details |
| --- | --- | --- |
| Firebase Authentication | **Production-Ready** | Fully integrated |
| Firestore Database | **Production-Ready** | Real-time persistence operational |
| Outbound Email OTP | **Production-Ready** | Brevo service integration |
| Phone Auth Verification | **Production-Ready** | Firebase Native SMS Provider |
| BVN / Identity Check | **Mock Integration** | Mocked (Passes validation on regex format check) |
| Biometric Face Sync | **Mock Integration** | Mocked (Returns deterministic positive responses) |
| Virtual Accounts (Flutterwave) | **Sandbox Mode** | Account numbers generated; deposits simulated only |
| Ledger / Transfer Engine | **Under Construction** | Planned for upcoming build cycle |
| Wallet Balances | **Under Construction** | Planned for upcoming build cycle |

---

### 10. Project Directory Layout

```text
app/
├── main.py                     FastAPI application instance initialization
├── api/                        Route aggregation and version control mapping
├── core/                       Environment config, safety handlers, system exceptions
├── infra/                      Third-party adapters (Firebase, Firestore, Brevo, Flutterwave)
└── features/                   Domain-driven design feature modules
    ├── users/                  Profile structures, identity claims, transaction PIN
    ├── otp/                    Email verification delivery logic
    ├── tags/                   Unique handle allocation (@tag)
    ├── account_numbers/        Core bank routing and account creation
    ├── identity/               Government ID / BVN validation logic (mocked)
    ├── virtual_accounts/       Payment gateway bridge (Flutterwave Sandbox)
    ├── accounts/               Balance states (planned)
    ├── funding/                Inbound deposit processing (planned)
    ├── currency/               FX calculations (planned)
    ├── ledger/                 Double-entry bookkeeping (planned)
    ├── transfers/              Outbound transaction handling (planned)
    └── transactions/           Account history and statements (planned)

```

Each feature module is structured cleanly into four discrete layers:

* `router.py` — Controller definitions / API routing interface
* `schemas.py` — Pydantic request / response validation models
* `service.py` — Domain business logic processing
* `repository.py` — Database execution layer (Firestore)

---

### 11. Local Backend Setup

```bash
# Initialize virtual environment
python -m venv .venv

# Activate environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate environment (macOS/Linux)
# source .venv/bin/activate

# Install application dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload

```

#### Required Prerequisites

* Valid `serviceAccountKey.json` placed directly within the root project directory.
* Configured `.env` file populated according to parameters defined in `.env.example`.

---

### 12. Test Execution

```bash
pytest tests/ -v -s

```

*Running `tests/test_auth.py` triggers functional integration tests against a live local server instance bound to Firebase and Firestore. Ensure `FIREBASE_WEB_API_KEY` is present in your local `.env` configuration.*

---

### 13. Technical Support

* **API Specs / Contracts:** Contact the primary Backend Engineer.
* **Authentication Platform:** Consult the project Firebase Console settings panel.

```

```