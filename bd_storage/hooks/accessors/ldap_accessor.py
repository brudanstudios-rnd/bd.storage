import os
import sys
import uuid
import subprocess

from bd_storage.abstract.accessor import Accessor
from bd.secrets import get_secret

from bd_storage.logger import get_logger

this = sys.modules[__name__]
this._log = get_logger(__name__)


class LDAPAccessor(Accessor):

    def __init__(self, root=None):
        self._root = root
        if self._root:
            self._root = root.replace('\\', '/')

    def root(self):
        return self._root

    def resolve(self, uid):
        if not self._root:
            return uid
        return self.join(self._root, uid)

    def read(self, uid):
        filename = self.resolve(uid)
        if not os.path.exists(filename):
            return

        with open(filename, 'rb') as f:
            data = f.read()

        return data

    def write(self, uid, data):
        filename = self.resolve(uid)

        self.make_dir(os.path.dirname(self.resolve(uid)), True)

        tmp_filename = '{}__{}'.format(filename, uuid.uuid4().hex)

        self._execute('install -m 777 /dev/null {}'.format(tmp_filename))

        try:
            with open(tmp_filename, 'wb') as f:
                f.write(data)

            self._execute('chmod 0775 {}'.format(tmp_filename))
            self._execute('mv -f "{}" "{}"'.format(tmp_filename, filename))

        except Exception as e:
            if os.path.exists(tmp_filename):
                self._execute('rm {}'.format(tmp_filename))
            raise

    def is_dir(self, uid):
        return os.path.isdir(self.resolve(uid))

    def is_file(self, uid):
        return os.path.isfile(self.resolve(uid))

    def list(self, uid, relative=True, recursive=True):
        paths = []

        initial_dir = self.resolve(uid).rstrip('/')
        start_index = len(initial_dir)

        for root, dirs, files in os.walk(initial_dir):

            dirname = root
            if relative:
                dirname = root[start_index + 1:]

            paths.extend([self.join(dirname, x) for x in files])
            if not recursive:
                continue

        return paths

    def join(self, *args):
        return os.path.join(*args).replace('\\', '/')

    def make_dir(self, uid, recursive=False):
        self._execute('mkdir {} {}'.format('-p' if recursive else '', self.resolve(uid)))

    def rm(self, uid):
        path = self.resolve(uid)
        if os.path.isdir(path):
            self._execute('rm -r {}'.format(path))
        elif os.path.isfile(path):
            self._execute('rm {}'.format(path))

    def exists(self, uid):
        return os.path.exists(self.resolve(uid))

    def _execute(self, command):
        cmd = 'echo {password} | su {username} -c "{command}"'.format(
            password=get_secret()['LDAP_LOGIN'],
            username=get_secret()['LDAP_PASSWORD'],
            command=command
        )
        p = subprocess.Popen(
            ['/bin/bash', '-c', cmd],
            stderr=subprocess.PIPE
        )
        _, stderr = p.communicate()

        if not p.returncode:
            return

        error_msg = stderr.strip().replace('Password: ', '')
        raise Exception('Unable to execute command: {}\n{}'.format(command, error_msg))


def register(registry):
    registry.add_hook('storage.accessor.init.ldap-accessor', LDAPAccessor)
