#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os.path
import shutil
import re

def main():
    try:
        import ansible
    except ImportError:
        print('Could not load ansible module')
        sys.exit(1)

    #
    # Ansible Version の 取得
    #
    m = re.match(r'^(\d)\.(\d).*$', ansible.__version__)
    if m is None:
        raise Exception('Cannot parse ansible version')

    major = int(m.group(1))
    minor = int(m.group(2))

    #
    # Ansible の パスを取得
    #
    ansible_path = os.path.dirname(os.path.abspath(os.path.realpath(ansible.__file__)))
    print('Ansible path is %s' % ansible_path)

    #
    # バージョン毎に適切なディレクトリが存在するかを確認
    #
    if (major, minor) == (2, 4):
        module_utils_path = os.path.join(ansible_path, 'module_utils')
    else:
        module_utils_path = os.path.join(ansible_path, 'module_utils', 'cloud', 'ecl2')
    if not os.path.exists(module_utils_path):
        print('Module utils directory (%s) does not exist' % module_utils_path)
        sys.exit(1)
    if not os.path.isdir(module_utils_path):
        print('Module utils path (%s) is not a directory' % module_utils_path)
        sys.exit(1)

    #
    # モジュールのパスをAnsibleのバージョンによって設定する
    #
    if major < 2 or major == 2 and minor <= 2:
        extra_modules_path = os.path.join(ansible_path, 'modules', 'extras', 'cloud')
    else:
        extra_modules_path = os.path.join(ansible_path, 'modules', 'cloud')

    if not os.path.exists(extra_modules_path):
        print('Extra modules directory (%s) does not exist' % extra_modules_path)
        sys.exit(1)
    print('Ansible extras path is %s' % extra_modules_path)

    if not os.path.isdir(extra_modules_path):
        print('Extra modules path (%s) is not a directory' % extra_modules_path)
        sys.exit(1)

    here = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    ansible_modules_sourcedir = os.path.join(here, 'library')

    #
    # インストールするファイルを集める
    #
    ansible_module_files = []
    for filename in os.listdir(ansible_modules_sourcedir):
        if filename.endswith('.py'):
            ansible_module_files.append(filename)

#    # Copy ecl2.py to module_utils
#    if 'ecl2.py' not in ansible_module_files:
#        print('Could not find ecl2 module utils file')
#        sys.exit(1)
#
#    print('Copying ecl2.py to %s' % module_utils_path)
#    shutil.copy(os.path.join(ansible_modules_sourcedir, 'ecl2.py'), os.path.join(module_utils_path, 'ecl2.py'))
#
#    ansible_module_files.remove('ecl2.py')

    #
    # ecl2 用 の ディレクトリ作成
    #
    ecl2_module_dir = os.path.join(extra_modules_path, 'ecl2')
    if not os.path.exists(ecl2_module_dir):
        print('Creating directory %s' % ecl2_module_dir)
        os.mkdir(ecl2_module_dir)

    #
    # モジュール用のファイルコピー
    #
    for file in ansible_module_files:
        print('Copying %s to %s' % (file, ecl2_module_dir))
        source = os.path.join(ansible_modules_sourcedir, file)
        destination = os.path.join(ecl2_module_dir, file)
        if os.path.exists(destination):
            print('Overwriting %s' % destination)
        else:
            print('Copying %s' % destination)
        shutil.copy(source, destination)

if __name__ == '__main__':
    main()

