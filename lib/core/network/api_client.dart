import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';

class ApiFailure implements Exception {
  final String code;
  final String message;
  final int? status;
  final Map<String, dynamic> details;

  const ApiFailure(
    this.code,
    this.message, {
    this.status,
    this.details = const {},
  });

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({
    Dio? dio,
    FirebaseAuth? auth,
    Future<String?> Function(bool)? tokenProvider,
  }) : _tokenProvider = tokenProvider,
       _auth = tokenProvider == null ? (auth ?? FirebaseAuth.instance) : null,
       _dio =
           dio ??
           Dio(
             BaseOptions(
               baseUrl: const String.fromEnvironment(
                 'API_URL',
                 defaultValue: 'https://novabanq-api.onrender.com/api/v1',
               ),
               connectTimeout: const Duration(seconds: 10),
               receiveTimeout: const Duration(seconds: 20),
               contentType: Headers.jsonContentType,
             ),
           );

  final Dio _dio;
  final FirebaseAuth? _auth;
  final Future<String?> Function(bool)? _tokenProvider;

  Future<Map<String, dynamic>> request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? query,
    bool forceRefresh = false,
  }) async {
    final token = _tokenProvider != null
        ? await _tokenProvider(forceRefresh)
        : await _auth?.currentUser?.getIdToken(forceRefresh);
    if (token == null) {
      throw const ApiFailure('AUTH_REQUIRED', 'Sign in to continue.');
    }
    try {
      final response = await _dio.request<Map<String, dynamic>>(
        path,
        data: body,
        queryParameters: query,
        options: Options(
          method: method,
          headers: {'Authorization': 'Bearer $token'},
        ),
      );
      final envelope = response.data ?? const <String, dynamic>{};
      if (envelope['success'] != true) {
        throw _failure(envelope, response.statusCode);
      }
      final data = envelope['data'];
      return data is Map<String, dynamic> ? data : <String, dynamic>{};
    } on ApiFailure catch (failure) {
      if (failure.code == 'AUTH_INVALID' && !forceRefresh) {
        return request(
          method,
          path,
          body: body,
          query: query,
          forceRefresh: true,
        );
      }
      rethrow;
    } on DioException catch (error) {
      final payload = error.response?.data;
      if (payload is Map<String, dynamic>) {
        final failure = _failure(payload, error.response?.statusCode);
        if (failure.code == 'AUTH_INVALID' && !forceRefresh) {
          return request(
            method,
            path,
            body: body,
            query: query,
            forceRefresh: true,
          );
        }
        throw failure;
      }
      throw ApiFailure(
        'NETWORK_ERROR',
        'Connection failed. Please try again.',
        status: error.response?.statusCode,
      );
    }
  }

  ApiFailure _failure(Map<String, dynamic> payload, int? status) {
    final error = payload['error'];
    if (error is Map) {
      return ApiFailure(
        error['code']?.toString() ?? 'INTERNAL_ERROR',
        error['message']?.toString() ?? 'Something went wrong.',
        status: status,
        details: error['details'] is Map<String, dynamic>
            ? error['details'] as Map<String, dynamic>
            : const {},
      );
    }
    return ApiFailure(
      'INTERNAL_ERROR',
      'Something went wrong.',
      status: status,
    );
  }
}
