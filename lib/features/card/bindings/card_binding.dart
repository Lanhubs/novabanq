import 'package:get/get.dart';
import '../controllers/card_controller.dart';
import '../controllers/card_controls_controller.dart';

class CardBinding extends Bindings {
  @override
  void dependencies() {
    Get.lazyPut<CardController>(() => CardController());
    Get.lazyPut<CardControlsController>(() => CardControlsController());
  }
}