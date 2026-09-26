import 'api_client.dart';

class ProfileApi {
  ProfileApi(this.client);
  final ApiClient client;

  Future<Map<String, dynamic>> profile() => client.request('GET', '/users/me');
  Future<Map<String, dynamic>> create({
    required String firstName,
    required String middleName,
    required String lastName,
    required String country,
    required String phone,
  }) => client.request(
    'POST',
    '/users/me',
    body: {
      'first_name': firstName,
      'middle_name': middleName,
      'last_name': lastName,
      'country': country,
      'phone': phone,
    },
  );
  Future<Map<String, dynamic>> updateNames(
    String first,
    String middle,
    String last,
  ) => client.request(
    'PATCH',
    '/users/me/names',
    body: {'first_name': first, 'middle_name': middle, 'last_name': last},
  );
  Future<Map<String, dynamic>> checkTag(String base) =>
      client.request('GET', '/users/me/tag/check', query: {'tag': base});
  Future<Map<String, dynamic>> claimTag(String base) =>
      client.request('POST', '/users/me/tag', body: {'tag': base});
  Future<Map<String, dynamic>> verifyPhone(String phone) => client.request(
    'POST',
    '/users/me/phone/verify',
    body: {'phone_number': phone},
    forceRefresh: true,
  );
  Future<Map<String, dynamic>> setPin(String pin) =>
      client.request('POST', '/users/me/pin', body: {'pin': pin});
  Future<Map<String, dynamic>> verifyPin(String pin) =>
      client.request('POST', '/users/me/pin/verify', body: {'pin': pin});
  Future<Map<String, dynamic>> resetPin() =>
      client.request('POST', '/users/me/pin/reset', forceRefresh: true);
  Future<Map<String, dynamic>> sendEmailOtp() =>
      client.request('POST', '/otp/email/send', body: {});
  Future<Map<String, dynamic>> verifyEmailOtp(String code) =>
      client.request('POST', '/otp/email/verify', body: {'code': code});
  Future<Map<String, dynamic>> uploadSignature() =>
      client.request('GET', '/identity/upload-signature');
  Future<Map<String, dynamic>> verifyIdentity(String bvn, String publicId) =>
      client.request(
        'POST',
        '/identity/verify',
        body: {'bvn': bvn, 'cloudinary_public_id': publicId},
      );
}
