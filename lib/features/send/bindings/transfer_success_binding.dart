import 'package:get/get.dart';
import '../controllers/transfer_success_controller.dart';

class TransferSuccessBinding extends Bindings {
  @override
  void dependencies() {
    Get.lazyPut<TransferSuccessController>(() => TransferSuccessController());
  }
}
