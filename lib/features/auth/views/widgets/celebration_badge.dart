import 'dart:math' as math;
import 'package:flutter/material.dart';

class CelebrationBadge extends StatelessWidget {
  final double size;

  const CelebrationBadge({
    super.key,
    this.size = 112.0,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: Color(0xFF9DE7B0), // Soft mint / pistachio green
        shape: BoxShape.circle,
      ),
      child: Center(
        child: CustomPaint(
          size: Size(size * 0.75, size * 0.75),
          painter: _PartyPopperPainter(),
        ),
      ),
    );
  }
}

class _PartyPopperPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Party Popper Cone coordinates
    // Cone apex pointing down-left, opening towards up-right
    final apex = Offset(w * 0.18, h * 0.78);
    final topCorner = Offset(w * 0.35, h * 0.28);
    final rightCorner = Offset(w * 0.72, h * 0.65);

    // 1. Draw Cone Body
    final conePath = Path()
      ..moveTo(apex.dx, apex.dy)
      ..lineTo(topCorner.dx, topCorner.dy)
      ..lineTo(rightCorner.dx, rightCorner.dy)
      ..close();

    final conePaint = Paint()
      ..color = const Color(0xFFFFD54F) // Vibrant bright yellow
      ..style = PaintingStyle.fill;
    canvas.drawPath(conePath, conePaint);

    // 2. Draw Cone Opening Rim (Orange oval)
    final rimCenter = Offset((topCorner.dx + rightCorner.dx) / 2,
        (topCorner.dy + rightCorner.dy) / 2);
    final rimPaint = Paint()
      ..color = const Color(0xFFFF7043) // Coral orange
      ..style = PaintingStyle.fill;

    canvas.save();
    canvas.translate(rimCenter.dx, rimCenter.dy);
    canvas.rotate(math.pi / 4);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset.zero,
        width: w * 0.46,
        height: h * 0.16,
      ),
      rimPaint,
    );
    canvas.restore();

    // 3. Draw Confetti Streamers (Ribbons)
    final strokePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 3.5;

    // Dark Blue Streamer (curling upwards)
    strokePaint.color = const Color(0xFF0D47A1);
    final bluePath = Path()
      ..moveTo(w * 0.52, h * 0.40)
      ..cubicTo(
        w * 0.58, h * 0.26,
        w * 0.68, h * 0.32,
        w * 0.74, h * 0.16,
      );
    canvas.drawPath(bluePath, strokePaint);

    // Cyan / Light Blue Streamer
    strokePaint.color = const Color(0xFF00ACC1);
    final cyanPath = Path()
      ..moveTo(w * 0.38, h * 0.38)
      ..cubicTo(
        w * 0.38, h * 0.22,
        w * 0.48, h * 0.24,
        w * 0.44, h * 0.14,
      );
    canvas.drawPath(cyanPath, strokePaint);

    // Pink / Magenta Streamer (curling to the right)
    strokePaint.color = const Color(0xFFEC407A);
    final pinkPath = Path()
      ..moveTo(w * 0.62, h * 0.48)
      ..cubicTo(
        w * 0.72, h * 0.42,
        w * 0.70, h * 0.58,
        w * 0.80, h * 0.50,
      );
    canvas.drawPath(pinkPath, strokePaint);

    // 4. Draw Confetti Dots & Stars
    final dotPaint = Paint()..style = PaintingStyle.fill;

    // Blue dot
    dotPaint.color = const Color(0xFF1976D2);
    canvas.drawCircle(Offset(w * 0.42, h * 0.18), 3.0, dotPaint);

    // Pink dot
    dotPaint.color = const Color(0xFFE91E63);
    canvas.drawCircle(Offset(w * 0.70, h * 0.36), 3.2, dotPaint);

    // Orange dot
    dotPaint.color = const Color(0xFFFF5722);
    canvas.drawCircle(Offset(w * 0.56, h * 0.26), 2.8, dotPaint);

    // Yellow dot
    dotPaint.color = const Color(0xFFFFB300);
    canvas.drawCircle(Offset(w * 0.78, h * 0.22), 3.0, dotPaint);

    // Purple dot
    dotPaint.color = const Color(0xFF8E24AA);
    canvas.drawCircle(Offset(w * 0.48, h * 0.46), 2.5, dotPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
