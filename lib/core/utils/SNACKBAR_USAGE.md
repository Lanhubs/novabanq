# SnackBar Helper Usage Guide

The `SnackBarHelper` provides a convenient way to display consistent snack bars throughout your NovaBank Flutter app. It offers various pre-styled variants and full customization options.

## Features

- 🎨 **Pre-styled variants**: Success, Error, Warning, Info
- ⚡ **Quick access**: Static methods for instant use
- 🎯 **Context extensions**: Use directly from BuildContext
- 🔧 **Fully customizable**: Override any property when needed
- 📱 **Responsive**: Works with GetX snackbar system
- 🎭 **Animations**: Smooth entrance/exit animations
- 🎬 **Action support**: Add buttons and interactions
- 📡 **Network helpers**: Built-in retry functionality

## Basic Usage

### Import the helper
```dart
import 'package:novabanq/core/utils/helpers.dart';
// or directly
import 'package:novabanq/core/utils/snack_bar_helper.dart';
```

### Success Messages
```dart
// Simple success
SnackBarHelper.showSuccess(message: 'Transaction completed successfully!');

// With custom title
SnackBarHelper.showSuccess(
  message: 'Your profile has been updated',
  title: 'Profile Updated',
);

// With custom duration and callback
SnackBarHelper.showSuccess(
  message: 'Payment successful',
  duration: const Duration(seconds: 5),
  onTap: () => navigateToTransactionDetails(),
);
```

### Error Messages
```dart
// Simple error
SnackBarHelper.showError(message: 'Something went wrong!');

// Validation error (pre-configured)
SnackBarHelper.showValidationError(
  message: 'Please enter a valid email address',
);

// Network error with retry
SnackBarHelper.showNetworkError(
  message: 'Unable to connect to server',
  onRetry: () => retryNetworkRequest(),
);
```

### Warning Messages
```dart
SnackBarHelper.showWarning(
  message: 'Your session will expire in 5 minutes',
  title: 'Session Warning',
);
```

### Info Messages
```dart
SnackBarHelper.showInfo(
  message: 'New features are available in settings',
  title: 'Update Available',
);
```

## Advanced Usage

### Loading States
```dart
// Show loading snackbar
SnackBarHelper.showLoading(
  message: 'Processing your request...',
);

// Later, dismiss and show result
SnackBarHelper.dismiss();
SnackBarHelper.showSuccess(message: 'Request processed!');
```

### Action Snack Bars
```dart
// Undo functionality
SnackBarHelper.showAction(
  message: 'Message deleted',
  actionLabel: 'UNDO',
  onAction: () => restoreMessage(),
);

// Navigation action
SnackBarHelper.showAction(
  message: 'New transaction received',
  actionLabel: 'VIEW',
  onAction: () => navigateToTransaction(),
  backgroundColor: Colors.blue.shade600,
  icon: const Icon(Icons.account_balance_wallet, color: Colors.white),
);
```

### Custom Snack Bars
```dart
SnackBarHelper.showCustom(
  message: 'Welcome to NovaBank Premium!',
  title: 'Premium Account',
  backgroundColor: Colors.purple.shade600,
  icon: const Icon(Icons.star, color: Colors.amber),
  duration: const Duration(seconds: 4),
  borderRadius: 20.0,
  margin: const EdgeInsets.all(20),
);
```

### Context Extensions
```dart
class MyWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: () {
        // Use context extensions for cleaner code
        context.showSuccessSnackBar('Profile saved!');
        context.showErrorSnackBar('Failed to load data');
        context.showWarningSnackBar('Low balance');
        context.showInfoSnackBar('App updated');
      },
      child: Text('Show Snackbar'),
    );
  }
}
```

## Banking-Specific Examples

### Transfer Operations
```dart
// Transfer success
SnackBarHelper.showOperationComplete(operation: 'Money transfer');

// Insufficient funds
SnackBarHelper.showWarning(
  message: 'Insufficient funds for this transaction',
  title: 'Transaction Failed',
);
```

### Security Alerts
```dart
// Account security
SnackBarHelper.showError(
  message: 'Account temporarily locked due to suspicious activity',
  title: 'Security Alert',
  duration: const Duration(seconds: 8),
);

// Verification required
SnackBarHelper.showInfo(
  message: 'Please verify your identity to continue',
  title: 'Security Check',
);
```

### Login States
```dart
// Login success
SnackBarHelper.showSuccess(
  message: 'Welcome back, John!',
  title: 'Login Successful',
  duration: const Duration(seconds: 2),
);
```

## Utility Methods

### Dismissal
```dart
// Dismiss current snackbar
SnackBarHelper.dismiss();

// Dismiss all snackbars
SnackBarHelper.dismissAll();
```

## Customization Options

All snack bar methods support these optional parameters:

- `title`: Custom title (defaults to variant name)
- `duration`: How long to show (default: 3 seconds)
- `position`: Top or bottom positioning
- `onTap`: Callback when snackbar is tapped
- `isDismissible`: Whether user can dismiss by swiping
- `margin`: Custom margins
- `borderRadius`: Custom corner radius

## Best Practices

1. **Use appropriate variants**: Match the snack bar type to the message context
2. **Keep messages concise**: Snack bars should be brief and scannable
3. **Provide actions when helpful**: Use action snack bars for undoable operations
4. **Handle loading states**: Use loading snack bars for long operations
5. **Consider positioning**: Use top for alerts, bottom for actions
6. **Test on different devices**: Ensure margins and sizing work across screen sizes

## Migration from Standard SnackBar

Replace this:
```dart
ScaffoldMessenger.of(context).showSnackBar(
  SnackBar(
    content: Text('Success!'),
    backgroundColor: Colors.green,
    duration: Duration(seconds: 3),
  ),
);
```

With this:
```dart
SnackBarHelper.showSuccess(message: 'Success!');
```

The helper provides consistent styling, animations, and behavior across your entire app while reducing boilerplate code.