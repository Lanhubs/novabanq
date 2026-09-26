import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/models/country_item.dart';
import 'package:novabanq/features/home/models/home_country_currency.dart';

class CorridorCountrySelector extends StatelessWidget {
  final String label;
  final HomeCountryCurrency selected;
  final List<HomeCountryCurrency> countries;
  final ValueChanged<HomeCountryCurrency> onSelect;

  const CorridorCountrySelector({
    super.key,
    required this.label,
    required this.selected,
    required this.countries,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // Label: "From" or "To"
        Text(
          label,
          style: GoogleFonts.outfit(
            fontSize: 13,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
          ),
        ),

        const SizedBox(height: 8),

        // Country row with flag + name + dropdown
        PopupMenuButton<HomeCountryCurrency>(
          tooltip: 'Select country',
          offset: const Offset(0, 36),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          elevation: 6,
          color: Colors.white,
          onSelected: onSelect,
          itemBuilder: (context) {
            return countries.map((item) {
              return PopupMenuItem<HomeCountryCurrency>(
                value: item,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CountryFlagBadge(
                      code: item.countryCode,
                      width: 22,
                      height: 15,
                    ),
                    const SizedBox(width: 10),
                    Text(
                      item.name,
                      style: GoogleFonts.outfit(
                        fontSize: 14,
                        fontWeight: item.countryCode == selected.countryCode
                            ? FontWeight.w700
                            : FontWeight.w500,
                        color: const Color(0xFF101828),
                      ),
                    ),
                  ],
                ),
              );
            }).toList();
          },
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              CountryFlagBadge(
                code: selected.countryCode,
                width: 24,
                height: 16,
              ),
              const SizedBox(width: 10),
              Text(
                selected.name,
                style: GoogleFonts.outfit(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: const Color(0xFF101828),
                ),
              ),
              const SizedBox(width: 6),
              const Icon(
                Icons.keyboard_arrow_down_rounded,
                size: 20,
                color: Color(0xFF667085),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
