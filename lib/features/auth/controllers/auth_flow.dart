part of 'auth_controller.dart';

extension AuthFlow on AuthController {
  Future<void> advance() async {
    if (busy.value) return;
    error.value = '';
    switch (currentStep.value) {
      case 0:
        currentStep.value = 1;
      case 1:
        if (emailController.text.trim().contains('@')) {
          currentStep.value = 2;
        } else {
          error.value = 'Enter a valid email address.';
        }
      case 2:
        if ([
          firstNameController,
          middleNameController,
          lastNameController,
        ].every((item) => item.text.trim().isNotEmpty)) {
          currentStep.value = googleSignup.value ? 4 : 3;
        } else {
          error.value = 'Enter all three legal names.';
        }
      case 3:
        await _register();
      case 4:
        if (e164Phone.length < 8 || e164Phone.length > 20) {
          error.value = 'Enter a valid phone number.';
        } else if (googleSignup.value) {
          await _createProfile();
        } else {
          currentStep.value = 5;
        }
      case 5:
        await verifyEmailCode();
      case 6:
        if (RegExp(r'^\d{11}$').hasMatch(bvnController.text.trim()) &&
            isBvnConfirmed.value) {
          currentStep.value = 7;
        } else {
          error.value = 'Enter and confirm a valid 11-digit BVN.';
        }
      case 8:
        await _setPin();
    }
  }

  Future<void> _register() async {
    if (!FirebaseBootstrap.ready) {
      error.value = 'Firebase setup is required.';
      return;
    }
    if (passwordController.text.length < 6 ||
        passwordController.text != confirmPasswordController.text) {
      error.value = 'Check your password and confirmation.';
      return;
    }
    await _run(() async {
      if (FirebaseAuth.instance.currentUser?.email !=
          emailController.text.trim()) {
        try {
          await FirebaseAuth.instance.createUserWithEmailAndPassword(
            email: emailController.text.trim(),
            password: passwordController.text,
          );
        } on FirebaseAuthException catch (failure) {
          if (failure.code != 'email-already-in-use') rethrow;
          await FirebaseAuth.instance.signInWithEmailAndPassword(
            email: emailController.text.trim(),
            password: passwordController.text,
          );
        }
      }
      await _sendEmailCode();
      currentStep.value = 4;
    });
  }

  Future<void> googleSignIn() async {
    if (!FirebaseBootstrap.ready) {
      error.value = 'Firebase setup is required.';
      return;
    }
    await _run(() async {
      final signIn = GoogleSignIn.instance;
      await signIn.initialize(
        clientId:
            defaultTargetPlatform == TargetPlatform.iOS &&
                FirebaseBootstrap.googleIosClientId.isNotEmpty
            ? FirebaseBootstrap.googleIosClientId
            : null,
        serverClientId: FirebaseBootstrap.googleClientId.isEmpty
            ? null
            : FirebaseBootstrap.googleClientId,
      );
      final account = await signIn.authenticate();
      final idToken = account.authentication.idToken;
      if (idToken == null) {
        throw const ApiFailure('AUTH_INVALID', 'Google sign-in failed.');
      }
      await FirebaseAuth.instance.signInWithCredential(
        GoogleAuthProvider.credential(idToken: idToken),
      );
      googleSignup.value = true;
      emailController.text = account.email;
      currentStep.value = 2;
    });
  }

  Future<void> _sendEmailCode() async {
    final result = await api.sendEmailOtp();
    resendSeconds.value =
        (result['resend_available_in_seconds'] as num?)?.toInt() ?? 10;
    tickResend(this, ++resendGeneration);
  }

  Future<void> sendEmailCode() async {
    if (resendSeconds.value > 0 || busy.value) return;
    clearVerificationPin();
    await _run(_sendEmailCode);
  }

  Future<void> verifyEmailCode() async {
    if (verificationPin.value.length != 6) {
      error.value = 'Enter the 6-digit email code.';
      return;
    }
    await _run(() async {
      await api.verifyEmailOtp(verificationPin.value);
      final profile = await _createProfileRequest();
      await promptTag(profile);
      currentStep.value = 8;
    });
  }

  Future<void> _createProfile() async {
    await _run(() async {
      final profile = await _createProfileRequest();
      await promptTag(profile);
      currentStep.value = 8;
    });
  }

  Future<Map<String, dynamic>> _createProfileRequest() async {
    late Map<String, dynamic> profile;
    try {
      profile = await api.create(
        firstName: firstNameController.text.trim(),
        middleName: middleNameController.text.trim(),
        lastName: lastNameController.text.trim(),
        country: selectedCountry.value.code,
        phone: e164Phone,
      );
    } on ApiFailure catch (failure) {
      if (failure.code != 'USER_ALREADY_EXISTS') rethrow;
      profile = await api.profile();
    }
    await FirebaseAuth.instance.currentUser?.updateDisplayName(fullName);
    return profile;
  }

  Future<void> _setPin() async {
    final pin = accountPin.value;
    if (!RegExp(r'^\d{5}$').hasMatch(pin)) {
      error.value = 'Enter a 5-digit PIN.';
      return;
    }
    await _run(() async {
      try {
        await api.setPin(pin);
      } on ApiFailure catch (failure) {
        if (failure.code != 'PIN_ALREADY_SET') rethrow;
      }
      accountPin.value = '';
      Get.offAllNamed(AppRoutes.accountSuccess);
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    if (busy.value) return;
    busy.value = true;
    error.value = '';
    try {
      await action();
    } on ApiFailure catch (failure) {
      handleOtpFailure(this, failure);
      error.value = failure.message;
    } on FirebaseAuthException catch (failure) {
      error.value = failure.message ?? 'Authentication failed.';
    } catch (_) {
      error.value = 'Unable to complete this step. Try again.';
    } finally {
      busy.value = false;
    }
  }
}
