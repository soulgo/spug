# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django_redis import get_redis_connection
from libs.ssh import SSH
import threading
import socket
import json


def exec_worker_handler(job):
    job = Job(**json.loads(job))
    threading.Thread(target=job.run).start()


class Job:
    def __init__(self, hostname, port, username, pkey, command, token=None):
        self.ssh = SSH(hostname, port, username, pkey)
        self.key = f'{hostname}:{port}'
        self.command = command
        self.token = token
        self.rds_cli = None

    def _send(self, message, with_expire=False):
        if self.rds_cli is None:
            self.rds_cli = get_redis_connection()
        self.rds_cli.lpush(self.token, json.dumps(message))
        if with_expire:
            self.rds_cli.expire(self.token, 300)

    def send(self, data):
        message = {'key': self.key, 'data': data}
        self._send(message)

    def send_status(self, code):
        message = {'key': self.key, 'status': code}
        self._send(message, True)

    def run(self):
        if not self.token:
            with self.ssh:
                return self.ssh.exec_command(self.command)
        self.send('\x1b[36m### Executing ...\x1b[0m\r')
        code = -1
        try:
            with self.ssh:
                for code, out in self.ssh.exec_command_with_stream(self.command):
                    self.send(out)
        except socket.timeout:
            code = 130
            self.send('\r\n\x1b[31m### Time out\x1b[0m')
        except Exception as e:
            code = 131
            self.send(f'\r\n\x1b[31m### Exception {e}\x1b[0m')
        finally:
            self.send_status(code)