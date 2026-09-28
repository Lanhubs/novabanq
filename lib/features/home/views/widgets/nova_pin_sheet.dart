import 'package:flutter/material.dart';
import 'package:novabanq/core/network/api_client.dart';
import 'package:novabanq/core/network/nova_api.dart';
import 'package:novabanq/features/home/models/nova_transfer.dart';
import 'package:novabanq/features/send/views/widgets/transaction_pin_bottom_sheet.dart';

class NovaPinSheet extends StatefulWidget {
  const NovaPinSheet({super.key, required this.api, required this.preview});
  final NovaApi api;
  final NovaTransferPreview preview;

  @override
  State<NovaPinSheet> createState() => _NovaPinSheetState();
}

class _NovaPinSheetState extends State<NovaPinSheet> {
  String pin = '';
  String? error;
  bool isLoading = false;
  bool uncertain = false;

  Future<void> _confirm() async {
    if (isLoading || uncertain) return;
    if (pin.length != 5) {
      setState(() => error = 'Enter your 5-digit PIN.');
      return;
    }
    final submittedPin = pin;
    setState(() {
      isLoading = true;
      error = null;
      pin = '';
    });
    try {
      final result = await widget.api.executeTransfer(
        preview: widget.preview,
        pin: submittedPin,
      );
      if (mounted) Navigator.of(context).pop(result);
    } on ApiFailure catch (failure) {
      if (!mounted) return;
      setState(() {
        if (failure.status == 409 && failure.code == 'VALIDATION_ERROR') {
          error =
              'The recipient changed. Close this sheet and review a new quote.';
          uncertain = true;
        } else if (failure.code == 'NETWORK_ERROR') {
          error =
              'Connection uncertain. Check transaction history before trying again.';
          uncertain = true;
        } else if (failure.code == 'DUPLICATE_TRANSFER') {
          error =
              'This may have settled already. Check transaction history before sending again.';
          uncertain = true;
        } else if (failure.status != null && failure.status! >= 500) {
          error =
              'Nova is unavailable. Check transaction history before trying again.';
          uncertain = true;
        } else {
          error = failure.message;
        }
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          error =
              'Result uncertain. Check transaction history before trying again.';
          uncertain = true;
        });
      }
    } finally {
      if (mounted) setState(() => isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !isLoading,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (error != null)
            Container(
              width: double.infinity,
              color: Colors.white,
              padding: const EdgeInsets.all(12),
              child: Text(
                error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
              ),
            ),
          TransactionPinBottomSheet(
            pin: pin,
            isLoading: isLoading,
            isDisabled: uncertain,
            onKeyPress: (digit) {
              if (!isLoading && !uncertain && pin.length < 5) {
                setState(() => pin += digit);
              }
            },
            onBackspace: () {
              if (!isLoading && pin.isNotEmpty) {
                setState(() => pin = pin.substring(0, pin.length - 1));
              }
            },
            onClear: () {
              if (!isLoading) setState(() => pin = '');
            },
            onConfirm: _confirm,
          ),
        ],
      ),
    );
  }
}
