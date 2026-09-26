import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import 'api_client.dart';
import 'profile_api.dart';

class IdentityService {
  IdentityService(this.api);
  final ProfileApi api;

  Future<Map<String, dynamic>> verifyWithCamera(String bvn) async {
    if (!RegExp(r'^\d{11}$').hasMatch(bvn) || bvn == '00000000000') {
      throw const ApiFailure('VALIDATION_ERROR', 'Enter a valid 11-digit BVN.');
    }
    final image = await ImagePicker().pickImage(
      source: ImageSource.camera,
      maxWidth: 1200,
      imageQuality: 82,
    );
    if (image == null) {
      throw const ApiFailure('CANCELLED', 'Photo capture cancelled.');
    }
    final signed = await api.uploadSignature();
    final cloud = signed['cloud_name']?.toString() ?? '';
    if (cloud.isEmpty) {
      throw const ApiFailure('INTERNAL_ERROR', 'Image upload unavailable.');
    }
    final data = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        await image.readAsBytes(),
        filename: 'selfie.jpg',
      ),
      'api_key': signed['api_key'],
      'folder': signed['folder'],
      'timestamp': signed['timestamp'],
      'access_mode': signed['access_mode'],
      'signature': signed['signature'],
    });
    try {
      final response =
          await Dio(
            BaseOptions(
              connectTimeout: const Duration(seconds: 10),
              sendTimeout: const Duration(seconds: 30),
              receiveTimeout: const Duration(seconds: 30),
            ),
          ).post<Map<String, dynamic>>(
            'https://api.cloudinary.com/v1_1/$cloud/image/upload',
            data: data,
          );
      final publicId = response.data?['public_id']?.toString() ?? '';
      if (!publicId.startsWith('kyc-temp/')) {
        throw const ApiFailure(
          'INTERNAL_ERROR',
          'Image upload could not be verified.',
        );
      }
      return api.verifyIdentity(bvn, publicId);
    } on DioException {
      throw const ApiFailure(
        'NETWORK_ERROR',
        'Image upload failed. Please retry.',
      );
    }
  }
}
