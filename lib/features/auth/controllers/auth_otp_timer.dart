part of 'auth_controller.dart';

Future<void> tickResend(AuthController controller, int generation) async {
  while (controller.resendSeconds.value > 0 &&
      !controller.isClosed &&
      generation == controller.resendGeneration) {
    await Future.delayed(const Duration(seconds: 1));
    if (!controller.isClosed &&
        generation == controller.resendGeneration &&
        controller.resendSeconds.value > 0) {
      controller.resendSeconds.value--;
    }
  }
}

void handleOtpFailure(AuthController controller, ApiFailure failure) {
  if (failure.code == 'OTP_INVALID' ||
      failure.code == 'OTP_EXPIRED' ||
      failure.code == 'OTP_TOO_MANY_ATTEMPTS') {
    controller.clearVerificationPin();
  }
  if (failure.code == 'OTP_EXPIRED' ||
      failure.code == 'OTP_TOO_MANY_ATTEMPTS') {
    controller.resendSeconds.value = 0;
  }
  if (failure.code == 'OTP_RESEND_TOO_SOON') {
    controller.resendSeconds.value =
        (failure.details['retry_after_seconds'] as num?)?.toInt() ?? 10;
    tickResend(controller, ++controller.resendGeneration);
  }
  if (failure.code == 'EMAIL_NOT_VERIFIED') {
    controller.currentStep.value = 5;
    controller.resendSeconds.value = 0;
  }
}
