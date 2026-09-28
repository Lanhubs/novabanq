import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:novabanq/features/home/views/widgets/ai_agent_sheet.dart';
import 'package:novabanq/features/home/views/widgets/ai_trigger_button.dart';
import '../../controllers/home_controller.dart';
import 'home_account_number_card.dart';
import 'home_balance_section.dart';
import 'home_promo_banner.dart';
import 'home_quick_actions.dart';
import 'home_top_bar.dart';
import 'home_transactions_section.dart';

class HomeTabView extends GetView<HomeController> {
  const HomeTabView({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
                      child: RefreshIndicator(
                        onRefresh: () async {
                          // Refresh both balance and transactions
                          await Future.wait([
                            controller.loadAccount(),
                            controller.refreshTransactions(),
                          ]);
                        },
                        color: const Color(0xFF1570EF),
                        child: SingleChildScrollView(
                          physics: const AlwaysScrollableScrollPhysics(
                            parent: BouncingScrollPhysics(),
                          ),
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
                                  balance: controller.balanceAmount.value,
                                  currencyCode:
                                      controller.selectedCurrency.value,
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

                              const SizedBox(height: 26),

                              // Promotional Banner
                              HomePromoBanner(
                                onTap: () =>
                                    controller.onQuickAction('Promo Banner'),
                              ),

                              const SizedBox(height: 28),

                              // Recent Transactions Section
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
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
      floatingActionButton: AiTriggerButton(
        onPressed: () => Get.bottomSheet(
          const AiAgentSheet(),
          isScrollControlled: true,
          backgroundColor: Colors.transparent,
        ),
      ),
    );
  }
}
