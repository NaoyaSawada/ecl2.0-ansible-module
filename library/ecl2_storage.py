#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ecl as eclsdk
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.openstack import (
    openstack_full_argument_spec, openstack_cloud_from_module, openstack_module_kwargs)

#
# ストレージサービス: ブロックストレージの作成
#
def main():
    #
    # Open Stack 共通引数取得
    #
    argument_spec = openstack_full_argument_spec()
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
    ecl2 = eclsdk.connection.Connection(**ecl2_args)
    servers = []
    #servers = [server.to_dict() for server in ecl2.compute.servers()]

    #
    # 正常終了
    #
    module.exit_json(msg=servers, changed=False)

#
# Entry Point
#
if __name__ == '__main__':
    main()

