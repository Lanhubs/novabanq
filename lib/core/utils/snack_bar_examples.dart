import 'package:flutter/material.dart';
import 'snack_bar_helper.dart';

/// Example usage of SnackBarHelper
/// This file demonstrates how to use the different snack bar variants
/// You can delete this file after reviewing the examples
class SnackBarExamples {
  
  /// Example: Success operations
  static void exampleSuccess() {
    // Simple success message
    SnackBarHelper.showSuccess(message: 'Transaction completed successfully!');
    
    // Success with custom title and duration
    SnackBarHelper.showSuccess(
      message: 'Your account has been updated',
      title: 'Profile Updated',
      duration: const Duration(seconds: 5),
    );
    
    // Success with tap callback
    SnackBarHelper.showSuccess(
      message: 'Payment successful',
      onTap: () => print('User tapped success snackbar'),
    );
  }

  /// Example: Error handling
  static void exampleError() {
    // Simple error message
    SnackBarHelper.showError(message: 'Something went wrong!');
    
    // Validation error
    SnackBarHelper.showValidationError(
      message: 'Please enter a valid email address',
    );
    
    // Network error with retry
    SnackBarHelper.showNetworkError(
      message: 'Unable to connect to server',
      onRetry: () {
        print('Retrying network request...');
        // Add your retry logic here
      },
    );
  }

  /// Example: Warning and info messages
  static void exampleWarningAndInfo() {
    // Warning message
    SnackBarHelper.showWarning(
      message: 'Your session will expire in 5 minutes',
      title: 'Session Warning',
    );
    
    // Info message
    SnackBarHelper.showInfo(
      message: 'New features are available in settings',
      title: 'Update Available',
    );
  }

  /// Example: Loading states
  static void exampleLoading() {
    // Show loading
    SnackBarHelper.showLoading(
      message: 'Processing your request...',
    );
    
    // Simulate some work, then dismiss
    Future.delayed(const Duration(seconds: 3), () {
      SnackBarHelper.dismiss();
      SnackBarHelper.showSuccess(message: 'Request processed successfully!');
    });
  }

  /// Example: Action snack bars
  static void exampleActions() {
    // Undo action
    SnackBarHelper.showAction(
      message: 'Message deleted',
      actionLabel: 'UNDO',
      onAction: () {
        print('Undo action triggered');
        SnackBarHelper.showInfo(message: 'Message restored');
      },
      backgroundColor: Colors.grey.shade800,
    );
    
    // View details action
    SnackBarHelper.showAction(
      message: 'New transaction received',
      actionLabel: 'VIEW',
      onAction: () {
        print('Navigate to transaction details');
      },
      backgroundColor: Colors.blue.shade600,
      icon: const Icon(Icons.account_balance_wallet, color: Colors.white),
    );
  }

  /// Example: Custom snack bars
  static void exampleCustom() {
    // Custom purple theme for special notifications
    SnackBarHelper.showCustom(
      message: 'Welcome to NovaBank Premium!',
      title: 'Premium Account',
      backgroundColor: Colors.purple.shade600,
      icon: const Icon(Icons.star, color: Colors.amber),
      duration: const Duration(seconds: 4),
    );
    
    // Custom notification with rounded corners
    SnackBarHelper.showCustom(
      message: 'Your card has been blocked for security',
      title: 'Security Alert',
      backgroundColor: Colors.deepOrange,
      icon: const Icon(Icons.security, color: Colors.white),
      borderRadius: 20.0,
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
    );
  }

  /// Example: Using context extensions (in a widget)
  static void exampleWithContext(BuildContext context) {
    // Using context extensions for cleaner code
    context.showSuccessSnackBar('Profile saved successfully!');
    context.showErrorSnackBar('Failed to load data');
    context.showWarningSnackBar('Low account balance');
    context.showInfoSnackBar('App updated to version 2.1.0');
  }

  /// Example: Banking-specific scenarios
  static void exampleBankingScenarios() {
    // Transfer success
    SnackBarHelper.showOperationComplete(operation: 'Money transfer');
    
    // Login success
    SnackBarHelper.showSuccess(
      message: 'Welcome back, John!',
      title: 'Login Successful',
      duration: const Duration(seconds: 2),
    );
    
    // Insufficient funds
    SnackBarHelper.showWarning(
      message: 'Insufficient funds for this transaction',
      title: 'Transaction Failed',
    );
    
    // Security verification
    SnackBarHelper.showInfo(
      message: 'Please verify your identity to continue',
      title: 'Security Check',
    );
    
    // Account locked
    SnackBarHelper.showError(
      message: 'Account temporarily locked due to suspicious activity',
      title: 'Security Alert',
      duration: const Duration(seconds: 8),
    );
  }

  /// Example: Batch operations
  static void exampleBatchOperations() {
    // Dismiss all current snack bars
    SnackBarHelper.dismissAll();
    
    // Show multiple notifications in sequence
    Future.delayed(const Duration(milliseconds: 500), () {
      SnackBarHelper.showInfo(message: 'Starting batch processing...');
    });
    
    Future.delayed(const Duration(seconds: 2), () {
      SnackBarHelper.dismiss();
      SnackBarHelper.showLoading(
        message: 'Processing transactions...',
        duration: const Duration(seconds: 3),
      );
    });
    
    Future.delayed(const Duration(seconds: 5), () {
      SnackBarHelper.dismiss();
      SnackBarHelper.showSuccess(
        message: '25 transactions processed successfully',
        title: 'Batch Complete',
      );
    });
  }
}