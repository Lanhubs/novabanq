import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import 'widgets/home_account_number_card.dart';
import 'widgets/home_balance_section.dart';
import 'widgets/home_bottom_nav_bar.dart';
import 'widgets/home_promo_banner.dart';
import 'widgets/home_quick_actions.dart';
import 'widgets/home_top_bar.dart';
import 'widgets/home_transactions_section.dart';
import 'widgets/profile_action_prompts.dart';

class HomeScreen extends GetView<HomeController> {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final horizontalPadding = (constraints.maxWidth * 0.055).clamp(
                  18.0,
                  24.0,
                );

                return Column(
                  children: [
                    Padding(
                      padding: EdgeInsets.only(
                        left: horizontalPadding,
                        right: horizontalPadding,
                        top: 12,
                      ),
                      child: Obx(
                        () => HomeTopBar(
                          userName: controller.greetingName,
                          accountTag: controller.accountTag.value,
                          onNotificationTap: controller.onNotificationTap,
                          onAddAccountTagTap: controller.onAddAccountTag,
                        ),
                      ),
                    ),
                    Expanded(
                      child: SingleChildScrollView(
                        physics: const BouncingScrollPhysics(),
                        padding: EdgeInsets.only(
                          left: horizontalPadding,
                          right: horizontalPadding,
                          bottom: 12,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            const SizedBox(height: 22),

                            // Currency Pill + Balance + Eye Toggle
                            Obx(
                              () => HomeBalanceSection(
                                balance: controller.balanceAmount,
                                currencyCode: controller.selectedCurrency.value,
                                countryCode: controller.countryCode,
                                currencySymbol: controller.currencySymbol,
                                isVisible: controller.isBalanceVisible.value,
                                onToggleVisibility:
                                    controller.toggleBalanceVisibility,
                                onSelectCountry:
                                    controller.selectCountryCurrency,
                              ),
                            ),

                            const SizedBox(height: 20),

                            // Quick Action Buttons: Send, Receive, Convert
                            HomeQuickActions(
                              onActionTap: controller.onQuickAction,
                            ),

                            const SizedBox(height: 18),

                            // Account Number Row
                            Obx(
                              () => HomeAccountNumberCard(
                                currency: controller.selectedCurrency.value,
                                maskedAccountNumber: controller.accountNumber,
                                onCopy: controller.copyAccountNumber,
                              ),
                            ),

                            const ProfileActionPrompts(),

                            const SizedBox(height: 26),

                            // Tax-free Sending Promotional Layered Banner
                            HomePromoBanner(
                              onTap: () =>
                                  controller.onQuickAction('Promo Banner'),
                            ),

                            const SizedBox(height: 28),

                            // Recent Transactions Empty State
                            HomeTransactionsSection(
                              onSeeMoreTap: () => controller.onQuickAction(
                                'Recent Transactions',
                              ),
                            ),

                            const SizedBox(height: 24),
                          ],
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
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
