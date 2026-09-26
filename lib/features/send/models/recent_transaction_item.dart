class RecentTransactionItem {
  final String name;
  final String subtitle;
  final String date;
  final String? avatarUrl;

  const RecentTransactionItem({
    required this.name,
    required this.subtitle,
    required this.date,
    this.avatarUrl,
  });
}

const List<RecentTransactionItem> kDefaultRecentTransactions = [
  RecentTransactionItem(
    name: 'Noble Godswill',
    subtitle: '10238935890',
    date: '12-08-2023',
  ),
  RecentTransactionItem(
    name: 'Samuel Favour',
    subtitle: '@Samuel.ng',
    date: '11-09-2023',
  ),
  RecentTransactionItem(
    name: 'Philip Stefan',
    subtitle: '@stefan.ken',
    date: '18-09-2023',
  ),
];
