import 'country_item.dart';

const List<CountryItem> kSupportedCountries = [
  CountryItem(
    name: 'Nigeria',
    code: 'NG',
    dialCode: '+234',
    flagWidget: CountryFlagBadge(code: 'NG'),
  ),
  CountryItem(
    name: 'Ghana',
    code: 'GH',
    dialCode: '+233',
    flagWidget: CountryFlagBadge(code: 'GH'),
  ),
  CountryItem(
    name: 'Senegal',
    code: 'SN',
    dialCode: '+221',
    flagWidget: CountryFlagBadge(code: 'SN'),
  ),
  CountryItem(
    name: 'Ivory coast',
    code: 'CI',
    dialCode: '+225',
    flagWidget: CountryFlagBadge(code: 'CI'),
  ),
  CountryItem(
    name: 'Kenya',
    code: 'KE',
    dialCode: '+254',
    flagWidget: CountryFlagBadge(code: 'KE'),
  ),
  CountryItem(
    name: 'South Africa',
    code: 'ZA',
    dialCode: '+27',
    flagWidget: CountryFlagBadge(code: 'ZA'),
  ),
];
