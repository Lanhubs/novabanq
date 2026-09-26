class HomeCountryCurrency {
  final String name;
  final String countryCode;
  final String currencyCode;
  final String symbol;

  const HomeCountryCurrency({
    required this.name,
    required this.countryCode,
    required this.currencyCode,
    required this.symbol,
  });
}

const List<HomeCountryCurrency> kHomeSupportedCurrencies = [
  HomeCountryCurrency(
    name: 'Nigeria',
    countryCode: 'NG',
    currencyCode: 'NGN',
    symbol: '₦',
  ),
  HomeCountryCurrency(
    name: 'Ghana',
    countryCode: 'GH',
    currencyCode: 'GHS',
    symbol: 'GH₵',
  ),
  HomeCountryCurrency(
    name: 'Senegal',
    countryCode: 'SN',
    currencyCode: 'XOF',
    symbol: 'CFA',
  ),
  HomeCountryCurrency(
    name: 'Ivory Coast (CIV)',
    countryCode: 'CI',
    currencyCode: 'XOF',
    symbol: 'CFA',
  ),
  HomeCountryCurrency(
    name: 'Kenya',
    countryCode: 'KE',
    currencyCode: 'KES',
    symbol: 'KSh',
  ),
  HomeCountryCurrency(
    name: 'South Africa',
    countryCode: 'ZA',
    currencyCode: 'ZAR',
    symbol: 'R',
  ),
];
