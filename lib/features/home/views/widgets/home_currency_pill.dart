import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/models/country_item.dart';
import '../../models/home_country_currency.dart';

class HomeCurrencyPill extends StatelessWidget {
  final String currencyCode;
  final String countryCode;
  final ValueChanged<HomeCountryCurrency>? onSelectCountry;

  const HomeCurrencyPill({
    super.key,
    required this.currencyCode,
    required this.countryCode,
    this.onSelectCountry,
  });

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<HomeCountryCurrency>(
      tooltip: 'Select country currency',
      offset: const Offset(0, 36),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 6,
      color: Colors.white,
      onSelected: onSelectCountry,
      itemBuilder: (context) {
        return kHomeSupportedCurrencies.map((item) {
          final isSelected = item.countryCode == countryCode;
          return PopupMenuItem<HomeCountryCurrency>(
            value: item,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                CountryFlagBadge(code: item.countryCode, width: 22, height: 15),
                const SizedBox(width: 12),
                Text(
                  item.currencyCode,
                  style: GoogleFonts.outfit(
                    fontSize: 14.5,
                    fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                    color: isSelected
                        ? const Color(0xFF005100)
                        : const Color(0xFF101828),
                  ),
                ),
                const SizedBox(width: 16),
                if (isSelected)
                  const Icon(
                    Icons.check_circle_rounded,
                    size: 16,
                    color: Color(0xFF005100),
                  )
                else
                  const SizedBox(width: 16),
              ],
            ),
          );
        }).toList();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFF9DE7B0),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Country Flag Badge
            CountryFlagBadge(code: countryCode, width: 18, height: 13),

            const SizedBox(width: 7),

            // Currency code
            Text(
              currencyCode,
              style: GoogleFonts.outfit(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF0A4F1D),
              ),
            ),

            const SizedBox(width: 4),

            // Down chevron arrow
            const Icon(
              Icons.keyboard_arrow_down_rounded,
              size: 18,
              color: Color(0xFF0A4F1D),
            ),
          ],
        ),
      ),
    );
  }
}
