import 'package:get/get.dart';
import '../controllers/send_amount_controller.dart';

class SendAmountBinding extends Bindings {
  @override
  void dependencies() {
    Get.lazyPut<SendAmountController>(() => SendAmountController());
  }
}
