#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ecl as eclsdk
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.openstack import (
    openstack_full_argument_spec, openstack_cloud_from_module, openstack_module_kwargs)

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
def _find_storage_by_name(ecl2_connection, name):
    for storage in ecl2_connection.storage.storages(False):
        storage_dict = storage.to_dict()
        if storage_dict['name'] == name:
            return storage_dict
    return None

#
# 仮想ストレージのボリュームを名前で検索
#
def _find_storage_volume_by_name(ecl2_connection, name):
    for volume in ecl2_connection.storage.volumes(False):
        volume_dict = volume.to_dict()
        if volume_dict['name'] == name:
            return volume_dict
    return None

#
# 仮想ネットワークの検索
#
def _find_network_by_name(ecl2_connection, name):
    for network in ecl2_connection.network.networks():
        network_dict = network.to_dict()
        if network_dict['name'] == name:
            return network_dict
    return None

#
# 仮想サブネットの検索
#
def _find_network_subnet_by_name(ecl2_connection, name):
    for subnet in ecl2_connection.network.subnets():
        subnet_dict = subnet.to_dict()
        if subnet_dict['name'] == name:
            return subnet_dict
    return None

#
# 仮想ストレージの作成
#
def _create_storage(module, ecl2_connection, name, subnet_name, ip_pool_start, ip_pool_end):
    #
    # サブネットの取得
    #
    subnet = _find_network_subnet_by_name(ecl2_connection, subnet_name)
    if subnet == None:
        module.fail_json('Network subnet(%s) is not exist.' %(subnet_name))
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
            'start' : ip_pool_start,
            'end'   : ip_pool_end
        }
    }

    #
    # ストレージの作成
    #
    ecl2_connection.storage.create_storage(**args)
    return True

#
# 仮想ストレージの削除
#
def _delete_storage_by_name(ecl2_connection, name):
    # ストレージの検索
    storage = _find_storage_by_name(ecl2_connection, name)
    if not storage == None:
        # ストレージの削除
        storage_id = storage['id']
        ecl2_connection.storage.delete_storage(storage_id)
        return True
    return False

#
# 仮想ストレージ内にボリュームを作成
#
def _create_storage_volume(module, ecl2_connection, name, size, iops_per_gb, virtual_storage_name, availability_zone):
    #
    # ストレージの検索
    #
    storage = _find_storage_by_name(ecl2_connection, virtual_storage_name)
    if storage == None:
        module.fail_json('Virtual storage(%s) is not exist.' %(virtual_storage_name))
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
    ecl2_connection.storage.create_volume(**args)
    return True

#
# ストレージサービス: ブロックストレージの作成
#
def main():
    #
    # Open Stack 共通引数取得
    #
    argument_spec = openstack_full_argument_spec(
        name=dict(required=True),
        size=dict(requires=True, type='int', choices=[100, 250, 500, 1000, 2000, 4000, 8000, 12000]),
        iops_per_gb=dict(requires=True, choices=['2', '4']),
        virtual_storage=dict(required=True),
        availability_zone=dict(required=True),
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
    # Ansible引数の取得
    #
    name = module.params['name']
    size = module.params['size']
    iops_per_gb = module.params['iops_per_gb']
    virtual_storage_name = module.params['virtual_storage']
    availability_zone = module.params['availability_zone']
    state = module.params['state']

    # 待機時間の取得
    #wait = module.params['wait']
    #timeout = module.params['timeout']

    #
    # ECLへの接続
    #
    ecl2 = _get_ecl_connection_from_module(module)
    volume = _find_storage_volume_by_name(ecl2, name)

    #
    # 仮想ストレージの作成
    #
    if state == 'present':
        #
        # 既に仮想ボリュームが存在する場合
        #
        if not volume == None:
            module.exit_json(msg = 'Virtual storage volume(%s) is already exist.' %(virtual_storage_name), changed=False)

        #
        # 仮想ストレージボリュームの作成
        #
        _create_storage_volume(module, ecl2, name, size, iops_per_gb, virtual_storage_name, availability_zone)

        #
        # 正常終了
        #
        module.exit_json(changed=True)
        return True
    #else:
        #
        # 既に仮想ストレージが存在しない場合
        #
        #if volume == None:
        #    module.exit_json(msg = 'Virtual storage volume(%s) is not exist.' %(name), changed=False)

        #
        # 仮想ストレージボリュームの削除
        #
        #_delete_storage_by_name(ecl2, name)

        #
        # 正常終了
        #
        #module.exit_json(changed=True)
        #return True

#
# Entry Point
#
if __name__ == '__main__':
    main()

