#!/usr/bin/env python
# -*- coding: utf-8 -*-
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.openstack import openstack_full_argument_spec, openstack_module_kwargs

try:
    import ecl as eclsdk
    HAS_ECLSDK=True
except:
    HAS_ECLSDK=False

#
# ECL接続
#
def _get_ecl_connection_from_module(module):
    try:
        #
        # モジュールから接続情報を取得するためのユーティリティを読み込み
        #
        from ansible.module_utils.openstack import openstack_cloud_from_module

        #
        # Cloud インスタンスの取得
        #
        sdk, cloud = openstack_cloud_from_module(module)
    except:
        #
        # Clouds.yaml の 情報読み込み
        #
        import openstack
        cloud_config = module.params['cloud']
        cloud = openstack.connect(cloud=cloud_config)

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
    for storage in cloud_ecl2.storage.storages(True):
        storage_dict = storage.to_dict()
        if storage_dict['name'] == name:
            return storage_dict
    return None

#
# 仮想ストレージのボリュームを名前で検索
#
def _find_storage_volume_by_name(cloud_ecl2, name):
    for volume in cloud_ecl2.storage.volumes(True):
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
    initiator_iqns = module.params['initiator_iqns']
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
        'initiator_iqns'        : initiator_iqns,
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
    #
    argument_spec = openstack_full_argument_spec(
        name=dict(required=True)
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
    # Ansible引数の取得
    #
    name = module.params['name']

    #
    # ECLSDKがインストールされているかの確認
    #
    if HAS_ECLSDK == False:
        module.fail_json(msg='ECLSDK is not exist.')

    #
    # ECLへの接続
    #
    ecl2 = _get_ecl_connection_from_module(module)
    volume = _find_storage_volume_by_name(ecl2, name)

    #
    # ボリュームが存在しない場合
    #
    if volume == None:
        module.fail_json(msg='Volume (%s) is not exist.' %(name))

    #
    # 正常終了
    #
    module.exit_json(volume=volume, changed=False)
    return True

#
# Entry Point
#
if __name__ == '__main__':
    main()

