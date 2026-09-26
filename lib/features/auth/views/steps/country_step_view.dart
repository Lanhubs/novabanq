import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:novabanq/features/auth/models/country_item.dart';
import 'package:novabanq/features/auth/views/widgets/auth_cta_button.dart';
import 'package:novabanq/features/auth/views/widgets/country_selector.dart';

class CountryStepView extends StatelessWidget {
  final CountryItem selectedCountry;
  final List<CountryItem> countries;
  final bool isDropdownOpen;
  final VoidCallback onToggleDropdown;
  final ValueChanged<CountryItem> onSelectCountry;
  final VoidCallback onContinue;

  const CountryStepView({
    super.key,
    required this.selectedCountry,
    required this.countries,
    required this.isDropdownOpen,
    required this.onToggleDropdown,
    required this.onSelectCountry,
    required this.onContinue,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title matching design
        Text(
          "What country\ndo you live in?",
          style: GoogleFonts.outfit(
            fontSize: 32,
            fontWeight: FontWeight.w800,
            color: const Color(0xFF111111),
            height: 1.15,
            letterSpacing: -0.6,
          ),
        ),

        const SizedBox(height: 10),

        // Subtitle matching design
        Text(
          "What is your primary country of residence",
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: const Color(0xFF667085),
          ),
        ),

        const SizedBox(height: 20),

        // Country Selector Component
        CountrySelector(
          selectedCountry: selectedCountry,
          countries: countries,
          isOpen: isDropdownOpen,
          onToggle: onToggleDropdown,
          onSelect: onSelectCountry,
        ),

        const SizedBox(height: 24),

        // Continue Button
        AuthCtaButton(
          onPressed: onContinue,
          text: "Continue",
        ),
      ],
    );
  }
}
