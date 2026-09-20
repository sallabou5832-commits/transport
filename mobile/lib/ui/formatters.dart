String _two(int n) => n.toString().padLeft(2, '0');

String formatHeure(DateTime date) {
  final local = date.toLocal();
  return '${_two(local.hour)}:${_two(local.minute)}';
}

String formatDate(DateTime date) {
  final local = date.toLocal();
  return '${_two(local.day)}/${_two(local.month)}/${local.year}';
}

String formatDateHeure(DateTime date) => '${formatDate(date)} ${formatHeure(date)}';
