import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:google_fonts/google_fonts.dart';
import 'widgets/face_scan_shutter_button.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/identity_service.dart';
import 'package:novabanq/features/auth/controllers/auth_controller.dart';

class FaceScanScreen extends StatefulWidget {
  const FaceScanScreen({super.key});

  @override
  State<FaceScanScreen> createState() => _FaceScanScreenState();
}

class _FaceScanScreenState extends State<FaceScanScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;
  late final Animation<double> _pulseAnimation;
  bool _isCapturing = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.96, end: 1.04).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _handleCapture() async {
    if (_isCapturing) return;

    setState(() {
      _isCapturing = true;
      _error = '';
    });

    HapticFeedback.mediumImpact();

    try {
      final auth = Get.find<AuthController>();
      final result = await IdentityService(
        auth.api,
      ).verifyWithCamera(auth.bvnController.text.trim());
      if (!mounted) return;
      if (result['status'] == 'VERIFIED') {
        Get.back(result: true);
      } else {
        setState(
          () => _error = 'Identity check: ${result['status'] ?? 'REJECTED'}',
        );
      }
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => _error = failure.message);
    } finally {
      if (mounted) setState(() => _isCapturing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        systemNavigationBarColor: Colors.black,
        systemNavigationBarIconBrightness: Brightness.light,
      ),
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(
          fit: StackFit.expand,
          children: [
            // 1. Exact Face Verification Camera Viewfinder matching design
            Image.asset(
              'assets/images/face_scan_sample_clean.png',
              fit: BoxFit.cover,
              alignment: Alignment.center,
            ),

            // 2. Subtle scanning glow pulse effect
            AnimatedBuilder(
              animation: _pulseAnimation,
              builder: (context, child) {
                return Center(
                  child: Transform.scale(
                    scale: _pulseAnimation.value,
                    child: Container(
                      width: 200,
                      height: 200,
                      decoration: BoxDecoration(shape: BoxShape.circle),
                    ),
                  ),
                );
              },
            ),

            // 3. Close / Back button at top left
            SafeArea(
              child: Align(
                alignment: Alignment.topLeft,
                child: Padding(
                  padding: const EdgeInsets.only(left: 16.0, top: 12.0),
                  child: InkWell(
                    onTap: () => Get.back(result: false),
                    borderRadius: BorderRadius.circular(20),
                    child: Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.4),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: Colors.white.withValues(alpha: 0.2),
                          width: 1,
                        ),
                      ),
                      child: const Icon(
                        Icons.arrow_back,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                  ),
                ),
              ),
            ),

            // 4. Processing overlay when shutter is tapped
            if (_isCapturing)
              Container(
                color: Colors.black.withValues(alpha: 0.45),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircularProgressIndicator(
                        valueColor: AlwaysStoppedAnimation<Color>(
                          Color(0xFF22C55E),
                        ),
                        strokeWidth: 3,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Verifying face...',
                        style: GoogleFonts.outfit(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            if (_error.isNotEmpty)
              Align(
                alignment: Alignment.bottomCenter,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 96),
                  child: Text(
                    _error,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      backgroundColor: Colors.red,
                    ),
                  ),
                ),
              ),

            // 5. Shutter / Capture Button at bottom center matching design
            Align(
              alignment: Alignment.bottomCenter,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 20),
                child: FaceScanShutterButton(onTap: _handleCapture),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
