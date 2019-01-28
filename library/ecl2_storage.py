#!/usr/bin/env python
# -*- coding: utf-8 -*-
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.openstack import openstack_full_argument_spec, openstack_module_kwargs

try:
    import ecl as eclsdk
    HAS_ECLSDK=True
except:
    HAS_ECLSDK=False

try:
    from ansible.module_utils.openstack import openstack_cloud_from_module
except:
    #
    # 古いAnsibleへの対応
    #
    def openstack_cloud_from_module(module, min_version='0.12.0'):
        from distutils.version import StrictVersion
        try:
            # Due to the name shadowing we should import other way
            import importlib
            sdk = importlib.import_module('openstack')
        except ImportError:
            module.fail_json(msg='openstacksdk is required for this module')
    
        if min_version:
            if StrictVersion(sdk.version.__version__) < StrictVersion(min_version):
                module.fail_json(
                    msg="To utilize this module, the installed version of"
                        "the openstacksdk library MUST be >={min_version}".format(
                            min_version=min_version))
    
        cloud_config = module.params.pop('cloud', None)
        try:
            if isinstance(cloud_config, dict):
                fail_message = (
                    "A cloud config dict was provided to the cloud parameter"
                    " but also a value was provided for {param}. If a cloud"
                    " config dict is provided, {param} should be"
                    " excluded.")
                for param in (
                        'auth', 'region_name', 'verify',
                        'cacert', 'key', 'api_timeout', 'auth_type'):
                    if module.params[param] is not None:
                        module.fail_json(msg=fail_message.format(param=param))
                # For 'interface' parameter, fail if we receive a non-default value
                if module.params['interface'] != 'public':
                    module.fail_json(msg=fail_message.format(param='interface'))
                return sdk, sdk.connect(**cloud_config)
            else:
                return sdk, sdk.connect(
                    cloud=cloud_config,
                    auth_type=module.params['auth_type'],
                    auth=module.params['auth'],
                    region_name=module.params['region_name'],
                    verify=module.params['verify'],
                    cacert=module.params['cacert'],
                    key=module.params['key'],
                    api_timeout=module.params['api_timeout'],
                    interface=module.params['interface'],
                )
        except sdk.exceptions.SDKException as e:
            # Probably a cloud configuration/login error
            module.fail_json(msg=str(e))

#
# ECL接続
#
def _get_ecl_connection_from_module(module):
    #
    # Cloud インスタンスの取得
    #
    sdk, cloud = openstack_cloud_from_module(module)

    #
    # 設定情報の取り出し
    #
    # [参考]
    # {
    #   'username'          : 'API 鍵',
    #   'password'          : 'API 秘密鍵',
    #   'project_id'        : 'テナントID',
    #   'user_domain_id'    : 'default',
    #   'project_domain_id' : 'default',
    #   'auth_url'          : '認証サーバURL'
    # }
    #
    auth_args = cloud.config.get_auth_args()

    #
    # 不要な項目はフィルタ
    #
    ecl2_args = {
        'username'          : auth_args['username'],
        'password'          : auth_args['password'],
        'project_id'        : auth_args['project_id'],
        'user_domain_id'    : auth_args['user_domain_id'],
        'project_domain_id' : auth_args['project_domain_id'],
        'auth_url'          : auth_args['auth_url']
    }

    #
    # ECL2.0に接続する
    #
    return eclsdk.connection.Connection(**ecl2_args)

#
# 仮想ストレージを名前で検索
#
def _find_storage_by_name(cloud_ecl2, name):
    for storage in cloud_ecl2.storage.storages(False):
        storage_dict = storage.to_dict()
        if storage_dict['name'] == name:
            return storage_dict
    return None

#
# 仮想ストレージのボリュームを名前で検索
#
def _find_storage_volume_by_name(cloud_ecl2, name):
    for volume in cloud_ecl2.storage.volumes(False):
        volume_dict = volume.to_dict()
        if volume_dict['name'] == name:
            return volume_dict
    return None

#
# 仮想ネットワークの検索
#
def _find_network_by_name(cloud_ecl2, name):
    for network in cloud_ecl2.network.networks():
        network_dict = network.to_dict()
        if network_dict['name'] == name:
            return network_dict
    return None

#
# 仮想サブネットの検索
#
def _find_network_subnet_by_name(cloud_ecl2, name):
    for subnet in cloud_ecl2.network.subnets():
        subnet_dict = subnet.to_dict()
        if subnet_dict['name'] == name:
            return subnet_dict
    return None

