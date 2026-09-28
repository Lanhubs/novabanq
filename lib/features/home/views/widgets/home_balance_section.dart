import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:hugeicons/hugeicons.dart';
import '../../models/home_country_currency.dart';
import 'home_currency_pill.dart';

class HomeBalanceSection extends StatelessWidget {
  final String balance;
  final bool isVisible;
  final bool isLoading;
  final String currencyCode;
  final String countryCode;
  final String currencySymbol;
  final VoidCallback onToggleVisibility;
  final ValueChanged<HomeCountryCurrency>? onSelectCountry;

  const HomeBalanceSection({
    super.key,
    required this.balance,
    required this.isVisible,
    this.isLoading = false,
    required this.currencyCode,
    required this.countryCode,
    required this.currencySymbol,
    required this.onToggleVisibility,
    this.onSelectCountry,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        // 1. Currency Selector Pill with Dropdown
        HomeCurrencyPill(
          currencyCode: currencyCode,
          countryCode: countryCode,
          onSelectCountry: onSelectCountry,
        ),

        const SizedBox(height: 10),

        // 2. Balance Amount + Eye Icon Row
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // Currency Symbol
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Text(
                currencySymbol,
                style: GoogleFonts.outfit(
                  fontSize: currencySymbol.length > 2 ? 21 : 32,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF101828),
                ),
              ),
            ),

            // Amount or Masked dots
            if (isLoading)
              const _BalanceSkeleton()
            else
              Text(
                isVisible ? balance : '••••••',
                style: GoogleFonts.outfit(
                  fontSize: 42,
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF101828),
                  letterSpacing: -1.2,
                ),
              ),

            const SizedBox(width: 10),

            // Eye Toggle Icon Button
            GestureDetector(
              onTap: onToggleVisibility,
              behavior: HitTestBehavior.opaque,
              child: Padding(
                padding: const EdgeInsets.all(4.0),
                child: HugeIcon(
                  icon: isVisible
                      ? HugeIcons.strokeRoundedView
                      : HugeIcons.strokeRoundedViewOffSlash,
                  color: const Color(0xFF667085),
                  size: 25,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _BalanceSkeleton extends StatefulWidget {
  const _BalanceSkeleton();

  @override
  State<_BalanceSkeleton> createState() => _BalanceSkeletonState();
}

class _BalanceSkeletonState extends State<_BalanceSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 850),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Loading account balance',
      liveRegion: true,
      child: SizedBox(
        width: 164,
        height: 42,
        child: FadeTransition(
          opacity: _pulse.drive(Tween(begin: 0.4, end: 0.95)),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: const Color(0xFFE4E7EC),
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
      ),
    );
  }
}
