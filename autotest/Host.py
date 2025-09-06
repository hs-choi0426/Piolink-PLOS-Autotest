import os
import sys
import time
import argparse
import telnetlib
import re
import traceback

from autotest.Log import *

SHUTDOWN_LAST_MSG = 'Shutdown'

class _Host(object):

    def __init__(self, hosts, host_key=None, telnet_factory=telnetlib):
        self.telnet_factory = telnet_factory
        self.telnet         = None
        self.host_prompt    = hosts['dev_prompt']
        self.host_name      = hosts['dev_name']
        self.host_ip        = hosts['dev_con_ip']
        self.host_console   = hosts['dev_console']
        self.host_id        = hosts['#id']
        self.host_passwd    = hosts['#passwd']
        self.host_key       = host_key

    def _connect(self, reboot=None):
        host_id = self.host_id
        host_passwd = self.host_passwd

        if (self.host_console == 'none') or (reboot == True):
            self.telnet.read_until(b'login:', 300)
        else:
            self.telnet.read_until(b'Escape character is', 10)
        time.sleep(2)
        self._execute_cmd(host_id, 'Password: ')
        self._execute_cmd(host_passwd, '> ')
        self._execute_cmd('enable', 'Password: ')
        self._execute_cmd(host_passwd, '# ')
        self._execute_cmd('terminal length 0')

    def execute(self, cmds, config, timeout=30):
        if type(cmds) is not list:
            cmds = [cmds]

        if config == 'config':
            prompt = '# '
            config_exit = True
        elif config == 'shell':
            prompt = '# '
            config_exit = True
        else:	
            prompt = f'{self.host_prompt}# '
            config_exit = False

        try:
            self._execute_cmd('')
            rets = self._execute(cmds, prompt, timeout, config, config_exit)
        except:
            self.reset_connection()
            rets = self._execute(cmds, prompt, timeout, config, config_exit)
        return rets

    def _execute(self, cmds, prompt, timeout, config = '', config_exit=True):
        if config == 'config':
            self._execute_cmd('configure terminal')

        elif config == 'shell':
            self._execute_cmd('at-shell dnflsekqdmfckwdmfrjtdleksmfrmfoTemtdl', prompt='# ')

        rets = []

        cmds
        for cmd in cmds:
            if cmd.startswith("sleep"):
                match = re.match(r"sleep (\d+)", cmd)
                if match:
                    time.sleep(int(match.group(1)))
                    continue

            if config == 'shell':
                if cmd == 'rtk_user_diag':
                    config = 'sdk'
                    prompt = '> '
                else:
                    prompt = '# '

            elif config == 'sdk':
                if cmd == 'exit':
                    config = 'shell'
                    prompt = '# '
                else:
                    prompt = '> '

            rets.extend(self._execute_cmd(cmd, prompt, timeout))
        if config_exit:
            self._execute_cmd('exit')
        return rets



    def _execute_cmd(self, cmd, prompt='# ', timeout=30):
        ret       = []

        try:
            self.telnet.write(cmd.encode('utf-8') + b'\n')
            if (cmd[0:9] == 'os update'):
                ret.extend(self._read_data("Continue? (y/n):".encode('utf-8'), timeout))
                self.telnet.write("y".encode('utf-8') + b'\n')
                current_log(self.host_key, ret)

            if type(prompt) is str and type(timeout) is int:
                ret.extend(self._read_data(prompt.encode('utf-8'), timeout))
                current_log(self.host_key, ret)

        except Exception as e:
            print("fail to console prompt error(Host): %s" % (self.host_console))
            print(traceback.format_exc())
            self.telnet.close()
            ret = None

        return ret

    def _read_data(self, prompt, timeout):
        ret = []
        buf1 = self.telnet.read_until(prompt, timeout).decode('utf-8').splitlines()
        ret.extend(buf1)

        buf2 = self.telnet.read_very_eager().decode('utf-8')
        if buf2:
            if buf2[-1] == '\r':
                ret.extend(buf2.splitlines())
            else:
                buf2 = buf2.splitlines()
                ret[-1] += buf2[0]
                if len(buf2) > 1:
                    ret.extend(buf2[1:])

            buf3 = self.telnet.read_until(prompt, timeout).decode('utf-8')
            if buf3:
                if buf3[-1] == '\r':
                    ret.extend(buf3.splitlines())
                else:
                    buf3 = buf3.splitlines()
                    ret[-1] += buf3[0]
                    if len(buf3) > 1:
                        ret.extend(buf3[1:])

        ret = list(filter(lambda x: x != '', ret))

        return ret

    def reset_connection(self, reboot=None, retry=10):
        try:
            for attempt in range(retry):
                try:
                    if self.host_console == 'none':
                        self.telnet = self.telnet_factory.Telnet(host=self.host_ip, timeout=30)
                    else:
                        self.telnet = self.telnet_factory.Telnet(host=self.host_ip, port=self.host_console, timeout=30)
                    break
                except ConnectionRefusedError as e:
                    print(f"Connection error attempt {attempt+1}/{retry}: {e}")
                    if attempt < retry - 1:
                        time.sleep(1)
                    else:
                        raise

            self._connect(reboot)
        except Exception as e:
            print("fail to connect host ip :%s" % (str(self.host_ip)))
            print(traceback.format_exc())
            return 1

        return 0

    def connection_terminate(self, telnet_host=None):
        try:
            if telnet_host == None:
                print("fail to host connect terminate")
                return 1

            telnet_host.telnet.write(b'exit\n')
            telnet_host.telnet.read_until(b'login: ')
            telnet_host.telnet.close()

        except Exception as e:
            print("fail to host connect terminate error(Host): %s" % (telnet_host.host_console))
            print(traceback.format_exc())
            telnet_host.telnet.close()
            return 1

        return 0

    def reboot(self):
        try:
            self._execute_cmd('')
            self._execute(['reboot'], ': ', 30, 'config', False)
            self._execute(['y'], None, None, False, False)
        except:
            self.reset_connection()
            self._execute(['reboot'], ': ', 30, 'config', False)
            self._execute(['y'], None, None, False, False)

    def shutdown(self):
        try:
            self._execute_cmd('')
            self._execute(['at-shell'], '# ', 30, False, False)
            self._execute(['.q halt'], SHUTDOWN_LAST_MSG, 30, False, False)
        except:
            self.reset_connection()
            self._execute(['at-shell'], '# ', 30, False, False)
            self._execute(['.q halt'], SHUTDOWN_LAST_MSG, 30, False, False)

    def copy_factory_default_startup_config(self):
        # sfu config reset
        reset_cmd = ['copy factory-default startup-config']
        try:
            self._execute_cmd('')
            self._execute(reset_cmd, ': ', 30, True, False)
            self._execute(['y'], None, None, False, False)
        except:
            self.reset_connection()
            self._execute(reset_cmd, ': ', 30, True, False)
            self._execute(['y'], None, None, False, False)


