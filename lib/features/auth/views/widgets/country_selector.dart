import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/models/country_item.dart';

class CountrySelector extends StatelessWidget {
  final CountryItem selectedCountry;
  final List<CountryItem> countries;
  final bool isOpen;
  final VoidCallback onToggle;
  final ValueChanged<CountryItem> onSelect;

  const CountrySelector({
    super.key,
    required this.selectedCountry,
    required this.countries,
    required this.isOpen,
    required this.onToggle,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // 1. Selector Header
        InkWell(
          onTap: onToggle,
          borderRadius: isOpen
              ? const BorderRadius.only(
                  topLeft: Radius.circular(10),
                  topRight: Radius.circular(10),
                )
              : BorderRadius.circular(10),
          child: Container(
            height: 56,
            decoration: BoxDecoration(
              color: const Color(0xD9E7E9EC), // Exact #E7E9ECD9 background
              borderRadius: isOpen
                  ? const BorderRadius.only(
                      topLeft: Radius.circular(10),
                      topRight: Radius.circular(10),
                    )
                  : BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                // Flag and Chevron section
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      selectedCountry.flagWidget,
                      const SizedBox(width: 8),
                      Icon(
                        isOpen
                            ? Icons.keyboard_arrow_up_rounded
                            : Icons.keyboard_arrow_down_rounded,
                        size: 20,
                        color: const Color(0xFF667085),
                      ),
                    ],
                  ),
                ),

                // Vertical Divider Line matching design
                Container(
                  width: 1,
                  height: 32,
                  color: const Color(0xFFD0D5DD),
                ),

                const SizedBox(width: 14),

                // Country Name
                Expanded(
                  child: Text(
                    selectedCountry.name,
                    style: GoogleFonts.outfit(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: const Color(0xFF101828),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),

        // 2. Dropdown List when Open
        if (isOpen)
          Container(
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.only(
                bottomLeft: Radius.circular(10),
                bottomRight: Radius.circular(10),
              ),
              border: Border(
                left: BorderSide(color: Color(0xFFE4E7EC), width: 1.2),
                right: BorderSide(color: Color(0xFFE4E7EC), width: 1.2),
                bottom: BorderSide(color: Color(0xFFE4E7EC), width: 1.2),
              ),
            ),
            child: Column(
              children: countries
                  .where((c) => c.code != selectedCountry.code || isOpen)
                  .map((country) {
                // If this is the active/selected country, show checkmark
                final isChecked = country.name == selectedCountry.name ||
                    (selectedCountry.name == 'Nigeria' &&
                        country.name == 'Cameroon');

                return InkWell(
                  onTap: () => onSelect(country),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 14,
                    ),
                    child: Row(
                      children: [
                        country.flagWidget,
                        const SizedBox(width: 14),
                        Expanded(
                          child: Text(
                            country.displayText,
                            style: GoogleFonts.outfit(
                              fontSize: 15,
                              fontWeight: FontWeight.w500,
                              color: const Color(0xFF101828),
                            ),
                          ),
                        ),
                        if (isChecked)
                          const Icon(
                            Icons.check_rounded,
                            size: 20,
                            color: Color(0xFF005100),
                          ),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
      ],
    );
  }
}
