import os
import sys
import copy
import time
import argparse
import telnetlib
import re
import traceback
import pdb
from collections import defaultdict

from autotest.resources.Data import *
from autotest.resources.Data import _Data
from autotest.Tools import *
from autotest.Print import *
from autotest.Log import *
from autotest.Log import _Backup
from autotest.Parsing import _Parsing

#Test Enum
SCRIPT_CONFIG=0
SCRIPT_RUN   =1
SCRIPT_PARSE =2

class _TestType(object):
    def __init__(self, name, test_func, parsing_func):
        self.name         = name
        self.test_func    = test_func
        self.parsing_func = parsing_func

class _Run(object):
    def __init__(self, data):
        self.data          = data

        # current test function table args
        self.config        = dict()
        self.test_func_tlb = dict()
        self.parse_func    = None
        self.cmd_list      = []

        # backup status log
        self.backup        = _Backup()

        # session info
        self.host_key      = ""
        self.host_session  = dict()
        self.nbr1_session  = dict()
        self.nbr2_session  = dict()

    def script_func_format(func):
        def wrapper(self, *args, **kwargs):
            self.cmd_list = []
            func(self, *args, **kwargs)
            self.parse_func("complete", [], index=-1)
        return wrapper

    def script_block_mangager(self, cmd_list, context):
        context_block = []
        st_cmd   = cmd_list.index("#S_{context}".format(context=context))
        ed_cmd   = cmd_list.index("#E_{context}".format(context=context))

        context_block = cmd_list[st_cmd:ed_cmd+1]                # script context block
        cmd_list      = cmd_list[:st_cmd]+cmd_list[ed_cmd+1:]    # cmd_list - context_block

        return cmd_list, context_block

    def script_block_execute(self, script_block_name=str, action="", index=0):
        self.cmd_list, context_block = self.script_block_mangager(self.cmd_list, script_block_name)

        if script_block_name.startswith("CLI"):
            self.parse_func(action, self.host_session.execute(context_block, 'config'), index=index)
        elif script_block_name.startswith("NBR1"):
            self.parse_func(action, self.nbr1_session.execute(context_block, 'config'), index=index)
        elif script_block_name.startswith("NBR2"):
            self.parse_func(action, self.nbr2_session.execute(context_block, 'config'), index=index)
        elif  script_block_name.startswith("SHELL"):
            if any('rtk_user_diag' in line for line in context_block) and self.config['sdk_type'] != 'RTK': return
            if any('bcm.user.proxy' in line for line in context_block) and self.config['sdk_type'] != 'BCM': return
            self.parse_func(action, self.host_session.execute(context_block, 'shell'), index=index)
        else:
            self.parse_func(action, self.host_session.execute(context_block, 'config'), index=index)

    def get_cmd_script(self, filename):
        cmd_list = []
        f = open(filename, 'r')
        for cmd in f.read().splitlines():
            cmd_list.append(cmd)
        f.close()
        return cmd_list

    def set_cmd_arg(self, cmd_list, config):
        new_cmd_list = []
        for line in cmd_list:
            for key, val in config.items():
                if line.find("{"+key+"}") != -1:
                    line = line.replace("{"+key+"}", val)
            new_cmd_list.append(line)

        return new_cmd_list 

    def update_console_extension_time(self):
        ext_time = "#update"
        self.host_session.execute(ext_time, "terminal")
        self.nbr1_session.execute(ext_time, "terminal")
        self.nbr2_session.execute(ext_time, "terminal")

    def initial_set(self, host_key, session, term=1):
        cmd_list      = []
        context_block = []
        config        = self.data.host_info[host_key]
        script        = "autotest/resources/script/plos-init"
        ret           = 0

        cmd_list = self.set_cmd_arg(self.get_cmd_script(script), config)

        # Uplink Shutdown
        if config['uplink_port'] == 'none':
            cmd_list, context_block = self.script_block_mangager(cmd_list, "UPLINK_PORT_SHUT")
            session.execute(cmd_list, 'config')

        cmd_list, context_block = self.script_block_mangager(cmd_list, "CLI_SHOW_SYSTEM")
        session.execute(cmd_list, 'config')

        if term: session.connection_terminate(session)

        return ret

    def plos_update(self, host_key, session, term=1):
        cmd_list      = []
        context_block = []
        config        = self.data.host_info[host_key]
        script        = "autotest/resources/script/plos-update"
        ret           = 0

        cmd_list = self.set_cmd_arg(self.get_cmd_script(script), config)
        cmd_list, context_block = self.script_block_mangager(cmd_list, "UPDATE_SET")

        ret = self._plos_update_check_process(session.execute(context_block, 'config'))

        cmd_list, context_block = self.script_block_mangager(cmd_list, "UPDATE_CLEAR")
        session.execute(context_block, 'config')

        if term: session.connection_terminate(session)

        return ret

    def _plos_update_check_process(self, log):
        ret = 0
        for line in log:
            if line.find("Error:") != -1 or line.find("Aborted.") != -1: ret = -1

        return ret

    def get_devinfo_data(self, host_key, nbr1_key, nbr2_key, host_session, nbr1_session, nbr2_session):
        parse_func = _Parsing(self.data, self.data.host_info[host_key], self.backup, host_key)
        parse_func = _Parsing(self.data, self.data.host_info[nbr1_key], self.backup, nbr1_key)
        parse_func = _Parsing(self.data, self.data.host_info[nbr2_key], self.backup, nbr2_key)

        _host = parse_func.get_devinfo_data('HOST', host_session.execute(["show system"], "terminal"))
        _nbr1 = parse_func.get_devinfo_data('NBR1', nbr1_session.execute(["show system"], "terminal"))
        _nbr2 = parse_func.get_devinfo_data('NBR2', nbr2_session.execute(["show system"], "terminal"))

        self.data.host_info[host_key].update(_host)
        self.data.host_info[host_key].update(_nbr1)
        self.data.host_info[host_key].update(_nbr2)

    @script_func_format
    def port_mapping_test(self):
        script = "autotest/resources/script/port_mapping_test"

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_INIT")

        for port_num in range(1, int(self.config['port_max'])):
            if port_num <= int(self.config.get('1g_max_port', 0)):
                self.config['v_cli_port'] = f"ge{port_num}"
            else:
                self.config['v_cli_port'] = f"xg{port_num - int(self.config.get('1g_max_port', 0))}"
            self.config['v_sdk_port'] = self.config[self.config['v_cli_port']]

            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_SHUTDOWN", action="shutdown", index=port_num)
            self.script_block_execute("SHELL_SHUTDOWN", action="shutdown", index=port_num)
            self.script_block_execute("CLI_NO_SHUTDOWN", action="no-shutdown", index=port_num)
            self.script_block_execute("SHELL_NO_SHUTDOWN", action="no-shutdown", index=port_num)

        self.script_block_execute("CLI_RECOVERY")

    @script_func_format
    def port_shutdown_test(self):
        script = "autotest/resources/script/port_shuwdown_test"
        for port_num in range(1,4):
            self.config["v_cli_port"] = self.config[f"dev_port{port_num}"]
            self.config["v_sdk_port"] = self.config[f"sdk_port{port_num}"]
            if int(self.host_key[4:]) == self.data.max_host:
                self.config["v_nbr_port"] = self.config[f"(nbr1)dev_port{port_num}"]
            else:
                self.config["v_nbr_port"] = self.config[f"(nbr1)nbr_port{port_num}"]

            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_SHUTDOWN", action="shutdown", index=port_num)
            self.script_block_execute("SHELL_SHUTDOWN", action="shutdown", index=port_num)
            self.script_block_execute("NBR1_SHUTDOWN", action="shutdown", index=port_num)
            self.script_block_execute("CLI_NO_SHUTDOWN", action="no-shutdown", index=port_num)
            self.script_block_execute("SHELL_NO_SHUTDOWN", action="no-shutdown", index=port_num)
            self.script_block_execute("NBR1_NO_SHUTDOWN", action="no-shutdown", index=port_num)

        self.script_block_execute("CLI_RECOVERY")

    @script_func_format
    def port_speed_test(self):
        script = "autotest/resources/script/port_speed_test"
        phyinf = "default" # BCM or RTL8218D or SERDES
        for port_num in [1, 3]:
            self.config["v_cli_port"] = self.config[f"dev_port{port_num}"]
            self.config["v_sdk_port"] = self.config[f"sdk_port{port_num}"]
            if int(self.host_key[4:]) == self.data.max_host:
                self.config["v_nbr_port"] = self.config[f"(nbr1)dev_port{port_num}"]
            else:
                self.config["v_nbr_port"] = self.config[f"(nbr1)nbr_port{port_num}"]
            host_speed_list = []
            nbr_speed_list  = []

            if self.config["v_cli_port"].startswith("ge"):
                if int(self.config.get("1g_max_port", 0)) > 0:
                    phyinf = self.config.get("1g_phy", "default")
                    host_speed_list = ["10", "100", "1000", "AUTO"]
                elif int(self.config.get("2_5g_max_port", 0)) > 0:
                    phyinf = self.config.get("2_5g_phy", "default")
                    host_speed_list = ["10", "100", "AUTO"]
                elif int(self.config.get("5g_max_port", 0)) > 0:
                    phyinf = self.config.get("5g_phy", "default")
                    host_speed_list = ["10", "AUTO"]
            elif self.config["v_cli_port"].startswith("xg"):
                if int(self.config.get("10g_max_port", 0)) > 0:
                    phyinf = self.config.get("10g_phy", "default")
                    if phyinf == "RTL8261BE":
                        host_speed_list = ["100", "AUTO"]
                    else:
                        host_speed_list = ["1000", "10000", "AUTO"]

            if self.config["v_nbr_port"].startswith("ge"):
                if int(self.config.get("(nbr1)1g_max_port", 0)) > 0:
                    phyinf = self.config.get("(nbr1)1g_phy", "default")
                    nbr_speed_list = ["10", "100", "1000", "AUTO"]
                elif int(self.config.get("(nbr1)2_5g_max_port", 0)) > 0:
                    phyinf = self.config.get("(nbr1)2_5g_phy", "default")
                    nbr_speed_list = ["10", "100", "AUTO"]
                elif int(self.config.get("(nbr1)5g_max_port", 0)) > 0:
                    phyinf = self.config.get("(nbr1)5g_phy", "default")
                    nbr_speed_list = ["10", "AUTO"]
            elif self.config["v_nbr_port"].startswith("xg"):
                if int(self.config.get("(nbr1)10g_max_port", 0)) > 0:
                    phyinf = self.config.get("(nbr1)10g_phy", "default")
                    if phyinf == "RTL8261BE":
                        nbr_speed_list = ["100", "AUTO"]
                    else:
                        nbr_speed_list = ["1000", "10000", "AUTO"]

            for host_speed in host_speed_list:
                self.config["host_speed"] = host_speed
                self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
                self.script_block_execute("HOST_SPEED_SET")

                for nbr_speed in nbr_speed_list:
                    self.config["nbr_speed"]  = nbr_speed
                    self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
                    self.script_block_execute("NBR1_SPEED_SET")
                    self.script_block_execute("CLI_SPEED_SHOW", action="diff-speed", index=port_num)
                    self.script_block_execute("SHELL_SPEED_SHOW", action="diff-speed", index=port_num)
                    self.script_block_execute("NBR1_SPEED_SHOW", action="diff-speed", index=port_num)

    @script_func_format
    def port_duplex_test(self):
        script = "autotest/resources/script/port_duplex_test"
        if self.config["dev_port1"].startswith("xg"): return

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_HALF_DUPLEX_SHOW", action="half-duplex")
        self.script_block_execute("SHELL_HALF_DUPLEX_SHOW", action="half-duplex")
        self.script_block_execute("CLI_FULL_DUPLEX_SHOW", action="full-duplex")
        self.script_block_execute("SHELL_FULL_DUPLEX_SHOW", action="full-duplex")
        self.script_block_execute("CLI_RECOVERY")

    @script_func_format
    def port_mdix_test(self):
        script = "autotest/resources/script/port_mdix_test"
        if self.config["dev_port1"].startswith("xg"): return

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_AUTO_SHOW", action="mdix-auto")
        self.script_block_execute("SHELL_AUTO_SHOW", action="mdix-auto")
        self.script_block_execute("CLI_MDI_SHOW", action="mdix-mdi")
        self.script_block_execute("SHELL_MDI_SHOW", action="mdix-mdi")
        self.script_block_execute("CLI_MDIX_SHOW", action="mdix-mdix")
        self.script_block_execute("SHELL_MDIX_SHOW", action="mdix-mdix")
        self.script_block_execute("CLI_RECOVERY")

    @script_func_format
    def port_flowctrl_test(self):
        script = "autotest/resources/script/port_flowctrl_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_FLOW_SEND_RECEIVE_ON", action="flowctrl-on")
        self.script_block_execute("SHELL_FLOW_SEND_RECEIVE_ON", action="flowctrl-on")
        self.script_block_execute("CLI_FLOW_SEND_RECEIVE_OFF", action="flowctrl-off")
        self.script_block_execute("SHELL_FLOW_SEND_RECEIVE_OFF", action="flowctrl-off")
        self.script_block_execute("CLI_1G_RECOVERY")
        if int(self.config.get('10g_max_port', 0)) > 0:
            self.script_block_execute("CLI_10G_RECOVERY")

    @script_func_format
    def port_stormctrl_test(self):
        script = "autotest/resources/script/port_stormctrl_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_STORM_SET", action="storm-set")
        self.script_block_execute("CLI_STORM_UNSET", action="storm-unset")

    @script_func_format
    def port_eee_test(self):
        script = "autotest/resources/script/port_eee_test"
        if int(self.host_key[4:]) == self.data.max_host:
            self.config["(nbr1)nbr_port1"] = self.config[f"(nbr1)dev_port1"]

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_EEE_SET", action="eee-set")
        self.script_block_execute("NBR1_EEE_SET")
        self.script_block_execute("SHELL_EEE_SET", action="eee-set")
        self.script_block_execute("CLI_EEE_UNSET", action="eee-unset")
        self.script_block_execute("SHELL_EEE_UNSET", action="eee-unset")
        self.script_block_execute("NBR1_RECOVERY")

    @script_func_format
    def port_jumboframe_test(self):
        script = "autotest/resources/script/port_jumboframe_test"
        if self.config["dev_port1"].startswith("xg"): return

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_JUMBOFRAME_SET", action="jumboframe-set")
        self.script_block_execute("SHELL_JUMBOFRAME_SET", action="jumboframe-set")
        self.script_block_execute("CLI_JUMBOFRAME_UNSET", action="jumboframe-unset")
        self.script_block_execute("SHELL_JUMBOFRAME_UNSET", action="jumboframe-unset")

    @script_func_format
    def port_cable_diag_test(self):
        script = "autotest/resources/script/port_cable_diag_test"
        if self.config["dev_port1"].startswith("xg"): return

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("NBR1_SPEED_SET")
        if self.config['sdk_type'] != 'BCM':
            self.script_block_execute("CLI_2PAIR_SHOW", action="2pair-set")
            self.script_block_execute("SHELL_2PAIR_SHOW", action="2pair-set")
        self.script_block_execute("CLI_4PAIR_SHOW", action="4pair-set")
        self.script_block_execute("SHELL_4PAIR_SHOW", action="4pair-set")
        self.script_block_execute("HOST_RECOVERY")

    @script_func_format
    def port_mirroring_test(self):
        script = "autotest/resources/script/port_mirroring_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_MIRRORING_SET_SHOW", action="mirroring-set")
        self.script_block_execute("SHELL_MIRRORING_SET_SHOW", action="mirroring-set")
        self.script_block_execute("CLI_MIRRORING_SET_STATISTIC_SHOW", action="mirroring-set-statistic")
        self.script_block_execute("CLI_MIRRORING_UNSET_SHOW", action="mirroring-unset")
        self.script_block_execute("SHELL_MIRRORING_UNSET_SHOW", action="mirroring-unset")
        self.script_block_execute("CLI_MIRRORING_UNSET_STATISTIC_SHOW", action="mirroring-unset-statistic")

    @script_func_format
    def port_lldp_test(self):
        script = "autotest/resources/script/port_lldp_test"
        if int(self.host_key[4:]) == self.data.max_host:
            self.config["(nbr1)nbr_port1"] = self.config[f"(nbr1)dev_port1"]
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_LLDP_SET", action="lldp-set")
        self.script_block_execute("NBR1_LLDP_SET", action="lldp-set")
        self.script_block_execute("CLI_LLDP_SET_SHOW", action="lldp-set-show")
        self.script_block_execute("NBR1_LLDP_SET_SHOW", action="lldp-set-show")
        self.script_block_execute("CLI_LLDP_UNSET_SHOW", action="lldp-unset-show")
        self.script_block_execute("NBR1_LLDP_UNSET_SHOW", action="lldp-unset-show")

    @script_func_format
    def port_udld_test(self):
        script = "autotest/resources/script/port_udld_test"
        if int(self.host_key[4:]) == self.data.max_host:
            self.config["(nbr1)nbr_port1"] = self.config[f"(nbr1)dev_port1"]
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_UDLD_UPLINK_SHOW", action="udld-uplink")
        self.script_block_execute("NBR1_UDLD_UPLINK_SHOW", action="udld-uplink")
        self.script_block_execute("CLI_UDLD_ADVERTISE_SHOW", action="udld-advertise")
        self.script_block_execute("NBR1_UDLD_ADVERTISE_SHOW", action="udld-advertise")
        self.script_block_execute("CLI_UDLD_UNSET_SHOW", action="udld-unset")
        self.script_block_execute("NBR1_UDLD_UNSET_SHOW", action="udld-unset")

    @script_func_format
    def vlan_test(self):
        script = "autotest/resources/script/vlan_test"
        if int(self.host_key[4:]) == self.data.max_host:
            tmp = self.config['input_port']
            self.config['input_port']  = self.config['output_port']
            self.config['output_port'] = tmp

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_ACCESS_SET", action="access-set")
        self.script_block_execute("SHELL_ACCESS_SET", action="access-set")
        self.script_block_execute("CLI_HYBRID_SET", action="hybrid-set")
        self.script_block_execute("SHELL_HYBRID_SET", action="hybrid-set")
        self.script_block_execute("CLI_TRUNK_SET",  action="trunk-set")
        self.script_block_execute("SHELL_TRUNK_SET",  action="trunk-set")
        self.script_block_execute("CLI_RECOVERY")

    @script_func_format
    def lacp_test(self):
        script = "autotest/resources/script/lacp_test"
        if int(self.host_key[4:]) == self.data.max_host:
            self.config["(nbr1)nbr_port1"] = self.config[f"(nbr1)dev_port1"]
            self.config["(nbr1)nbr_port2"] = self.config[f"(nbr1)dev_port2"]

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("NBR1_LACP_SET")
        self.script_block_execute("CLI_LACP_SET")
        self.script_block_execute("CLI_LACP_SET_SHOW", action="lacp-set-show")
        self.script_block_execute("NBR1_LACP_UNSET")
        self.script_block_execute("CLI_LACP_UNSET")
        self.script_block_execute("CLI_LACP_UNSET_SHOW", action="lacp-unset-show")

    @script_func_format
    def stp_test(self):
        if int(self.host_key[4:]) == (self.data.max_host-1):
            script = "autotest/resources/script/stp_test2"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1"   )
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_ROOT_SHOW"     , action="root-bridge-set2"   )
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1" )
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2" )
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1"     )
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover1"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover2"     )
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")
        elif int(self.host_key[4:]) == self.data.max_host:
            script = "autotest/resources/script/stp_test3"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1"   )
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("NBR1_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set2"   )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1"     )
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover1"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover2"     )
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")
        else:
            script = "autotest/resources/script/stp_test"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1"   )
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("NBR1_STP_BRIDGE_CHANGE_ROOT_SHOW"   , action="root-bridge-set2"   )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1"     )
            self.script_block_execute("CLI_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2"     )
            self.script_block_execute("CLI_STP_FAILOVER_SHOW"              , action="port-failover1"     )
            self.script_block_execute("CLI_STP_FAILOVER_SHOW"              , action="port-failover2"     )
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")

    @script_func_format
    def stp_lacp_test(self):
        if int(self.host_key[4:]) == (self.data.max_host-1):
            script = "autotest/resources/script/stp_lacp_test2"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1"   )
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_ROOT_SHOW"     , action="root-bridge-set2"   , index=1)
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1" )
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2" )
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1"     )
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover1"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover2"     )
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")
        elif int(self.host_key[4:]) == self.data.max_host:
            script = "autotest/resources/script/stp_lacp_test3"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1"   )
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("NBR1_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set2"   , index=1)
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1"     )
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover1"     )
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover2"     )
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")
        else:
            script = "autotest/resources/script/stp_lacp_test"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1"   )
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("NBR1_STP_BRIDGE_CHANGE_ROOT_SHOW"   , action="root-bridge-set2"   , index=1)
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2" )
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1"     )
            self.script_block_execute("CLI_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2"     )
            self.script_block_execute("CLI_STP_FAILOVER_SHOW"              , action="port-failover1"     )
            self.script_block_execute("CLI_STP_FAILOVER_SHOW"              , action="port-failover2"     )
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")

    @script_func_format
    def private_vlan_test(self):
        script = "autotest/resources/script/private_vlan_test"
        if int(self.host_key[4:]) == self.data.max_host:
            tmp = self.config['input_port']
            self.config['input_port']  = self.config['output_port']
            self.config['output_port'] = tmp
            tmp = self.config['(nbr1)input_port']
            self.config['(nbr1)input_port']  = self.config['(nbr1)output_port']
            self.config['(nbr1)output_port'] = tmp

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_PRIVATE_VLAN_SET", action="private-vlan-set")
        self.script_block_execute("SHELL_PRIVATE_VLAN_SET", action="private-vlan-set")
        self.script_block_execute("CLI_PRIMARY_PORT_STATISTIC", action="primary-port-traffic-test")
        self.script_block_execute("NBR1_COMMON1_PORT_SET")
        self.script_block_execute("CLI_COMMON1_PORT_STATISTIC", action="common1-port-traffic-test")
        self.script_block_execute("NBR1_COMMON2_PORT_SET")
        self.script_block_execute("CLI_COMMON2_PORT_STATISTIC", action="common2-port-traffic-test")
        self.script_block_execute("NBR1_ISOLATED_PORT_SET")
        self.script_block_execute("CLI_ISOLATED_PORT_STATISTIC", action="isolated-port-traffic-test")
        self.script_block_execute("NBR1_PRIVATE_VLAN_UNSET")
        self.script_block_execute("CLI_PRIVATE_VLAN_UNSET", action="private-vlan-unset")
        self.script_block_execute("SHELL_PRIVATE_VLAN_UNSET", action="private-vlan-unset")

    @script_func_format
    def voice_vlan_test(self):
        script = "autotest/resources/script/voice_vlan_test"
        if self.config['sdk_type'] == "RTK":
            if self.config['board_type'] == "RTL9300":
                self.config['bit']   = self.config['9300_bit']
            else:
                self.config['bit']   = self.config['9310_bit']

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_VOICE_VLAN_SET", action="voice-vlan-set")
        self.script_block_execute("SHELL_VOICE_VLAN_SET", action="voice-vlan-set")
        self.script_block_execute("CLI_VOICE_VLAN_UNSET", action="voice-vlan-unset")
        self.script_block_execute("SHELL_VOICE_VLAN_UNSET", action="voice-vlan-unset")

    @script_func_format
    def ping_test(self):
        script = "autotest/resources/script/ping_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("NBR1_PING_SET", action="ping-set")
        self.script_block_execute("CLI_PING_SET", action="ping-set")
        self.script_block_execute("SHELL_PING_SET", action="ping-set")
        self.script_block_execute("NBR1_PING_UNSET")
        self.script_block_execute("CLI_PING_UNSET")

    @script_func_format
    def static_route_test(self):
        script = "autotest/resources/script/static_route_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_ROUTE_SET", action="route-set")
        self.script_block_execute("SHELL_ROUTE_SET", action="route-set")
        self.script_block_execute("CLI_ROUTE_UNSET", action="route-unset")
        self.script_block_execute("SHELL_ROUTE_UNSET", action="route-unset")

    @script_func_format
    def igmp_snooping_test(self):
        script = "autotest/resources/script/igmp_snooping_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_IGMP_SNOOPING_SET", action="igmp-snooping-set")
        self.script_block_execute("CLI_IGMP_MAC_SHOW", action="igmp-group-mac-show")
        self.script_block_execute("SHELL_IGMP_MAC_SHOW", action="igmp-group-mac-show")

        # last device except
        if int(self.host_key[4:]) != self.data.max_host:
            self.script_block_execute("NBR1_IGMP_GROUP_MEMBERSHIP_TIMEOUT")
            self.script_block_execute("CLI_IGMP_GROUP_MEMBERSHIP_TIMEOUT", action="igmp-group-timeout")

        self.script_block_execute("NBR1_IGMP_SNOOPING_UNSET")
        self.script_block_execute("CLI_IGMP_SNOOPING_UNSET", action="igmp-snooping-unset")
        self.script_block_execute("SHELL_IGMP_MAC_SHOW", action="igmp-snooping-unset")
        self.script_block_execute("CLI_RECOVERY")
        self.script_block_execute("NBR1_RECOVERY")

    @script_func_format
    def l2_smoke_test(self):
        if int(self.host_key[4:]) == (self.data.max_host-1):
            script = "autotest/resources/script/l2_smoke_test2"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_ROOT_SHOW"     , action="root-bridge-set2", index=1)
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover1")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover2")
            self.script_block_execute("CLI_IGMP_GROUP_SHOW"                 , action="igmp-group-show")
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")
        elif int(self.host_key[4:]) == self.data.max_host:
            script = "autotest/resources/script/l2_smoke_test3"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set2", index=1)
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("NBR2_STP_FAILOVER_SHOW"              , action="port-failover2")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"                , action="igmp-group-show")
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")
        else:
            script = "autotest/resources/script/l2_smoke_test"
            self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
            self.script_block_execute("CLI_STP_SET")
            self.script_block_execute("NBR1_STP_SET")
            self.script_block_execute("NBR2_STP_SET")
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_ROOT_SHOW"    , action="root-bridge-set1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("CLI_STP_BRIDGE_CHANGE_NON_ROOT_SHOW", action="non-root-bridge-set")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_BRIDGE_CHANGE_ROOT_SHOW"   , action="root-bridge-set2", index=1)
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PORT_PRIORITY_CHANGE_SHOW"  , action="port-priority-set2")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("NBR1_STP_PORT_PRIORITY_CHANGE")
            self.script_block_execute("CLI_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("CLI_STP_PATH_COST_CHANGE_SHOW"      , action="port-cost-set2")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("CLI_STP_FAILOVER_SHOW"              , action="port-failover1")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("CLI_STP_FAILOVER_SHOW"              , action="port-failover2")
            self.script_block_execute("NBR1_IGMP_GROUP_SHOW"               , action="igmp-group-show")
            self.script_block_execute("CLI_STP_RECOVERY")
            self.script_block_execute("NBR1_STP_RECOVERY")
            self.script_block_execute("NBR2_STP_RECOVERY")

    @script_func_format
    def mac_table_test(self):
        script = "autotest/resources/script/mac_table_test"
        if int(self.host_key[4:]) == self.data.max_host:
            tmp = self.config['input_port']
            self.config['input_port']  = self.config['output_port']
            self.config['output_port'] = tmp

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_MAC_TABLE_SET", action="mac-table-set")
        self.script_block_execute("SHELL_MAC_TABLE_SET", action="mac-table-set")
        self.script_block_execute("CLI_MAC_TABLE_UNSET")

    @script_func_format
    def mac_addr_limit_test(self):
        script = "autotest/resources/script/mac_addr_limit_test"
        if int(self.host_key[4:]) == self.data.max_host:
            tmp = self.config['input_port']
            self.config['input_port']  = self.config['output_port']
            self.config['in_sdk_port']  = self.config[self.config['output_port']]
            self.config['output_port'] = tmp
            self.config['out_sdk_port'] = self.config[tmp]

        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_MAC_ADDR_LIMIT_SET", action="mac-addr-limit-set")
        self.script_block_execute("SHELL_MAC_ADDR_LIMIT_SET", action="mac-addr-limit-set")
        self.script_block_execute("CLI_MAC_ADDR_LIMIT_UNSET", action="mac-addr-limit-unset")
        self.script_block_execute("SHELL_MAC_ADDR_LIMIT_UNSET", action="mac-addr-limit-unset")
        self.script_block_execute("CLI_MAC_ADDR_LIMIT_UNSET")

    @script_func_format
    def mac_addr_static_test(self):
        script = "autotest/resources/script/mac_addr_static_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_MAC_FORWARD_SET", action="forward-set")
        self.script_block_execute("SHELL_MAC_FORWARD_SET", action="forward-set")
        self.script_block_execute("CLI_MAC_DISCARD_SET", action="discard-set")
        self.script_block_execute("SHELL_MAC_DISCARD_SET", action="discard-set")
        self.script_block_execute("CLI_MAC_STATIC_UNSET", action="static-unset")
        self.script_block_execute("SHELL_MAC_STATIC_UNSET", action="static-unset")

    @script_func_format
    def mac_agging_test(self):
        if int(self.host_key[4:]) == self.data.max_host:
            for side in ['', '(nbr1)']:
                tmp = self.config[f'{side}input_port']
                self.config[f'{side}input_port']  = self.config[f'{side}output_port']
                self.config[f'{side}output_port'] = tmp

        script = "autotest/resources/script/mac_agging_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("NBR1_MAC_AGEING_TIME_SET")
        self.script_block_execute("CLI_MAC_AGEING_TIME_SHOW", action="ageing-time-show")
        self.script_block_execute("CLI_MAC_AGEING_TIME_SET", action="ageing-time-set")
        self.script_block_execute("SHELL_MAC_AGEING_TIME_SET", action="ageing-time-set")
        self.script_block_execute("NBR1_MAC_AGEING_TIME_UNSET")
        self.script_block_execute("CLI_MAC_AGEING_TIME_UNSET", action="ageing-time-unset")
        self.script_block_execute("SHELL_MAC_AGEING_TIME_UNSET", action="ageing-time-unset")

    @script_func_format
    def arp_test(self):
        if int(self.host_key[4:]) == self.data.max_host:
            self.config['ip'] = self.config['last_ip']
            self.config['static_ip']   = self.config['last_static_ip']
            self.config['static_mac']  = self.config['last_static_mac']
            self.config['cstatic_mac']  = self.config['last_cstatic_mac']
            self.config['dynamic_ip']  = self.config['last_dynamic_ip']
            self.config['dynamic_mac'] = self.config['last_dynamic_mac']
            self.config['cdynamic_mac'] = self.config['last_cdynamic_mac']

            for side in ['', '(nbr1)']:
                tmp = self.config[f'{side}input_port']
                self.config[f'{side}input_port']  = self.config[f'{side}output_port']
                self.config[f'{side}output_port'] = tmp

        script = "autotest/resources/script/arp_test"
        self.cmd_list = self.set_cmd_arg(self.get_cmd_script(script), self.config)
        self.script_block_execute("CLI_ARP_DYNAMIC_SHOW", action="arp-dynamic")
        self.script_block_execute("SHELL_ARP_DYNAMIC_SHOW", action="arp-dynamic")
        self.script_block_execute("NBR1_ARP_DYNAMIC_CLEAR_SET")
        self.script_block_execute("CLI_ARP_DYNAMIC_CLEAR_SHOW", action="arp-dynamic-clear")
        self.script_block_execute("SHELL_ARP_DYNAMIC_SHOW", action="arp-dynamic-clear")
        self.script_block_execute("NBR1_ARP_STATIC_SET")
        self.script_block_execute("CLI_ARP_STATIC_SHOW", action="arp-static")
        self.script_block_execute("SHELL_ARP_STATIC_SHOW", action="arp-static")
        self.script_block_execute("NBR1_ARP_STATIC_CLEAR_SET")
        self.script_block_execute("CLI_ARP_STATIC_CLEAR_SHOW", action="arp-static-clear")
        self.script_block_execute("SHELL_ARP_STATIC_SHOW", action="arp-static-clear")
        self.script_block_execute("NBR1_ARP_TIMEOUT_SET")
        self.script_block_execute("CLI_ARP_TIMEOUT_SHOW", action="pre-arp-timeout")
        self.script_block_execute("NBR1_ARP_TIMEOUT_SET")
        self.script_block_execute("CLI_ARP_TIMEOUT_SHOW", action="after-arp-timeout")
        self.script_block_execute("CLI_RECOVERY")
        self.script_block_execute("NBR1_RECOVERY")

    def script_func_init(self, host_key, host_config):
        test_types = [
            #         Testtype              Script_func                Parsing_func
            _TestType("Port-Mapping"      , self.port_mapping_test   , "get_port_mapping_test_data"   ),
            _TestType("Shutdown"          , self.port_shutdown_test  , "get_port_shutdown_test_data"  ),
            _TestType("Speed"             , self.port_speed_test     , "get_port_speed_test_data"     ),
            _TestType("Duplex"            , self.port_duplex_test    , "get_port_duplex_test_data"    ),
            _TestType("Mdix"              , self.port_mdix_test      , "get_port_mdix_test_data"      ),
            _TestType("Flow-control"      , self.port_flowctrl_test  , "get_port_flowctrl_test_data"  ),
            _TestType("Storm-control"     , self.port_stormctrl_test , "get_port_stormctrl_test_data" ),
            _TestType("EEE"               , self.port_eee_test       , "get_port_eee_test_data"       ),
            _TestType("Jumbo-Frame"       , self.port_jumboframe_test, "get_port_jumboframe_test_data"),
            _TestType("Cable-Diagnostics" , self.port_cable_diag_test, "get_port_cable_diag_test_data"),
            _TestType("Mirroring"         , self.port_mirroring_test , "get_port_mirroring_test_data" ),
            _TestType("LLDP"              , self.port_lldp_test      , "get_port_lldp_test_data"      ),
            _TestType("UDLD"              , self.port_udld_test      , "get_port_udld_test_data"      ),
            _TestType("Switch-Mode"       , self.vlan_test           , "get_vlan_test_data"           ),
            _TestType("LACP"              , self.lacp_test           , "get_lacp_test_data"           ),
            _TestType("STP"               , self.stp_test            , "get_stp_test_data"            ),
            _TestType("STP&LACP"          , self.stp_lacp_test       , "get_l2_smoke_test_data"       ),
            _TestType("Private-Vlan"      , self.private_vlan_test   , "get_private_vlan_test_data"   ),
            _TestType("Voice-Vlan"        , self.voice_vlan_test     , "get_voice_vlan_test_data"     ),
            _TestType("Ping"              , self.ping_test           , "get_ping_test_data"           ),
            _TestType("Static-Route"      , self.static_route_test   , "get_static_route_test_data"   ),
            _TestType("IGMP-Snooping"     , self.igmp_snooping_test  , "get_igmp_snooping_test_data"  ),
            _TestType("L2-Smoke"          , self.l2_smoke_test       , "get_l2_smoke_test_data"       ),
            _TestType("MAC-Table"         , self.mac_table_test      , "get_mac_table_test_data"      ),
            _TestType("MAC-Address-Limit" , self.mac_addr_limit_test , "get_mac_addr_limit_test_data" ),
            _TestType("Static-Mac-ADDRESS", self.mac_addr_static_test, "get_static_mac_addr_test_data"),
            _TestType("MAC-Ageing-Time"   , self.mac_agging_test     , "get_mac_agging_test_data"     ),
            _TestType("ARP"               , self.arp_test            , "get_arp_test_data"            ),
            # Add more test types as needed
        ]

        for test_type in test_types:
            config = copy.deepcopy(host_config)
            self.test_func_tlb[test_type.name] = [
                config,
                test_type.test_func,
                getattr(_Parsing(self.data, config, self.backup, host_key, test_type.name), test_type.parsing_func),
            ]

    def run_script(self):

        print("\n#Test Execution#\n")

        try:
            for host_key, nbr1_key, nbr2_key in zip(self.data.hostkey_list, self.data.nbr1key_list, self.data.nbr2key_list):
                host_config = self.data.host_info[host_key]
                nbr1_config = self.data.host_info[nbr1_key]
                nbr2_config = self.data.host_info[nbr2_key]

                # Add neighbor config
                host_config.update({f"(nbr1){k}": v for k, v in nbr1_config.items()})
                host_config.update({f"(nbr2){k}": v for k, v in nbr2_config.items()})
                self.host_key = host_key

                self.host_session = self.data.full_session_list[host_key]
                self.nbr1_session = self.data.full_session_list[nbr1_key]
                self.nbr2_session = self.data.full_session_list[nbr2_key]

                self.host_session.reset_connection()
                self.nbr1_session.reset_connection()
                self.nbr2_session.reset_connection()

                self.get_devinfo_data(host_key, nbr1_key, nbr2_key, self.host_session, self.nbr1_session, self.nbr2_session)
                self.script_func_init(host_key, host_config)

                if self.backup.backup_time_dir_check(host_key, host_config['dev_name']) < 0:
                    self.host_session.connection_terminate(self.host_session)
                    self.nbr1_session.connection_terminate(self.nbr1_session)
                    self.nbr2_session.connection_terminate(self.nbr2_session)
                    continue

                for testtype in self.data.test_list:
                    if testtype in host_config['not_support'].split(','): continue

                    self.update_console_extension_time()

                    self.config = self.test_func_tlb[testtype][SCRIPT_CONFIG]
                    # Add test args
                    if testtype in self.data.cfg['test-args-set']:
                        self.config.update((key, str(val)) for key, val in self.data.cfg['test-args-set'][testtype].items())

                    self.backup.create_dataframe()
                    self.parse_func = self.test_func_tlb[testtype][SCRIPT_PARSE]
                    self.test_func_tlb[testtype][SCRIPT_RUN]()
                    self.backup.save_dataframe(testtype)

                    # stats-logs backup
                    self.backup.backup_statlog_save(host_key, self.config['dev_name'], testtype)

                self.backup.save_xlsx(host_key, host_config['dev_name'])
                self.host_session.connection_terminate(self.host_session)
                self.nbr1_session.connection_terminate(self.nbr1_session)
                self.nbr2_session.connection_terminate(self.nbr2_session)

        except Exception as e:
            print("Error during test execution :  \n", e)
            traceback.print_exc()
            return None

        return 0;

