import "package:flutter/material.dart";
class LoadingState extends StatelessWidget {
 

  const LoadingState({
    super.key,
  });

  @override
   Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: 60.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: Color(0xFF1570EF), strokeWidth: 3),
            SizedBox(height: 16),
            Text(
              'Loading transactions...',
              style: TextStyle(
                fontSize: 14,
                color: Color(0xFF667085),
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

}