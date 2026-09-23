# NovaBanq — Frontend Authentication Implementation Guide

**Audience:** The Flutter developer integrating with the NovaBanq backend.

**Goal:** Implement email/password signup, Google Sign-In, and phone (SMS) verification in Flutter using Firebase Auth, and correctly hand the resulting token off to the NovaBanq backend.

---

## Table of Contents

1. [Why Firebase Auth Lives in the Frontend](#1-why-firebase-auth-lives-in-the-frontend)
2. [Setup: Add Firebase to Your Flutter Project](#2-setup-add-firebase-to-your-flutter-project)
3. [Email/Password Signup](#3-emailpassword-signup)
4. [Google Sign-In](#4-google-sign-in)
5. [Phone Verification (SMS OTP)](#5-phone-verification-sms-otp)
6. [Testing Without Real SMS](#6-testing-without-real-sms)
7. [The Complete Onboarding Flow](#7-the-complete-onboarding-flow)
8. [Getting the Token in Your HTTP Calls](#8-getting-the-token-in-your-http-calls)
9. [Handling Token Expiry](#9-handling-token-expiry)
10. [Summary: What You Build vs What Firebase Builds](#10-summary-what-you-build-vs-what-firebase-builds)
11. [Common Errors](#11-common-errors)

---

## 1. Why Firebase Auth Lives in the Frontend

Before writing any code, understand the architecture. **This is not a workaround — it's the intended pattern.**

### The division of responsibility

**Firebase Authentication** is an identity provider, not your backend. It handles:

- Creating users with email/password
- Google Sign-In
- Phone number verification (SMS)
- Password reset emails
- Token issuance and automatic refresh

**The NovaBanq backend** handles:

- Verifying the token Firebase issues
- Loading the user's NovaBanq profile
- Balances, transfers, KYC, and everything else business-specific

### Why the backend doesn't create users directly

If the backend handled signup itself, it would need to **store passwords** — a serious liability. With Firebase Auth, the backend **never sees or stores passwords**. Firebase hashes them on Google's infrastructure, and the backend receives a signed token asserting "this user is who they claim to be."

### The end-to-end flow

1. Flutter calls the Firebase SDK: `signUp(email, password)` or `signInWithCredential(googleCredential)`.
2. Firebase creates/signs in the user and returns an **ID token**.
3. Flutter sends that token to NovaBanq: `Authorization: Bearer <token>`.
4. The backend calls `verify_id_token(token)` and extracts the `uid`.
5. The backend creates/returns the NovaBanq profile for that `uid`.

> **Key takeaway:** the backend never sees a password — only a token.

---

## 2. Setup: Add Firebase to Your Flutter Project

### Step 1 — Install the FlutterFire CLI

The FlutterFire CLI is the easiest way to configure Firebase across all platforms.

```bash
# Install Firebase CLI first (if not already installed)
npm install -g firebase-tools

# Log in
firebase login

# Install FlutterFire CLI
dart pub global activate flutterfire_cli

# Verify installation
flutterfire --help
```

### Step 2 — Configure your Flutter app

Run this from the Flutter project root:

```bash
flutterfire configure
```

This command:

- Prompts you to select the Firebase project (`novabanq-ec947`)
- Prompts you to select target platforms (Android, iOS, Web)
- **Auto-generates `lib/firebase_options.dart`** with all config values
- **Auto-creates platform-specific config files** (`google-services.json` for Android, `GoogleService-Info.plist` for iOS)

> You do **not** need to manually download or place any config files — the CLI handles it.

### Step 3 — Add dependencies

In `pubspec.yaml`:

```yaml
dependencies:
  firebase_core: ^3.15.0
  firebase_auth: ^5.6.1
  google_sign_in: ^6.3.0        # For Google Sign-In
  http: ^1.2.0                   # For calling the NovaBanq API
```

Then run:

```bash
flutter pub get
```

### Step 4 — Initialize Firebase in `main.dart`

```dart
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const MyApp());
}
```

`DefaultFirebaseOptions.currentPlatform` automatically picks the right config for the current platform (Android/iOS/Web) — no platform-specific initialization code needed.

---

## 3. Email/Password Signup

### Step 1 — Create the user

```dart
import 'package:firebase_auth/firebase_auth.dart';

Future<UserCredential?> signUpWithEmail(String email, String password) async {
  try {
    final credential = await FirebaseAuth.instance
        .createUserWithEmailAndPassword(
      email: email,
      password: password,
    );
    return credential;
  } on FirebaseAuthException catch (e) {
    if (e.code == 'weak-password') {
      // Handle: password too weak
    } else if (e.code == 'email-already-in-use') {
      // Handle: email already registered
    } else if (e.code == 'invalid-email') {
      // Handle: malformed email
    }
    return null;
  }
}
```

Firebase creates the user in its own system, and the user becomes authenticated. `credential.user.uid` is the Firebase `uid` — **this is the same `uid` the NovaBanq backend will use.**

### Step 2 — Get the ID token

```dart
final user = FirebaseAuth.instance.currentUser;
final idToken = await user?.getIdToken();
```

> **Important:** ID tokens expire after **1 hour**. Always call `getIdToken()` fresh before each API request rather than caching the token string yourself — the Firebase SDK caches it internally and refreshes it automatically.

### Step 3 — Send the token to NovaBanq

```dart
final response = await http.post(
  Uri.parse('https://novabanq-api.onrender.com/api/v1/users/me'),
  headers: {
    'Authorization': 'Bearer $idToken',
    'Content-Type': 'application/json',
  },
  body: jsonEncode({
    'first_name': 'David',
    'middle_name': 'Chukwuemeka',
    'last_name': 'Okafor',
    'country': 'NG',
    'phone': '+2348012345678',
  }),
);
```

> **Note:** This request returns `403 EMAIL_NOT_VERIFIED` until the user completes email OTP — see the [complete onboarding flow](#7-the-complete-onboarding-flow) below.

---

## 4. Google Sign-In

### Step 1 — Enable Google Sign-In in Firebase Console

1. Firebase Console → **Authentication** → **Sign-in method**
2. Click **Google** → **Enable** → Save
3. Download the updated `google-services.json` and replace the existing one

### Step 2 — Add the SHA-1 fingerprint (Android only)

Google Sign-In on Android requires your app's SHA-1 fingerprint to be registered in Firebase.

```bash
cd android
./gradlew signingReport
```

Copy the SHA-1 value from the debug variant, then add it in Firebase Console → **Project Settings** → **Your apps** → **Android** → **Add fingerprint**.

> ⚠️ **This step is often missed and causes `ApiException: 10` errors. Do not skip it.**

### Step 3 — Implement Google Sign-In

```dart
import 'package:google_sign_in/google_sign_in.dart';

Future<UserCredential?> signInWithGoogle() async {
  try {
    // Trigger the Google Sign-In flow
    final GoogleSignInAccount? googleUser = await GoogleSignIn.instance.authenticate();

    if (googleUser == null) {
      return null; // User cancelled
    }

    // Obtain the auth details from the request
    final GoogleSignInAuthentication googleAuth = await googleUser.authentication;

    // Create a new credential for Firebase
    final credential = GoogleAuthProvider.credential(
      idToken: googleAuth.idToken,
    );

    // Sign in to Firebase with the Google credential
    return await FirebaseAuth.instance.signInWithCredential(credential);

  } on FirebaseAuthException catch (e) {
    // Handle errors
    return null;
  }
}
```

Firebase receives the Google token, verifies it with Google, and either creates a new user or signs in the existing one. The resulting Firebase ID token contains `firebase.sign_in_provider: "google.com"`, which tells the NovaBanq backend to **skip email OTP** since Google already verified the email.

> **Still ask for the user's name after Google sign-in.** The name from Google may not match their government ID, and the backend needs the exact legal name for KYC.

### Step 4 — Sign out

```dart
await GoogleSignIn.instance.signOut();
await FirebaseAuth.instance.signOut();
```

---

## 5. Phone Verification (SMS OTP)

> **Phone verification happens on the dashboard, not during signup.** Users can browse the app before verifying their phone.

### Step 1 — Enable Phone Sign-In in Firebase Console

1. Firebase Console → **Authentication** → **Sign-in method**
2. Click **Phone** → **Enable** → Save

### Step 2 — Add SHA-256 for Android (production only)

SHA-1 is enough for testing on a real device. For production, also add SHA-256 and enable the **Google Play Integrity API**.

### Step 3 — Trigger phone verification

```dart
Future<void> verifyPhoneNumber(String phoneNumber) async {
  await FirebaseAuth.instance.verifyPhoneNumber(
    phoneNumber: phoneNumber,
    verificationCompleted: (PhoneAuthCredential credential) async {
      // Android ONLY: auto-retrieval of SMS code
      await FirebaseAuth.instance.signInWithCredential(credential);
      // Now call NovaBanq POST /users/me/phone/verify
    },
    verificationFailed: (FirebaseAuthException e) {
      // Handle error (e.g., invalid phone number, quota exceeded)
      print('Verification failed: ${e.message}');
    },
    codeSent: (String verificationId, int? resendToken) {
      // SMS sent. Show OTP input screen.
      // Store verificationId for the next step.
    },
    codeAutoRetrievalTimeout: (String verificationId) {
      // Auto-retrieval timed out. User must enter code manually.
    },
  );
}
```

**The four callbacks:**

| Callback | When it fires |
|---|---|
| `verificationCompleted` | Android auto-reads the SMS. Only fires on some devices. |
| `verificationFailed` | Something went wrong (invalid number, quota exceeded). |
| `codeSent` | SMS was sent. Show the OTP input screen. |
| `codeAutoRetrievalTimeout` | Auto-read timed out. User must enter the code manually. |

### Step 4 — Verify the SMS code

After the user enters the 6-digit code:

```dart
final credential = PhoneAuthProvider.credential(
  verificationId: verificationId,
  smsCode: enteredCode,
);

await FirebaseAuth.instance.signInWithCredential(credential);
```

> ⚠️ **Critical:** this call **replaces** the current Firebase session. If the user signed up with email, calling `signInWithCredential` here will switch them to a **new `uid`** — but their NovaBanq profile is tied to the old one.

**Do not call `signInWithCredential` if the user already has a session.** Use `linkWithCredential` instead:

```dart
final user = FirebaseAuth.instance.currentUser;
final credential = PhoneAuthProvider.credential(
  verificationId: verificationId,
  smsCode: enteredCode,
);

// Link phone to the EXISTING account, preserving the uid
await user?.linkWithCredential(credential);
```

After linking, force a fresh token:

```dart
final token = await user?.getIdToken(true); // true = force refresh
```

The token now contains a `phone_number` claim. Send it to:

```
POST /api/v1/users/me/phone/verify
Body: { "phone_number": "+2348012345678" }
```

The backend extracts the `phone_number` claim from the token and verifies it matches the profile.

---

## 6. Testing Without Real SMS

Firebase Console supports **test phone numbers** — fictional numbers with a fixed verification code, so you can test the flow without sending real SMS.

### Setup

1. Firebase Console → **Authentication** → **Sign-in method** → **Phone**
2. Expand **Phone numbers for testing**
3. Add `+2348012345678` with code `123456`
4. Save

### At runtime

When the app calls `verifyPhoneNumber()` with `+2348012345678`:

- **No real SMS is sent**
- The `codeSent` callback fires normally
- The user enters `123456`
- Firebase verifies it and returns a valid token

This exercises the full production flow with no backend bypass required.

---

## 7. The Complete Onboarding Flow

### Email/password signup

```
 1. User taps "Sign Up"
 2. Firebase createUserWithEmailAndPassword(email, password)
 3. → User is authenticated, uid exists in Firebase
 4. → Call NovaBanq POST /otp/email/send            (body: {})
 5. → User checks email, enters 6-digit code
 6. → Call NovaBanq POST /otp/email/verify           (body: {"code": "123456"})
 7. → Call NovaBanq POST /users/me                   (profile details)
 8. → Call NovaBanq GET  /users/me/tag/check?tag=david323
 9. → Call NovaBanq POST /users/me/tag               (body: {"tag": "david323"})
10. → Call NovaBanq POST /users/me/pin               (body: {"pin": "48392"})
11. → Navigate to Dashboard
```

### Google Sign-In

```
1. User taps "Sign in with Google"
2. Google Sign-In flow completes
3. Firebase signInWithCredential(googleCredential)
4. → Skip steps 4–6 above (email already verified by Google)
5. → Call NovaBanq POST /users/me (profile details)
6. → Continue from step 8 above
```

---

## 8. Getting the Token in Your HTTP Calls

Centralize token attachment in a single API client so every call is consistent:

```dart
class ApiClient {
  static const String baseUrl = 'https://novabanq-api.onrender.com/api/v1';

  static Future<Map<String, String>> headers() async {
    final token = await FirebaseAuth.instance.currentUser?.getIdToken();
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  static Future<Map<String, dynamic>> get(String path) async {
    final response = await http.get(
      Uri.parse('$baseUrl$path'),
      headers: await headers(),
    );
    return jsonDecode(response.body);
  }

  static Future<Map<String, dynamic>> post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: await headers(),
      body: jsonEncode(body),
    );
    return jsonDecode(response.body);
  }
}
```

> **Always call `getIdToken()` fresh** rather than storing the token string — the SDK caches and refreshes it internally.

---

## 9. Handling Token Expiry

If any API call returns `401 AUTH_INVALID`:

1. Call `FirebaseAuth.instance.currentUser?.getIdToken(true)` to force a refresh.
2. Retry the request **once**.
3. If it fails again, the user needs to re-login.

> Put this retry logic in the `ApiClient` helper — **not** duplicated across every endpoint call.

---

## 10. Summary: What You Build vs What Firebase Builds

| Task | Who builds it |
|---|---|
| Signup form UI | You (Flutter) |
| Password validation UI | You (Flutter) |
| Google Sign-In button | You (Flutter) |
| OTP input screen | You (Flutter) |
| Calling the Firebase SDK | You (Flutter) |
| Getting the ID token | You (Flutter) |
| Sending the token to NovaBanq | You (Flutter) |
| **Actually creating the user** | Firebase |
| **Hashing the password** | Firebase |
| **Sending password reset emails** | Firebase |
| **Google OAuth flow** | Firebase + Google |
| **Sending SMS OTP** | Firebase |
| **Verifying the token server-side** | NovaBanq backend |

**You are the client.** Firebase is the identity service. NovaBanq is the application backend. Each has its job — don't try to make one do another's work.

---

## 11. Common Errors

| Error | Cause | Fix |
|---|---|---|
| `ApiException: 10` (Google Sign-In, Android) | Missing SHA-1 fingerprint in Firebase Console | Project Settings → Your apps → Android → **Add fingerprint** |
| `invalid-phone-number` | Phone not in E.164 format | Use `+2348012345678`, not `08012345678` |
| `401 AUTH_INVALID` on NovaBanq calls | Token expired | Call `getIdToken(true)` and retry once |
| `403 EMAIL_NOT_VERIFIED` | User hasn't completed email OTP | Route them back to the OTP screen |
| "Firebase not initialized" | `Firebase.initializeApp()` not called before an Auth call | Ensure it's awaited in `main()` before `runApp()` |

---

**Questions?** Ping the backend engineer with the exact request, the exact response, and the `error.code` value.