import 'package:flutter/material.dart';

class UserAvatarWidget extends StatelessWidget {
  final double size;

  const UserAvatarWidget({
    super.key,
    this.size = 44.0,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: Color(0xFF6B3A21),
        shape: BoxShape.circle,
      ),
      child: ClipOval(
        child: CustomPaint(
          size: Size(size, size),
          painter: _AvatarPainter(),
        ),
      ),
    );
  }
}

class _AvatarPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Background circle tone
    final bgPaint = Paint()..color = const Color(0xFF5D2E1A);
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h), bgPaint);

    // Shoulders / Hoodie
    final bodyPaint = Paint()..color = const Color(0xFFD97706);
    final bodyPath = Path()
      ..moveTo(w * 0.15, h)
      ..cubicTo(w * 0.2, h * 0.72, w * 0.8, h * 0.72, w * 0.85, h)
      ..close();
    canvas.drawPath(bodyPath, bodyPaint);

    // Neck
    final skinPaint = Paint()..color = const Color(0xFF7C3E1D);
    canvas.drawRect(
      Rect.fromCenter(
        center: Offset(w * 0.5, h * 0.65),
        width: w * 0.22,
        height: h * 0.2,
      ),
      skinPaint,
    );

    // Head / Face
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(w * 0.5, h * 0.50),
        width: w * 0.42,
        height: h * 0.46,
      ),
      skinPaint,
    );

    // Afro Hair (Black bumpy curls around head)
    final hairPaint = Paint()..color = const Color(0xFF1E140F);
    final hairPositions = [
      Offset(w * 0.50, h * 0.24),
      Offset(w * 0.38, h * 0.26),
      Offset(w * 0.62, h * 0.26),
      Offset(w * 0.28, h * 0.34),
      Offset(w * 0.72, h * 0.34),
      Offset(w * 0.24, h * 0.44),
      Offset(w * 0.76, h * 0.44),
      Offset(w * 0.26, h * 0.54),
      Offset(w * 0.74, h * 0.54),
    ];
    for (final pos in hairPositions) {
      canvas.drawCircle(pos, w * 0.14, hairPaint);
    }

    // Eyes
    final eyePaint = Paint()..color = const Color(0xFF261208);
    canvas.drawCircle(Offset(w * 0.43, h * 0.50), w * 0.035, eyePaint);
    canvas.drawCircle(Offset(w * 0.57, h * 0.50), w * 0.035, eyePaint);

    // Smile
    final smilePaint = Paint()
      ..color = const Color(0xFF421E0D)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 1.6;
    final smilePath = Path()
      ..moveTo(w * 0.44, h * 0.59)
      ..quadraticBezierTo(w * 0.50, h * 0.64, w * 0.56, h * 0.59);
    canvas.drawPath(smilePath, smilePaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
