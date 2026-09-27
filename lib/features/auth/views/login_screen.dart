import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import '../controllers/login_controller.dart';
import 'widgets/auth_cta_button.dart';
import 'widgets/auth_text_field.dart';

class LoginScreen extends GetView<LoginController> {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Welcome back',
                    style: GoogleFonts.outfit(
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      color: Colors.black,
                      letterSpacing: -0.6,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Sign in to enter your Novabanq account',
                    style: GoogleFonts.outfit(
                      fontSize: 15,
                      color: const Color(0xFF8C8C8C),
                    ),
                  ),
                  const SizedBox(height: 12),
                  AuthTextField(
                    controller: controller.emailController,
                    label: 'Email address',
                    hintText: 'Enter your email address',
                    keyboardType: TextInputType.emailAddress,
                  ),
                  const SizedBox(height: 16),
                  AuthTextField(
                    controller: controller.passwordController,
                    label: 'Password',
                    hintText: 'Enter your password',
                    obscureText: true,
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton(
                      onPressed: controller.resetPassword,
                      style: TextButton.styleFrom(
                        padding: EdgeInsets.zero,
                        minimumSize: const Size(0, 24),
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        foregroundColor: const Color(0xFF36BE68),
                      ),
                      child: Text(
                        'Forgot password?',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
                  Obx(
                    () => controller.error.value.isEmpty
                        ? const SizedBox.shrink()
                        : Padding(
                            padding: const EdgeInsets.only(top: 12),
                            child: Text(
                              controller.error.value,
                              style: GoogleFonts.outfit(
                                color: const Color(0xFFB42318),
                                fontSize: 13,
                              ),
                            ),
                          ),
                  ),
                  const SizedBox(height: 24),
                  Obx(
                    () => AuthCtaButton(
                      onPressed: controller.busy.value
                          ? () {}
                          : controller.login,
                      text: controller.busy.value
                          ? 'Signing in...'
                          : 'Continue',
                    ),
                  ),
                  const SizedBox(height: 8),
                  Center(
                    child: Wrap(
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          'Don’t have an account? ',
                          style: GoogleFonts.outfit(
                            fontSize: 12,
                            color: const Color(0xFF475467),
                          ),
                        ),
                        TextButton(
                          onPressed: controller.signUp,
                          style: TextButton.styleFrom(
                            padding: EdgeInsets.zero,
                            minimumSize: const Size(0, 24),
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            foregroundColor: Colors.black,
                          ),
                          child: Text(
                            'Sign up',
                            style: GoogleFonts.outfit(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
