import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/core/widgets/sheet_drag_handle.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/home/models/home_country_currency.dart';
import 'package:novabanq/features/send/bindings/send_amount_binding.dart';
import 'package:novabanq/features/send/views/send_amount_screen.dart';
import 'corridor_country_selector.dart';
import 'corridor_dashed_divider.dart';

class SelectCorridorBottomSheet extends StatelessWidget {
  const SelectCorridorBottomSheet({super.key});

  static Future<T?> show<T>(BuildContext context) {
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.5),
      builder: (ctx) => const SelectCorridorBottomSheet(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final fromCountry = kHomeSupportedCurrencies[0].obs; // Nigeria
    final toCountry = kHomeSupportedCurrencies[1].obs; // Ghana

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(32),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // 1. Drag Handle
              const SheetDragHandle(),

              const SizedBox(height: 24),

              // 2. Title
              Text(
                'Select corridor',
                style: GoogleFonts.outfit(
                  fontSize: 21,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                  letterSpacing: -0.4,
                ),
              ),

              const SizedBox(height: 6),

              // 3. Subtitle
              Text(
                'Select where the funds is coming from and\ngoing to',
                style: GoogleFonts.outfit(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w400,
                  color: const Color(0xFF667085),
                  height: 1.45,
                ),
                textAlign: TextAlign.center,
              ),

              const SizedBox(height: 28),

              // 4. From Country Selector
              Align(
                alignment: Alignment.centerLeft,
                child: Obx(
                  () => CorridorCountrySelector(
                    label: 'From',
                    selected: fromCountry.value,
                    countries: kHomeSupportedCurrencies,
                    onSelect: (c) => fromCountry.value = c,
                  ),
                ),
              ),

              const SizedBox(height: 12),

              // 5. Dashed Divider
              const CorridorDashedDivider(),

              const SizedBox(height: 12),

              // 6. To Country Selector
              Align(
                alignment: Alignment.centerLeft,
                child: Obx(
                  () => CorridorCountrySelector(
                    label: 'To',
                    selected: toCountry.value,
                    countries: kHomeSupportedCurrencies,
                    onSelect: (c) => toCountry.value = c,
                  ),
                ),
              ),

              const SizedBox(height: 32),

              // 7. Confirm Button
              AuthCtaButton(
                text: 'Confirm',
                onPressed: () {
                  Navigator.of(context).pop();
                  Get.to(
                    () => const SendAmountScreen(),
                    binding: SendAmountBinding(),
                  );
                },
              ),

              const SizedBox(height: 14),
            ],
          ),
        ),
      ),
    );
  }
}
