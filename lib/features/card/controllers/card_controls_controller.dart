import 'package:get/get.dart';
import 'package:novabanq/core/utils/helpers.dart';

class CardControlsController extends GetxController {
  final isOnlinePaymentsEnabled = true.obs;
  final isInternationalUseEnabled = true.obs;
  final isAtmWithdrawalsEnabled = false.obs;
  final isContactlessEnabled = true.obs;

  void toggleOnlinePayments(bool value) {
    isOnlinePaymentsEnabled.value = value;
    _showFeedback('Online payments', value);
  }

  void toggleInternationalUse(bool value) {
    isInternationalUseEnabled.value = value;
    _showFeedback('International use', value);
  }

  void toggleAtmWithdrawals(bool value) {
    isAtmWithdrawalsEnabled.value = value;
    _showFeedback('ATM withdrawals', value);
  }

  void toggleContactless(bool value) {
    isContactlessEnabled.value = value;
    _showFeedback('Contactless payments', value);
  }

  void _showFeedback(String title, bool isEnabled) {
    SnackBarHelper.showSuccess(
      message: isEnabled ? '$title enabled' : '$title disabled',
      title: title,
      position: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 2),
    );
  }
}
