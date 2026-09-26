part of 'auth_controller.dart';

extension AuthTagFlow on AuthController {
  Future<void> promptTag(Map<String, dynamic> profile) async {
    if (profile['tag'] != null) return;
    final context = Get.context;
    if (context == null) return;
    await CreateAccountTagInputBottomSheet.show<String>(context);
  }
}
