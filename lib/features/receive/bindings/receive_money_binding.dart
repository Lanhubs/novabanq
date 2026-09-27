import 'package:get/get.dart';
import '../controllers/receive_money_controller.dart';

class ReceiveMoneyBinding extends Bindings {
  @override
  void dependencies() {
    Get.lazyPut<ReceiveMoneyController>(() => ReceiveMoneyController());
  }
}
