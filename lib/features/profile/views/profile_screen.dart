import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:hugeicons/hugeicons.dart';
import '../controllers/profile_controller.dart';
import 'widgets/profile_logout_button.dart';
import 'widgets/profile_menu_item.dart';
import 'widgets/profile_section_header.dart';
import 'widgets/profile_user_header.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<ProfileController>()
        ? Get.find<ProfileController>()
        : Get.put(ProfileController());

    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 1. User Header
                Obx(
                  () => ProfileUserHeader(
                    userName: controller.userName.value,
                    tierStatus: controller.tierStatus.value,
                  ),
                ),

                // 2. Account Preference Section
                const ProfileSectionHeader(title: 'Account preference'),
                ProfileMenuItem(
                  icon: HugeIcons.strokeRoundedUser,
                  title: 'Personal information',
                  subtitle: 'Manage your legal name and contact',
                  onTap: controller.onPersonalInformationTap,
                ),
                ProfileMenuItem(
                  icon: HugeIcons.strokeRoundedShield01,
                  title: 'Security & Privacy',
                  subtitle: 'Pins, biometrics, & 2 step verification',
                  onTap: controller.onSecurityPrivacyTap,
                ),
                ProfileMenuItem(
                  icon: HugeIcons.strokeRoundedPassport,
                  title: 'Identity & KYC',
                  subtitle: 'NIN, BVN and national ID',
                  onTap: controller.onIdentityKycTap,
                ),
                ProfileMenuItem(
                  icon: HugeIcons.strokeRoundedNotification01,
                  title: 'Notifications',
                  subtitle: 'Instant transaction and rate alerts',
                  onTap: controller.onNotificationsTap,
                ),

                // 3. Settings and Support Section
                const ProfileSectionHeader(title: 'Settings and support'),
                Obx(
                  () => ProfileMenuItem(
                    icon: HugeIcons.strokeRoundedPaintBoard,
                    title: 'Appearance',
                    subtitle: controller.appearanceSetting.value,
                    onTap: controller.onAppearanceTap,
                  ),
                ),
                Obx(
                  () => ProfileMenuItem(
                    icon: HugeIcons.strokeRoundedGlobe,
                    title: 'Language & region',
                    subtitle: controller.languageSetting.value,
                    onTap: controller.onLanguageRegionTap,
                  ),
                ),
                ProfileMenuItem(
                  icon: HugeIcons.strokeRoundedCustomerService01,
                  title: 'Help & support',
                  subtitle: 'FAQs, 24/7 live chat and support',
                  onTap: controller.onHelpSupportTap,
                ),

                const SizedBox(height: 24),

                // 4. Logout Button
                ProfileLogoutButton(
                  onTap: controller.onLogout,
                ),

                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
