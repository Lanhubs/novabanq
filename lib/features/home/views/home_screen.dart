import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/card/views/card_screen.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import 'package:novabanq/features/profile/views/profile_screen.dart';
import 'widgets/home_bottom_nav_bar.dart';
import 'widgets/home_tab_view.dart';

class HomeScreen extends GetView<HomeController> {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Obx(() {
        if (controller.currentNavIndex.value == 1) {
          return const CardScreen();
        }
        if (controller.currentNavIndex.value == 3) {
          return const ProfileScreen();
        }
        return const HomeTabView();
      }),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: [
              Obx(
                () => HomeBottomNavBar(
                  currentIndex: controller.currentNavIndex.value,
                  onTabSelected: controller.onSelectNavTab,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
