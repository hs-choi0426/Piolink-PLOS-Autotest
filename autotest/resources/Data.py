import os
import sys
import traceback
import yaml
from collections import defaultdict
from typing import Dict, List
from dataclasses import dataclass, field
from autotest.Log import *
from autotest.Tools import *
from autotest.Print import *
from autotest.Host import _Host

ENV_CONFIG_PATH = "./autotest/resources/env_config.yaml"

@dataclass
class _Data:
    # Config environment
    cfg: dict

    # Session manage
    full_session_list: Dict[str, str] = field(default_factory=dict)
    hostkey_list : List[int] = field(default_factory=list)
    nbr1key_list : List[int] = field(default_factory=list)
    nbr2key_list : List[int] = field(default_factory=list)

    # Host session
    host_info: Dict[str, str] = field(default_factory=dict)         # Host information
    host_list: List[int] = field(default_factory=list)              # host_info list
    test_list: str = None                                           # Test type lsit
    max_host: int = 0                                               # Maximum host num
    max_nbr: int = 0                                                # Maximum host num

    def __init__(self):

        self.full_session_list = dict()
        self.hostkey_list = list()
        self.nbr1key_list = list()
        self.nbr2key_list = list()

        with open(ENV_CONFIG_PATH) as f:
            self.cfg = yaml.safe_load(f)

        self.test_list = self.get_testtype_info(show="n")
        self.host_info = self.get_host_info()
        if self.host_info != None:
            self.host_list = self.host_info.keys()
            self.max_host  = len(self.host_list)
            self.get_session_list_info()
            self.update_host_info()

    def update_host_info(self):
        
        for host_key in self.host_list:
            additem = {}
            host = self.host_info[host_key]

            if host['dev_host'] == "y":
                additem['port_max'] = int(host['1g_max_port'])+int(host['2_5g_max_port'])+int(host['5g_max_port'])+int(host['10g_max_port'])

                # SDK port
                additem['in_sdk_port']  = host[host['input_port']]
                additem['out_sdk_port'] = host[host['output_port']]
                additem['sdk_port1']    = host[host['dev_port1']]
                additem['sdk_port2']    = host[host['dev_port2']]
                additem['sdk_port3']    = host[host['dev_port3']]
                additem['sdk_port4']    = host[host['dev_port4']]
                additem['sdk_port5']    = host[host['nbr_port1']]
                additem['sdk_port6']    = host[host['nbr_port2']]
                additem['sdk_port7']    = host[host['nbr_port3']]
                additem['sdk_port8']    = host[host['nbr_port4']]

            host.update(additem)

    def get_session_list_info(self):
        # HOST session list
        for host_key in reversed(self.host_list):

            session = _Host(self.host_info[host_key], host_key)
            self.full_session_list[host_key] = session

            if self.host_info[host_key]['dev_host'] != "y": continue
            self.hostkey_list.append(host_key)

        # NBR session list
        for host_key in self.hostkey_list:
            if int(host_key[4:]) == self.max_host:
                nbr1_key = ('HOST%s'%(str(self.max_host-1)))
            else:
                nbr1_key = ('HOST%s'%(str(int(host_key[4:])+1)))

            if (self.max_host - int(host_key[4:])) > 1:
                nbr2_key = ('HOST%s'%(str(int(host_key[4:])+2)))
            else:
                nbr2_key = ('HOST%s'%(str(self.max_host-2)))

            self.nbr1key_list.append(nbr1_key)
            self.nbr2key_list.append(nbr2_key)

        self.hostkey_list = reversed(self.hostkey_list)
        self.nbr1key_list = reversed(self.nbr1key_list)
        self.nbr2key_list = reversed(self.nbr2key_list)

    def get_host_info(self):
        Hosts = {}
        std_out, std_err = shell_exe("ls "+CONFIG_DIR+"/ | grep HOST* | egrep -v \'_\'")

        config_list = [line for line in std_out.read().decode('utf-8').splitlines()]

        host_number = 0

        try:
            for config in config_list:
                host_number = host_number + 1
                f = open(CONFIG_DIR + "/" + config ,'r')
                Host = {}

                for config_line in f.read().splitlines():
                    Host[config_line.split(':')[0]] = config_line.split(':')[1]

                    # PROFILE link
                    if (config_line.split(':')[0] == 'dev_type'):
                        Host.update(dict(self.get_profile_info(Host['dev_type'])))

                f.close()
                Hosts[config] = Host
        except Exception as e:
            print("Host info file open error:  \n", e)
            return None

        return Hosts

    def get_profile_info(self, profile):
        std_out, std_err = shell_exe("ls " + PROFILE_DIR)

        dev_profile = ''
        for line in std_out.read().decode('utf-8').splitlines():
            if line == profile:
                dev_profile = profile

        try:
            f = open(PROFILE_DIR + "/" + dev_profile, 'r')
            Profile = {}

            for profile_line in f.read().splitlines():
                Profile[profile_line.split(':')[0]] = profile_line.split(':')[1]

            f.close()
        except Exception as e:
            print("Profile file open error:  \n", e)
            return None

        return Profile

    def get_config_info(self):
        std_out, std_err = shell_exe("ls "+CONFIG_DIR+"/ | grep HOST* | egrep -v \'_\'")

        config_list = [line for line in std_out.read().decode('utf-8').splitlines()]

        try:
            for config in config_list:
                f = open(CONFIG_DIR+"/"+config ,'r')

                print(f"{'='*47}\n={config.center(45)}=\n{'='*47}")
                for config_line in f.read().splitlines():
                    print(config_line)

                f.close()
        except Exception as e:
            print("Config file open error:  \n", e)
            return None

        return 0

    def get_testtype_info(self, show="n"):
        test_list = []

        try:
            if show == "y":
                [print(line) for line in print_testtype_display(self.cfg['testtype'].items())]
            else:
                test_list.extend([key for key, value in self.cfg['testtype'].items() if value == 1])

        except Exception as e:
            print("ENV_TEST_SETTING open error:  \n", e)
            if show == "y":
                return None
            else:
                return []

        return test_list

    def set_testtype_info(self, select_str):
        try:
            numbers = []

            match = re.search(r'\s*([0-9,-]+)', select_str)
            if match:
                range_str = match.group(1)
                for part in range_str.split(','):
                    if '-' in part:
                        start, end = map(int, part.split('-'))
                        numbers.extend(range(start, end + 1))
                    else:
                        numbers.append(int(part))
            else:
                if select_str != 'all': return None

            num = 0
            for key, val in self.cfg['testtype'].items():
                if select_str == 'all':
                    self.cfg['testtype'][key] = 1
                else:
                    if num in numbers:
                        self.cfg['testtype'][key] = 1
                    else:
                        self.cfg['testtype'][key] = 0
                num += 1

            with open(ENV_CONFIG_PATH, 'w') as f:
                yaml.dump(self.cfg, f, sort_keys=False, indent=4)

            with open(ENV_CONFIG_PATH, 'r') as f:
                self.cfg = yaml.safe_load(f)

            self.get_testtype_info(show="y")

        except Exception as e:
            print("ENV_TEST_SETTING write error:  \n", e)
            return None

        return 0

