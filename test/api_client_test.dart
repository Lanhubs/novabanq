import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:novabanq/core/network/api_client.dart';

void main() {
  test('uses a fresh token and unwraps successful data', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
    var calls = 0;
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (request, handler) {
          expect(request.headers['Authorization'], 'Bearer token-${++calls}');
          handler.resolve(
            Response(
              requestOptions: request,
              data: {
                'success': true,
                'data': {'account_number': '0123456789'},
                'error': null,
              },
            ),
          );
        },
      ),
    );
    final client = ApiClient(
      dio: dio,
      tokenProvider: (_) async => 'token-${calls + 1}',
    );
    expect(
      (await client.request('GET', '/users/me'))['account_number'],
      '0123456789',
    );
    await client.request('GET', '/users/me');
    expect(calls, 2);
  });

  test('keeps backend error codes for client decisions', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (request, handler) {
          handler.resolve(
            Response(
              requestOptions: request,
              statusCode: 409,
              data: {
                'success': false,
                'data': null,
                'error': {
                  'code': 'TAG_TAKEN',
                  'message': 'Choose another tag.',
                  'details': {},
                },
              },
            ),
          );
        },
      ),
    );
    final client = ApiClient(dio: dio, tokenProvider: (_) async => 'token');
    await expectLater(
      client.request('POST', '/users/me/tag', body: {'tag': 'taken'}),
      throwsA(isA<ApiFailure>().having((e) => e.code, 'code', 'TAG_TAKEN')),
    );
  });

  test('refreshes an invalid Firebase token once', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1'));
    var calls = 0;
    final refreshes = <bool>[];
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (request, handler) {
          calls++;
          handler.resolve(
            Response(
              requestOptions: request,
              data: calls == 1
                  ? {
                      'success': false,
                      'data': null,
                      'error': {'code': 'AUTH_INVALID', 'message': 'Expired'},
                    }
                  : {
                      'success': true,
                      'data': {'uid': 'abc'},
                      'error': null,
                    },
            ),
          );
        },
      ),
    );
    final client = ApiClient(
      dio: dio,
      tokenProvider: (refresh) async {
        refreshes.add(refresh);
        return refresh ? 'fresh' : 'cached';
      },
    );
    expect((await client.request('GET', '/users/me'))['uid'], 'abc');
    expect(calls, 2);
    expect(refreshes, [false, true]);
  });
}
