import 'package:flutter/material.dart';

class AiTriggerButton extends StatelessWidget {
  final VoidCallback onPressed;

  const AiTriggerButton({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    const double circleSize = 65.0;

    return InkWell(
      onTap: onPressed,
      child: SizedBox(
        width: circleSize,
        height: circleSize,
        child: Stack(
          alignment: Alignment.bottomCenter,
          clipBehavior:
              Clip.none, // Allows the character image to break out of bounds
          children: [
            // 1. Green Circular Background with Shadow
            Container(
              width: circleSize,
              height: circleSize,
              decoration: BoxDecoration(
                color: const Color(0xFF50C878), // Match green background
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.40),
                    offset: const Offset(3, 3),
                    blurRadius: 7.0,
                    spreadRadius: 2.0,
                  ),
                ],
              ),
              child: CustomPaint(
                painter: FigmaInnerShadowPainter(
                  color: Colors.black.withValues(alpha: 0.25),
                  offset: Offset.zero,
                  blur: 1.9,
                  spread: 1.0,
                ),
              ),
            ),

            // 2. Character PNG Image breaking out from the top
            Positioned(
              bottom:
                  8.0, // Adjust bottom offset so feet touch the base properly
              top:
                  -45.0, // Negative top padding pushes the head/torso outside the top
              child: Image.asset(
                'assets/icons/ai_icon.png',
                fit: BoxFit.contain,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class FigmaInnerShadowPainter extends CustomPainter {
  final Color color;
  final Offset offset;
  final double blur;
  final double spread;

  FigmaInnerShadowPainter({
    required this.color,
    required this.offset,
    required this.blur,
    this.spread = 0.0,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final Rect rect = Offset.zero & size;
    final Path circlePath = Path()..addOval(rect);

    canvas.save();
    canvas.clipPath(circlePath);

    final Paint paint = Paint()
      ..color = color
      ..maskFilter = blur > 0 ? MaskFilter.blur(BlurStyle.normal, blur) : null;

    final Rect shadowRect = rect.deflate(spread);
    final Path cutOutPath = Path()
      ..addRect(rect.inflate(blur * 2 + offset.distance + spread))
      ..addOval(shadowRect);
    cutOutPath.fillType = PathFillType.evenOdd;

    canvas.translate(offset.dx, offset.dy);
    canvas.drawPath(cutOutPath, paint);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant FigmaInnerShadowPainter oldDelegate) =>
      oldDelegate.color != color ||
      oldDelegate.offset != offset ||
      oldDelegate.blur != blur ||
      oldDelegate.spread != spread;
}
