import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// A utility class that provides easy access to different snack bar variants
/// with consistent styling and behavior across the app.
class SnackBarHelper {
  // Private constructor to prevent instantiation
  SnackBarHelper._();

  /// Default duration for snack bars
  static const Duration _defaultDuration = Duration(seconds: 3);
  
  /// Default margin for snack bars
  static const EdgeInsets _defaultMargin = EdgeInsets.all(16.0);
  
  /// Default border radius for snack bars
  static const double _defaultBorderRadius = 12.0;

  /// Shows a success snack bar with green theme
  static void showSuccess({
    required String message,
    String? title,
    Duration duration = _defaultDuration,
    SnackPosition position = SnackPosition.TOP,
    VoidCallback? onTap,
    bool isDismissible = true,
  }) {
    Get.snackbar(
      title ?? 'Success',
      message,
      backgroundColor: Colors.green.shade600,
      colorText: Colors.white,
      icon: const Icon(
        Icons.check_circle_outline,
        color: Colors.white,
        size: 24,
      ),
      snackPosition: position,
      duration: duration,
      margin: _defaultMargin,
      borderRadius: _defaultBorderRadius,
      onTap: onTap != null ? (_) => onTap() : null,
      isDismissible: isDismissible,
      forwardAnimationCurve: Curves.easeOutBack,
      reverseAnimationCurve: Curves.easeInBack,
    );
  }

  /// Shows an error snack bar with red theme
  static void showError({
    required String message,
    String? title,
    Duration duration = _defaultDuration,
    SnackPosition position = SnackPosition.TOP,
    VoidCallback? onTap,
    bool isDismissible = true,
  }) {
    Get.snackbar(
      title ?? 'Error',
      message,
      backgroundColor: Colors.red.shade600,
      colorText: Colors.white,
      icon: const Icon(
        Icons.error_outline,
        color: Colors.white,
        size: 24,
      ),
      snackPosition: position,
      duration: duration,
      margin: _defaultMargin,
      borderRadius: _defaultBorderRadius,
      onTap: onTap != null ? (_) => onTap() : null,
      isDismissible: isDismissible,
      forwardAnimationCurve: Curves.easeOutBack,
      reverseAnimationCurve: Curves.easeInBack,
    );
  }

  /// Shows a warning snack bar with orange theme
  static void showWarning({
    required String message,
    String? title,
    Duration duration = _defaultDuration,
    SnackPosition position = SnackPosition.TOP,
    VoidCallback? onTap,
    bool isDismissible = true,
  }) {
    Get.snackbar(
      title ?? 'Warning',
      message,
      backgroundColor: Colors.orange.shade600,
      colorText: Colors.white,
      icon: const Icon(
        Icons.warning_amber_outlined,
        color: Colors.white,
        size: 24,
      ),
      snackPosition: position,
      duration: duration,
      margin: _defaultMargin,
      borderRadius: _defaultBorderRadius,
      onTap: onTap != null ? (_) => onTap() : null,
      isDismissible: isDismissible,
      forwardAnimationCurve: Curves.easeOutBack,
      reverseAnimationCurve: Curves.easeInBack,
    );
  }

  /// Shows an info snack bar with blue theme
  static void showInfo({
    required String message,
    String? title,
    Duration duration = _defaultDuration,
    SnackPosition position = SnackPosition.TOP,
    VoidCallback? onTap,
    bool isDismissible = true,
  }) {
    Get.snackbar(
      title ?? 'Info',
      message,
      backgroundColor: Colors.blue.shade600,
      colorText: Colors.white,
      icon: const Icon(
        Icons.info_outline,
        color: Colors.white,
        size: 24,
      ),
      snackPosition: position,
      duration: duration,
      margin: _defaultMargin,
      borderRadius: _defaultBorderRadius,
      onTap: onTap != null ? (_) => onTap() : null,
      isDismissible: isDismissible,
      forwardAnimationCurve: Curves.easeOutBack,
      reverseAnimationCurve: Curves.easeInBack,
    );
  }

