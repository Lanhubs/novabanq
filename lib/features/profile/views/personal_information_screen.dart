import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../controllers/profile_controller.dart';
import 'widgets/personal_info_avatar.dart';
import 'widgets/personal_info_row.dart';
import 'widgets/profile_top_bar.dart';

class PersonalInformationScreen extends StatelessWidget {
  const PersonalInformationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<ProfileController>()
        ? Get.find<ProfileController>()
        : Get.put(ProfileController());

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const ProfileTopBar(title: 'Personal information'),
                  const SizedBox(height: 24),
                  PersonalInfoAvatar(
                    onTap: controller.onChangeAvatar,
                  ),
                  const SizedBox(height: 28),
                  Obx(
                    () => PersonalInfoRow(
                      label: 'Novabanq account number',
                      value: controller.accountNumber.value,
                      actionIcon: Icons.copy_rounded,
                      onAction: controller.copyAccountNumber,
                    ),
                  ),
                  Obx(
                    () => PersonalInfoRow(
                      label: 'Account name',
                      value: controller.accountName.value,
                    ),
                  ),
                  Obx(
                    () => PersonalInfoRow(
                      label: 'Date of birth',
                      value: controller.dateOfBirth.value,
                      actionIcon: Icons.edit_outlined,
                      onAction: controller.onEditDateOfBirth,
                    ),
                  ),
                  Obx(
                    () => PersonalInfoRow(
                      label: 'Email address',
                      value: controller.emailAddress.value,
                      actionIcon: Icons.edit_outlined,
                      onAction: controller.onEditEmail,
                    ),
                  ),
                  Obx(
                    () => PersonalInfoRow(
                      label: 'Mobile number',
                      value: controller.mobileNumber.value,
                    ),
                  ),
                  Obx(
                    () => PersonalInfoRow(
                      label: 'Gender',
                      value: controller.gender.value,
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
