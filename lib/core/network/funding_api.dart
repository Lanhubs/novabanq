import 'package:novabanq/features/receive/models/virtual_account_info.dart';
import 'api_client.dart';

class FundingApi {
  final ApiClient client;

  FundingApi(this.client);

  Future<VirtualAccountInfo> getVirtualAccount() async {
    final data = await client.request('POST', '/funding/virtual-account');
    return VirtualAccountInfo.fromJson(data);
  }
}
