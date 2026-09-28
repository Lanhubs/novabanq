import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/home/controllers/home_controller.dart';
import 'package:novabanq/features/home/views/widgets/empty_state.dart';
import 'package:novabanq/features/home/views/widgets/error_state.dart';
import 'package:novabanq/features/home/views/widgets/loading_state.dart';
import 'package:novabanq/features/home/views/widgets/transactions_list.dart';

class HomeTransactionsSection extends StatelessWidget {
  final VoidCallback? onSeeMoreTap;

  const HomeTransactionsSection({super.key, this.onSeeMoreTap});

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<HomeController>();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 1. Header: "Recent transactions" & "See more"
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Recent transactions',
              style: GoogleFonts.outfit(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF101828),
              ),
            ),
            Obx(
              () => controller.transactions.isNotEmpty
                  ? GestureDetector(
                      onTap: onSeeMoreTap,
                      child: Text(
                        'See more',
                        style: GoogleFonts.outfit(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w500,
                          color: const Color(0xFF667085),
                        ),
                      ),
                    )
                  : const SizedBox.shrink(),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // 2. Dynamic Content based on state
        Obx(() {
          // Loading state
          if (controller.isTransactionsLoading.value &&
              controller.transactions.isEmpty) {
            return const LoadingState();
          }

          // Error state (only if no transactions loaded)
          if (controller.transactionsError.value.isNotEmpty &&
              controller.transactions.isEmpty) {
            return const ErrorState();
          }

          // Empty state (no transactions available)
          if (controller.transactions.isEmpty) {
            return const EmptyState();
          }

          // Transactions loaded - show list
          return TransactionsList(controller: controller);
        }),
      ],
    );
  }

 

 
  
  }
