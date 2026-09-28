import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

class NovaScheduleDateSheet extends StatefulWidget {
  const NovaScheduleDateSheet({super.key});

  @override
  State<NovaScheduleDateSheet> createState() => _NovaScheduleDateSheetState();
}

class _NovaScheduleDateSheetState extends State<NovaScheduleDateSheet> {
  static const _accent = Color(0xFF42C879);

  late final TextEditingController _dateInput;
  late DateTime _selectedDate;
  TimeOfDay? _selectedTime;
  String? _dateError;

  DateTime get _today {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  bool get _canConfirm {
    final time = _selectedTime;
    if (time == null || _dateError != null) return false;
    return DateTime(
      _selectedDate.year,
      _selectedDate.month,
      _selectedDate.day,
      time.hour,
      time.minute,
    ).isAfter(DateTime.now());
  }

  @override
  void initState() {
    super.initState();
    _selectedDate = _today.add(const Duration(days: 1));
    _dateInput = TextEditingController(text: _formatDate(_selectedDate));
  }

  @override
  void dispose() {
    _dateInput.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final insets = MediaQuery.viewInsetsOf(context);
    final lastDate = DateTime(_today.year + 2, _today.month, _today.day);
    return AnimatedPadding(
      duration: const Duration(milliseconds: 180),
      padding: EdgeInsets.only(bottom: insets.bottom),
      child: SafeArea(
        top: false,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: size.height * 0.94),
          child: Material(
            color: Colors.white,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
            clipBehavior: Clip.antiAlias,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 36,
                      height: 4,
                      decoration: BoxDecoration(
                        color: const Color(0xFFD0D5DD),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Schedule payment',
                    style: GoogleFonts.outfit(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: const Color(0xFF101828),
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    'Choose when this transfer should be sent.',
                    style: GoogleFonts.outfit(
                      fontSize: 13,
                      color: const Color(0xFF667085),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _dateInput,
                    keyboardType: TextInputType.datetime,
                    inputFormatters: [
                      FilteringTextInputFormatter.allow(RegExp(r'[0-9/]')),
                      LengthLimitingTextInputFormatter(10),
                    ],
                    onChanged: _handleDateInput,
                    style: GoogleFonts.outfit(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: const Color(0xFF101828),
                    ),
                    decoration: InputDecoration(
                      labelText: 'Date',
                      hintText: 'MM/DD/YYYY',
                      errorText: _dateError,
                      suffixIcon: const Icon(Icons.calendar_month_outlined),
                      floatingLabelStyle: GoogleFonts.outfit(
                        color: _accent,
                        fontWeight: FontWeight.w500,
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: Color(0xFFD0D5DD)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(
                          color: _accent,
                          width: 1.5,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFFF2EDF4),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Theme(
                      data: Theme.of(context).copyWith(
                        colorScheme: Theme.of(context).colorScheme.copyWith(
                          primary: _accent,
                          onPrimary: Colors.white,
                          surface: const Color(0xFFF2EDF4),
                        ),
                      ),
                      child: CalendarDatePicker(
                        key: ValueKey(
                          '${_selectedDate.year}-'
                          '${_selectedDate.month}-'
                          '${_selectedDate.day}',
                        ),
                        initialDate: _selectedDate,
                        firstDate: _today,
                        lastDate: lastDate,
                        onDateChanged: _handleCalendarDate,
                      ),
                    ),
                  ),
                  const Divider(height: 1, color: Color(0xFFEAECF0)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Time',
                          style: GoogleFonts.outfit(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: const Color(0xFF475467),
                          ),
                        ),
                      ),
                      TextButton.icon(
                        onPressed: _chooseTime,
                        icon: const Icon(Icons.schedule_outlined, size: 18),
                        label: Text(
                          _selectedTime?.format(context) ?? 'Select time',
                        ),
                        style: TextButton.styleFrom(foregroundColor: _accent),
                      ),
                    ],
                  ),
                  if (_selectedTime != null && !_canConfirm)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Choose a future time.',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          color: const Color(0xFFB42318),
                        ),
                      ),
                    ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('Cancel'),
                      ),
                      const SizedBox(width: 8),
                      FilledButton(
                        onPressed: _canConfirm ? _confirm : null,
                        style: FilledButton.styleFrom(
                          backgroundColor: _accent,
                          foregroundColor: Colors.white,
                        ),
                        child: const Text('Continue'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _handleDateInput(String value) {
    final parts = value.split('/');
    if (parts.length != 3 || parts.any((part) => part.isEmpty)) {
      setState(() => _dateError = 'Enter a date as MM/DD/YYYY.');
      return;
    }
    final month = int.tryParse(parts[0]);
    final day = int.tryParse(parts[1]);
    final year = int.tryParse(parts[2]);
    if (month == null || day == null || year == null) {
      setState(() => _dateError = 'Enter a valid date.');
      return;
    }
    final date = DateTime(year, month, day);
    final lastDate = DateTime(_today.year + 2, _today.month, _today.day);
    if (date.year != year ||
        date.month != month ||
        date.day != day ||
        date.isBefore(_today) ||
        date.isAfter(lastDate)) {
      setState(() => _dateError = 'Choose a future date within two years.');
      return;
    }
    setState(() {
      _selectedDate = date;
      _dateError = null;
    });
  }

  void _handleCalendarDate(DateTime date) {
    setState(() {
      _selectedDate = date;
      _dateError = null;
      _dateInput.value = TextEditingValue(
        text: _formatDate(date),
        selection: TextSelection.collapsed(offset: _formatDate(date).length),
      );
    });
  }

  Future<void> _chooseTime() async {
    final initialTime = TimeOfDay.fromDateTime(
      DateTime.now().add(const Duration(minutes: 30)),
    );
    final selectedTime = await showTimePicker(
      context: context,
      initialTime: _selectedTime ?? initialTime,
      builder: (context, child) => Theme(
        data: Theme.of(context).copyWith(
          colorScheme: Theme.of(context).colorScheme.copyWith(primary: _accent),
        ),
        child: child!,
      ),
    );
    if (selectedTime != null && mounted) {
      setState(() => _selectedTime = selectedTime);
    }
  }

  void _confirm() {
    final time = _selectedTime;
    if (time == null || !_canConfirm) return;
    Navigator.of(context).pop(
      DateTime(
        _selectedDate.year,
        _selectedDate.month,
        _selectedDate.day,
        time.hour,
        time.minute,
      ),
    );
  }

  String _formatDate(DateTime date) =>
      '${date.month.toString().padLeft(2, '0')}/'
      '${date.day.toString().padLeft(2, '0')}/'
      '${date.year.toString().padLeft(4, '0')}';
}
