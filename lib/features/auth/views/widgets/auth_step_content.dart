import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';
import '../steps/bvn_step_view.dart';
import '../steps/country_step_view.dart';
import '../steps/create_pin_step_view.dart';
import '../steps/email_step_view.dart';
import '../steps/face_verification_step_view.dart';
import '../steps/name_step_view.dart';
import '../steps/password_step_view.dart';
import '../steps/phone_number_step_view.dart';
import '../steps/phone_verification_step_view.dart';

class AuthStepContent extends GetView<AuthController> {
  final double horizontalPadding;
  final double topSpacing;

  const AuthStepContent({
    super.key,
    required this.horizontalPadding,
    required this.topSpacing,
  });

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      switch (controller.currentStep.value) {
        // Bracket 1: [Country -> Email]
        case 0:
          return _AuthScrollableStepWrapper(
            horizontalPadding: horizontalPadding,
            topSpacing: topSpacing,
            child: CountryStepView(
              selectedCountry: controller.selectedCountry.value,
              countries: controller.countries,
              isDropdownOpen: controller.isCountryDropdownOpen.value,
              onToggleDropdown: controller.toggleCountryDropdown,
              onSelectCountry: controller.selectCountry,
              onContinue: controller.nextStep,
            ),
          );
        case 1:
          return _AuthScrollableStepWrapper(
            horizontalPadding: horizontalPadding,
            topSpacing: topSpacing,
            child: EmailStepView(
              controller: controller.emailController,
              onContinue: controller.nextStep,
              onGoogleSignUp: controller.signInWithGoogle,
            ),
          );

        // Bracket 2: [Name -> Password]
        case 2:
          return _AuthScrollableStepWrapper(
            horizontalPadding: horizontalPadding,
            topSpacing: topSpacing,
            child: NameStepView(
              firstNameController: controller.firstNameController,
              middleNameController: controller.middleNameController,
              lastNameController: controller.lastNameController,
              onContinue: controller.nextStep,
            ),
          );
        case 3:
          return _AuthScrollableStepWrapper(
            horizontalPadding: horizontalPadding,
            topSpacing: topSpacing,
            child: Obx(
              () => PasswordStepView(
                passwordController: controller.passwordController,
                confirmPasswordController: controller.confirmPasswordController,
                isPasswordVisible: controller.isPasswordVisible.value,
                isConfirmPasswordVisible:
                    controller.isConfirmPasswordVisible.value,
                onTogglePasswordVisibility: controller.togglePasswordVisibility,
                onToggleConfirmPasswordVisibility:
                    controller.toggleConfirmPasswordVisibility,
                onContinue: controller.nextStep,
              ),
            ),
          );

        // Bracket 3: [Phone -> Number Verification Status]
        case 4:
          return Obx(
            () => PhoneNumberStepView(
              horizontalPadding: horizontalPadding,
              selectedCountry: controller.selectedCountry.value,
              phoneNumber: controller.phoneNumber.value,
              onKeyPress: controller.appendPhoneNumberDigit,
              onBackspace: controller.deletePhoneNumberDigit,
              onClear: controller.clearPhoneNumber,
              onContinue: controller.nextStep,
            ),
          );
        case 5:
          return Obx(
            () => PhoneVerificationStepView(
              horizontalPadding: horizontalPadding,
              pin: controller.verificationPin.value,
              maskedPhone: controller.maskedPhoneNumber,
              onKeyPress: controller.appendVerificationDigit,
              onBackspace: controller.deleteVerificationDigit,
              onClear: controller.clearVerificationPin,
              onResend: controller.resendVerificationCode,
              resendSeconds: controller.resendSeconds.value,
              onContinue: controller.handlePhoneVerificationDone,
            ),
          );

        // Bracket 4: [BVN -> Face Verification -> PIN creation]
        case 6:
          return _AuthScrollableStepWrapper(
            horizontalPadding: horizontalPadding,
            topSpacing: topSpacing,
            child: Obx(
              () => BvnStepView(
                controller: controller.bvnController,
                isConfirmed: controller.isBvnConfirmed.value,
                onToggleConfirm: controller.toggleBvnConfirmation,
                onConfirm: controller.nextStep,
              ),
            ),
          );
        case 7:
          return Padding(
            padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
            child: FaceVerificationStepView(
              onTakeSelfie: controller.takeSelfie,
            ),
          );
        case 8:
          return Obx(
            () => CreatePinStepView(
              horizontalPadding: horizontalPadding,
              pin: controller.accountPin.value,
              onKeyPress: controller.appendAccountPinDigit,
              onBackspace: controller.deleteAccountPinDigit,
              onClear: controller.clearAccountPin,
              onContinue: controller.nextStep,
            ),
          );
        default:
          return const SizedBox.shrink();
      }
    });
  }
}

class _AuthScrollableStepWrapper extends StatelessWidget {
  final double horizontalPadding;
  final double topSpacing;
  final Widget child;

  const _AuthScrollableStepWrapper({
    required this.horizontalPadding,
    required this.topSpacing,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(height: topSpacing),
          child,
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}
