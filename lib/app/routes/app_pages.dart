import 'package:get/get.dart';
import 'package:novabanq/app/routes/app_routes.dart';
import 'package:novabanq/features/auth/bindings/auth_binding.dart';
import 'package:novabanq/features/auth/bindings/login_binding.dart';
import 'package:novabanq/features/auth/views/account_success_screen.dart';
import 'package:novabanq/features/auth/views/auth_screen.dart';
import 'package:novabanq/features/auth/views/login_screen.dart';
import 'package:novabanq/features/auth/views/face_scan_screen.dart';
import 'package:novabanq/features/home/bindings/home_binding.dart';
import 'package:novabanq/features/home/views/home_screen.dart';
import 'package:novabanq/features/onboarding/bindings/onboarding_binding.dart';
import 'package:novabanq/features/onboarding/bindings/splash_screen_binding.dart';
import 'package:novabanq/features/onboarding/views/onboarding_screen.dart';
import 'package:novabanq/features/onboarding/views/splash_screen.dart';
import 'package:novabanq/features/card/bindings/card_binding.dart';
import 'package:novabanq/features/card/views/card_controls_screen.dart';
import 'package:novabanq/features/card/views/card_details_screen.dart';
import 'package:novabanq/features/card/views/card_screen.dart';
import 'package:novabanq/features/card/views/select_card_screen.dart';
import 'package:novabanq/features/card/views/add_card_screen.dart';
import 'package:novabanq/features/profile/bindings/profile_binding.dart';
import 'package:novabanq/features/profile/views/personal_information_screen.dart';
import 'package:novabanq/features/profile/views/profile_screen.dart';
import 'package:novabanq/features/profile/views/security_privacy_screen.dart';
import 'package:novabanq/features/profile/views/transaction_pin_screen.dart';
import 'package:novabanq/features/receive/bindings/receive_money_binding.dart';
import 'package:novabanq/features/receive/views/receive_money_screen.dart';
import 'package:novabanq/features/send/bindings/send_amount_binding.dart';
import 'package:novabanq/features/send/bindings/send_money_binding.dart';
import 'package:novabanq/features/send/bindings/transfer_success_binding.dart';
import 'package:novabanq/features/send/views/send_amount_screen.dart';
import 'package:novabanq/features/send/views/send_money_screen.dart';
import 'package:novabanq/features/send/views/transfer_success_screen.dart';

class AppPages {
  static List<GetPage> appPages = [
    GetPage(
      name: AppRoutes.splash,
      page: () => const SplashScreen(),
      binding: SplashBinding(),
    ),
    GetPage(
      name: AppRoutes.onboarding,
      page: () => const OnboardingScreen(),
      binding: OnboardingBinding(),
    ),
    GetPage(
      name: AppRoutes.auth,
      page: () => const AuthScreen(),
      binding: AuthBinding(),
    ),
    GetPage(
      name: AppRoutes.login,
      page: () => const LoginScreen(),
      binding: LoginBinding(),
    ),
    GetPage(name: AppRoutes.faceScan, page: () => const FaceScanScreen()),
    GetPage(
      name: AppRoutes.accountSuccess,
      page: () => const AccountSuccessScreen(),
    ),
    GetPage(
      name: AppRoutes.home,
      page: () => const HomeScreen(),
      binding: HomeBinding(),
    ),
    GetPage(
      name: AppRoutes.sendMoney,
      page: () => const SendMoneyScreen(),
      binding: SendMoneyBinding(),
    ),
    GetPage(
      name: AppRoutes.sendAmount,
      page: () => const SendAmountScreen(),
      binding: SendAmountBinding(),
    ),
    GetPage(
      name: AppRoutes.transferSuccess,
      page: () => const TransferSuccessScreen(),
      binding: TransferSuccessBinding(),
    ),
    GetPage(
      name: AppRoutes.receiveMoney,
      page: () => const ReceiveMoneyScreen(),
      binding: ReceiveMoneyBinding(),
    ),
    GetPage(
      name: AppRoutes.card,
      page: () => const CardScreen(),
      binding: CardBinding(),
    ),
    GetPage(
      name: AppRoutes.cardDetails,
      page: () => const CardDetailsScreen(),
      binding: CardBinding(),
    ),
    GetPage(
      name: AppRoutes.cardControls,
      page: () => const CardControlsScreen(),
      binding: CardBinding(),
    ),
    GetPage(
      name: AppRoutes.selectCard,
      page: () => const SelectCardScreen(),
      binding: CardBinding(),
    ),
    GetPage(
      name: AppRoutes.addCard,
      page: () => const AddCardScreen(),
      binding: CardBinding(),
    ),
    GetPage(
      name: AppRoutes.profile,
      page: () => const ProfileScreen(),
      binding: ProfileBinding(),
    ),
    GetPage(
      name: AppRoutes.personalInformation,
      page: () => const PersonalInformationScreen(),
      binding: ProfileBinding(),
    ),
    GetPage(
      name: AppRoutes.securityPrivacy,
      page: () => const SecurityPrivacyScreen(),
      binding: ProfileBinding(),
    ),
    GetPage(
      name: AppRoutes.transactionPin,
      page: () => const TransactionPinScreen(),
    ),
  ];
}
