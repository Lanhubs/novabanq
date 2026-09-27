import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../controllers/security_privacy_controller.dart';
import 'widgets/profile_top_bar.dart';
import 'widgets/security_biometric_tile.dart';
import 'widgets/security_menu_tile.dart';

class SecurityPrivacyScreen extends StatelessWidget {
  const SecurityPrivacyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<SecurityPrivacyController>()
        ? Get.find<SecurityPrivacyController>()
        : Get.put(SecurityPrivacyController());

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const ProfileTopBar(title: 'Security & privacy'),
                  const SizedBox(height: 24),

                  // Biometric Login Toggle
                  Obx(
                    () => SecurityBiometricTile(
                      isEnabled: controller.isBiometricEnabled.value,
                      onChanged: controller.toggleBiometrics,
                    ),
                  ),

                  // Transaction Pin
                  Obx(
                    () => SecurityMenuTile(
                      icon: Icons.lock_outline_rounded,
                      title: 'Transaction pin',
                      subtitle: controller.transactionPinStatus.value,
                      onTap: controller.onChangeTransactionPin,
                    ),
                  ),

                  // Account Password
                  Obx(
                    () => SecurityMenuTile(
                      icon: Icons.vpn_key_outlined,
                      title: 'Account password',
                      subtitle: controller.accountPasswordStatus.value,
                      onTap: controller.onChangePassword,
                    ),
                  ),

                  // SMS & Whatsapp Authentication
                  Obx(
                    () => SecurityMenuTile(
                      icon: Icons.verified_user_outlined,
                      title: 'SMS & Whatsapp authentication',
                      subtitle: controller.authMethodStatus.value,
                      subtitleColor: const Color(0xFF12B76A),
                      onTap: controller.onAuthMethodTap,
                    ),
                  ),

                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
