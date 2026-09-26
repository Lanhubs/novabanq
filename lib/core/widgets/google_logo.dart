import 'package:flutter/material.dart';

/// Crisp multi-colored Google 'G' logo
class GoogleLogo extends StatelessWidget {
  final double size;

  const GoogleLogo({super.key, this.size = 20});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size(size, size),
      painter: _GoogleLogoPainter(),
    );
  }
}

class _GoogleLogoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final center = Offset(w / 2, h / 2);
    final radius = w / 2;

    final rect = Rect.fromCircle(center: center, radius: radius);
    final strokeWidth = w * 0.22;
    final strokeRect = rect.deflate(strokeWidth / 2);

    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.butt;

    // Blue arc (Right & top-right)
    paint.color = const Color(0xFF4285F4);
    canvas.drawArc(strokeRect, -0.6, 1.6, false, paint);

    // Green arc (Bottom)
    paint.color = const Color(0xFF34A853);
    canvas.drawArc(strokeRect, 1.0, 1.5, false, paint);

    // Yellow arc (Bottom-left)
    paint.color = const Color(0xFFFBBC05);
    canvas.drawArc(strokeRect, 2.5, 1.2, false, paint);

    // Red arc (Top)
    paint.color = const Color(0xFFEA4335);
    canvas.drawArc(strokeRect, 3.7, 1.8, false, paint);

    // Blue horizontal bar
    final barPaint = Paint()
      ..color = const Color(0xFF4285F4)
      ..style = PaintingStyle.fill;

    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTRB(w * 0.45, h * 0.40, w * 0.98, h * 0.60),
        const Radius.circular(2),
      ),
      barPaint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