  /// Shows a custom snack bar with full customization options
  static void showCustom({
    required String message,
    String? title,
    required Color backgroundColor,
    Color textColor = Colors.white,
    Widget? icon,
    Duration duration = _defaultDuration,
    SnackPosition position = SnackPosition.TOP,
    VoidCallback? onTap,
    bool isDismissible = true,
    EdgeInsets? margin,
    double? borderRadius,
  }) {
    Get.snackbar(
      title ?? '',
      message,
      backgroundColor: backgroundColor,
      colorText: textColor,
      icon: icon,
      snackPosition: position,
      duration: duration,
      margin: margin ?? _defaultMargin,
      borderRadius: borderRadius ?? _defaultBorderRadius,
      onTap: onTap != null ? (_) => onTap() : null,
      isDismissible: isDismissible,
      forwardAnimationCurve: Curves.easeOutBack,
      reverseAnimationCurve: Curves.easeInBack,
    );
  }

  /// Shows a loading snack bar with progress indicator
  static void showLoading({
    String message = 'Loading...',
    String? title,
    Duration? duration, // null for indefinite loading
    SnackPosition position = SnackPosition.TOP,
    bool isDismissible = false,
  }) {
    Get.snackbar(
      title ?? '',
      message,
      backgroundColor: Colors.grey.shade800,
      colorText: Colors.white,
      icon: const SizedBox(
        width: 24,
        height: 24,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
        ),
      ),
      snackPosition: position,
      duration: duration,
      margin: _defaultMargin,
      borderRadius: _defaultBorderRadius,
      isDismissible: isDismissible,
      showProgressIndicator: true,
      progressIndicatorBackgroundColor: Colors.grey.shade600,
      progressIndicatorValueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
    );
  }

  /// Shows an action snack bar with a button
  static void showAction({
    required String message,
    required String actionLabel,
    required VoidCallback onAction,
    String? title,
    Color backgroundColor = Colors.grey,
    Color textColor = Colors.white,
    Color actionColor = Colors.blue,
    Duration duration = _defaultDuration,
    SnackPosition position = SnackPosition.BOTTOM,
    Widget? icon,
  }) {
    Get.snackbar(
      title ?? '',
      message,
      backgroundColor: backgroundColor,
      colorText: textColor,
      icon: icon,
      snackPosition: position,
      duration: duration,
      margin: _defaultMargin,
      borderRadius: _defaultBorderRadius,
      mainButton: TextButton(
        onPressed: () {
          Get.closeCurrentSnackbar();
          onAction();
        },
        child: Text(
          actionLabel,
          style: TextStyle(
            color: actionColor,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      forwardAnimationCurve: Curves.easeOutBack,
      reverseAnimationCurve: Curves.easeInBack,
    );
  }

  /// Dismisses all current snack bars
  static void dismissAll() {
    Get.closeAllSnackbars();
  }

  /// Dismisses the current snack bar
  static void dismiss() {
    Get.closeCurrentSnackbar();
  }

  /// Shows a network error snack bar with retry option
  static void showNetworkError({
    String message = 'Network connection failed',
    VoidCallback? onRetry,
    Duration duration = const Duration(seconds: 5),
  }) {
    if (onRetry != null) {
      showAction(
        message: message,
        actionLabel: 'RETRY',
        onAction: onRetry,
        title: 'Network Error',
        backgroundColor: Colors.red.shade600,
        icon: const Icon(
          Icons.wifi_off,
          color: Colors.white,
          size: 24,
        ),
        duration: duration,
      );
    } else {
      showError(
        message: message,
        title: 'Network Error',
        duration: duration,
      );
    }
  }

  /// Shows a validation error snack bar
  static void showValidationError({
    required String message,
    Duration duration = _defaultDuration,
  }) {
    showError(
      message: message,
      title: 'Validation Error',
      duration: duration,
    );
  }

  /// Shows an operation completed snack bar
  static void showOperationComplete({
    required String operation,
    Duration duration = _defaultDuration,
  }) {
    showSuccess(
      message: '$operation completed successfully',
      title: 'Complete',
      duration: duration,
    );
  }
}

/// Extension on BuildContext to provide snack bar helpers
extension SnackBarExtension on BuildContext {
  /// Shows a success snack bar
  void showSuccessSnackBar(String message, {String? title}) {
    SnackBarHelper.showSuccess(message: message, title: title);
  }

  /// Shows an error snack bar
  void showErrorSnackBar(String message, {String? title}) {
    SnackBarHelper.showError(message: message, title: title);
  }

  /// Shows a warning snack bar
  void showWarningSnackBar(String message, {String? title}) {
    SnackBarHelper.showWarning(message: message, title: title);
  }

  /// Shows an info snack bar
  void showInfoSnackBar(String message, {String? title}) {
    SnackBarHelper.showInfo(message: message, title: title);
  }
}