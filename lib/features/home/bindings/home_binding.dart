import 'package:get/get.dart';
import 'package:novabanq/features/card/controllers/card_controller.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import 'package:novabanq/features/profile/controllers/profile_controller.dart';

class HomeBinding extends Bindings {
  @override
  void dependencies() {
    Get.lazyPut<HomeController>(() => HomeController());
    Get.lazyPut<CardController>(() => CardController());
    Get.lazyPut<ProfileController>(() => ProfileController());
  }
}