#
# 仮想ストレージの作成
#
def _create_storage(module, cloud_ecl2):
    #
    # 必要な引数の取得
    #
    name = module.params['name']
    subnet_name = module.params['subnet']
    ip_addr_pool_start = module.params['ip_addr_pool_start']
    ip_addr_pool_end = module.params['ip_addr_pool_end']
    #
    # 待機時間の取得
    #
    wait = module.params['wait']
    timeout = int(module.params['timeout'])

    #
    # サブネットの入力チェック
    #
    if subnet_name == None:
        module.fail_json(msg='Please input subnet field.')
        return False

    #
    # サブネットの取得
    #
    subnet = _find_network_subnet_by_name(cloud_ecl2, subnet_name)
    if subnet == None:
        module.fail_json(msg='Network subnet(%s) is not exist.' %(subnet_name))
        return False

    #
    # IPの確認
    #
    if ip_addr_pool_start == None or ip_addr_pool_end == None:
        module.fail_json(msg='Please check ip_addr_pool_start & ip_addr_pool_end field.')
        return False

    #
    # 引数の取得
    #
    args = {
        'name' : name,
        'network_id' : subnet['network_id'],
        'subnet_id' : subnet['id'],
        'volume_type_id' : '6328d234-7939-4d61-9216-736de66d15f9',
        'ip_addr_pool' : {
            'start' : ip_addr_pool_start,
            'end'   : ip_addr_pool_end
        }
    }

    #
    # ストレージの作成
    #
    new_storage = cloud_ecl2.storage.create_storage(**args)
    if wait == True:
        cloud_ecl2.storage.wait_for_status(new_storage, status='available', wait=timeout)
    return True

#
# 仮想ストレージの削除
#
def _delete_storage_by_name(cloud_ecl2, name):
    # ストレージの検索
    storage = _find_storage_by_name(cloud_ecl2, name)
    if not storage == None:
        # ストレージの削除
        storage_id = storage['id']
        cloud_ecl2.storage.delete_storage(storage_id)
        return True
    return False

#
# 仮想ストレージ内にボリュームを作成
#
def _create_storage_volume(module, cloud_ecl2):
    #
    # 必要な引数の取得
    #
    name = module.params['name']
    size = module.params['size']
    iops_per_gb = module.params['iops_per_gb']
    virtual_storage_name = module.params['virtual_storage']
    availability_zone = module.params['availability_zone']
    #
    # 待機時間の取得
    #
    wait = module.params['wait']
    timeout = int(module.params['timeout'])

    #
    # ストレージの検索
    #
    storage = _find_storage_by_name(cloud_ecl2, virtual_storage_name)
    if storage == None:
        module.fail_json(msg='Virtual storage(%s) is not exist.' %(virtual_storage_name))
        return False

    #
    # 引数の取得
    #
    args = {
        'name'                  : name,
        'size'                  : int(size),        # サイズは整数値型でないとパラメータ不正が起こる
        'iops_per_gb'           : str(iops_per_gb), # iopsは文字列型でないとパラメータ不正が起こる
        'virtual_storage_id'    : storage['id'],
        'availability_zone'     : availability_zone
    }

    #
    # ボリュームの作成
    #
    new_volume = cloud_ecl2.storage.create_volume(**args)
    if wait == True:
        cloud_ecl2.storage.wait_for_status(new_volume, status='available', wait=timeout)
    return True

#
# 仮想ストレージ内のボリュームを削除
#
def _delete_storage_volume_by_name(module, cloud_ecl2):
    #
    # 必要な引数の取得
    #
    name = module.params['name']

    #
    # ボリュームの検索
    #
    volume = _find_storage_volume_by_name(cloud_ecl2, name)
    if not volume == None:
        # ボリュームの削除
        volume_id = volume['id']
        cloud_ecl2.storage.delete_volume(volume_id)
    return False

#
# ストレージサービス: ブロックストレージの作成
#
def main():
    #
    # Open Stack 共通引数取得
    # - name		: 仮想ストレージ名
    # - subnet_id	: サブネットID
    # - volume_type_id	= "6328d234-7939-4d61-9216-736de66d15f9",(固定？)
    # - ip_addr_pool	= { 'start' : '10.0.2.201', 'end' : '10.0.2.231' }
    #
    argument_spec = openstack_full_argument_spec(
        name=dict(required=True),
        subnet=dict(required=False),
        ip_addr_pool_start=dict(required=False),
        ip_addr_pool_end=dict(required=False),
        state=dict(default='present', choices=['absent', 'present'])
    )
    module_kwargs = openstack_module_kwargs()

    #
    # Ansible Module の 定義
    #
    module = AnsibleModule(
        argument_spec = argument_spec,
        supports_check_mode = True,
        **module_kwargs
    )

    #
    # 仮想ストレージ名の取得
    #
    name = module.params['name']
    state = module.params['state']

    #
    # ECLSDKがインストールされているかの確認
    #
    if HAS_ECLSDK == False:
        module.fail_json(msg='ECLSDK is not exist.')

    #
    # ECLへの接続
    #
    ecl2 = _get_ecl_connection_from_module(module)
    storage = _find_storage_by_name(ecl2, name)

    #
    # 仮想ストレージの作成
    #
    if state == 'present':
        #
        # 既に仮想ストレージが存在する場合
        #
        if not storage == None:
            module.exit_json(msg = 'Virtual storage(%s) is already exist.' %(name), changed=False)

        #
        # 仮想ストレージの作成
        #
        _create_storage(module, ecl2)

        #
        # 正常終了
        #
        module.exit_json(changed=True)
        return True
    else:
        #
        # 既に仮想ストレージが存在しない場合
        #
        if storage == None:
            module.exit_json(msg = 'Virtual storage(%s) is not exist.' %(name), changed=False)

        #
        # 仮想ストレージの削除
        #
        _delete_storage_by_name(ecl2, name)

        #
        # 正常終了
        #
        module.exit_json(changed=True)
        return True

#
# Entry Point
#
if __name__ == '__main__':
    main()

