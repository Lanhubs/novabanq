import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/utils/helpers.dart';
import 'package:novabanq/core/network/profile_api.dart';
import 'package:novabanq/core/services/firebase_bootstrap.dart';

class LoginController extends GetxController {
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  final busy = false.obs;
  final error = ''.obs;

  Future<void> login() async {
    if (busy.value) return;
    final email = emailController.text.trim();
    if (!email.contains('@') || passwordController.text.isEmpty) {
      error.value = 'Enter your email address and password.';
      return;
    }
    if (!FirebaseBootstrap.ready) {
      error.value = 'Sign in is unavailable. Please try again later.';
      return;
    }
    busy.value = true;
    error.value = '';
    try {
      await FirebaseAuth.instance.signInWithEmailAndPassword(
        email: email,
        password: passwordController.text,
      );
      await ProfileApi(ApiClient()).profile();
      Get.offAllNamed(AppRoutes.home);
    } on FirebaseAuthException catch (failure) {
      error.value = switch (failure.code) {
        'invalid-email' => 'Enter a valid email address.',
        'wrong-password' ||
        'invalid-credential' ||
        'user-not-found' => 'Email or password is incorrect.',
        'too-many-requests' => 'Too many attempts. Please try again later.',
        _ => failure.message ?? 'Unable to sign in. Please try again.',
      };
    } on ApiFailure catch (failure) {
      error.value = failure.message;
    } catch (_) {
      error.value = 'Unable to sign in. Check your connection and try again.';
    } finally {
      busy.value = false;
    }
  }

  Future<void> resetPassword() async {
    final email = emailController.text.trim();
    if (!email.contains('@')) {
      error.value = 'Enter your email address to reset your password.';
      return;
    }
    if (!FirebaseBootstrap.ready) {
      error.value = 'Password reset is unavailable. Please try again later.';
      return;
    }
    try {
      await FirebaseAuth.instance.sendPasswordResetEmail(email: email);
      error.value = '';
      SnackBarHelper.showSuccess(
        message: 'A password reset link has been sent.',
        title: 'Check your email',
        position: SnackPosition.TOP,
      );
    } on FirebaseAuthException catch (failure) {
      error.value = failure.message ?? 'Unable to send a reset link.';
    } catch (_) {
      error.value = 'Unable to send a reset link. Try again.';
    }
  }

  void signUp() => Get.offNamed(AppRoutes.auth);

  @override
  void onClose() {
    emailController.dispose();
    passwordController.dispose();
    super.onClose();
  }
}
