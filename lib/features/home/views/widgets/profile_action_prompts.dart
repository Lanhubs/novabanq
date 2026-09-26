import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../../controllers/home_controller.dart';
import 'edit_names_prompt.dart';
import 'reset_pin_prompt.dart';
import 'verify_identity_prompt.dart';
import 'verify_phone_prompt.dart';

class ProfileActionPrompts extends GetView<HomeController> {
  const ProfileActionPrompts({super.key});

  void _open(BuildContext context, Widget child) => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => child,
  );

  @override
  Widget build(BuildContext context) => Obx(() {
    if (controller.isLoading.value) {
      return const LinearProgressIndicator(minHeight: 2);
    }
    if (controller.profileError.value.isNotEmpty) {
      return TextButton(
        onPressed: controller.loadProfile,
        child: Text('${controller.profileError.value} Retry'),
      );
    }
    if (controller.profile.isEmpty) return const SizedBox.shrink();
    final profile = controller.profile;
    final phone = profile['phone']?.toString() ?? '';
    return Wrap(
      alignment: WrapAlignment.center,
      children: [
        if (profile['phone_verified'] != true)
          TextButton(
            onPressed: () => _open(
              context,
              VerifyPhonePrompt(
                phone: phone,
                onVerified: controller.loadProfile,
              ),
            ),
            child: const Text('Verify phone number'),
          ),
        if (profile['identity_verified'] != true) ...[
          TextButton(
            onPressed: () => _open(
              context,
              VerifyIdentityPrompt(onVerified: controller.loadProfile),
            ),
            child: const Text('Verify identity'),
          ),
          TextButton(
            onPressed: () => _open(
              context,
              EditNamesPrompt(
                profile: profile,
                onSaved: controller.loadProfile,
              ),
            ),
            child: const Text('Edit legal name'),
          ),
        ],
        if (profile['pin_set'] == true)
          TextButton(
            onPressed: () => _open(
              context,
              ResetPinPrompt(phone: phone, onSaved: controller.loadProfile),
            ),
            child: const Text('Reset PIN'),
          ),
      ],
    );
  });
}
