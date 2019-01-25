# ecl2.0-ansible-module
  ecl2.0-ansible-moduleは、OpenStackモジュールで利用することが出来ない。
ECL2.0 の ストレージサービスを ECLのAPIを使用する事で、自動化するための
モジュールです。

## インストール方法
```bash
git clone git@inspect3.vt-assistant.com:cotoha-ansible/ecl2.0-ansible-module.git
cd ecl2.0-ansible-module
python install.py
```

## Ansible Playbook
### 仮想ストレージの作成
```yaml
- ecl2_storage:
    cloud: devel
    state: present
    name: '仮想ストレージ名'
    subnet: 'サブネット名'
    ip_addr_pool_start: '割り当て開始IP'
    ip_addr_pool_end: '割り当て終了IP(割り当て開始IP + 29)'
```

### 仮想ストレージの削除
```yaml
- ecl2_storage:
    cloud: devel
    state: absent
    name: '仮想ストレージ'
```

### 仮想ストレージにボリュームの作成
```yaml
- ecl2_storage_volume:
    cloud: devel
    state: present
    iops_per_gb: 2
    name: '仮想ボリューム名'
    size: 100
    virtual_storage: '仮想ストレージ名'
    availability_zone: 'zone1-groupb'
```

### 仮想ストレージにボリュームの削除
```yaml
- ecl2_storage_volume:
    cloud: devel
    state: absent
    name: '仮想ボリューム名'
```

### 実行方法
```bash
ansible-playbook -i localhost, -c local sample.yml -vvv
```

