import os
import sys
import re
import pdb

from collections import defaultdict
from autotest.Log import *
from autotest.Log import _Backup
from autotest.Print import *
from autotest.Print import _Loadbar
from autotest.Tools import *

# Error check
STATUS_FAIL        = 0
STATUS_OK          = 1
STATUS_NOT_SUPPORT = 2
STATUS_UNKNOWN     = 3

# Packet-delay
MIN_DELAY_LIMIT    = 200
AGG_2PORT_PERIOD   = 2

class _Parsing(object):
    def __init__(self, data, config, backup, host_key="", testtype=""):
        # test-info
        self.data          = data
        self.host_key      = host_key
        self.testtype      = testtype
        self.config        = config
        self.config_mode   = ""

        # backup-log object
        self.backup        = backup
        self.cycle         = 0
        self.loadbar       = _Loadbar(host_key, testtype, self.cycle)

    def update_xlsx_log(self, check, log):
        if check == STATUS_OK: 
            result = "Normal"
        elif check == STATUS_FAIL:
            result = "Abnormal"
        elif check == STATUS_NOT_SUPPORT:
            result = "Not Support"
        else:
            result = "Unknown"

        log.append(result)
        self.backup.add_dataframe(log)

    def parsing_func_format(func):
        def wrapper(self, *args, **kwargs):
            action = args[0]
            log    = args[1]

            # backup/test_logs
            self.backup.backup_testlog_save(self.host_key, self.config['dev_name'], log, self.testtype)

            if [line for line in log if "CLI" in line] != []:
                self.config_mode = "CLI"
            elif [line for line in log if "SHELL" in line] != []:
                self.config_mode = "SHELL"
            elif [line for line in log if "NBR1" in line] != []:
                self.config_mode = "NBR1"
            elif [line for line in log if "NBR2" in line] != []:
                self.config_mode = "NBR2"

            if action == "complete":
                self.loadbar.print_loadbar(True)
                return
            else:
                self.loadbar.print_loadbar(False)

            if len(action) > 0:
                func(self, *args, **kwargs)

        return wrapper

    def get_devinfo_data(self, side, logs):
        devinfo = dict()
        if side == "HOST":
            host_product   = get_search_context(SPLIT_TYPE2, "Product Name",     logs, row=2)
            host_model     = get_search_context(SPLIT_TYPE2, "Product Name",     logs, row=4)
            host_serial    = get_search_context(SPLIT_TYPE2, "Serial number",    logs, row=2)
            host_mac       = get_search_context(SPLIT_TYPE2, "Mgmt MAC address", logs, row=3)
            host_mac_colon = mac_addr_formatter('colon', host_mac)
            host_mac_dot   = mac_addr_formatter('dot',   host_mac)

            devinfo.update({'host_product':host_product})
            devinfo.update({'host_model':host_model})
            devinfo.update({'host_serial':host_serial})
            devinfo.update({'host_mac_colon':host_mac_colon})
            devinfo.update({'host_mac_dot':host_mac_dot})

        elif side == "NBR1":
            nbr1_product   = get_search_context(SPLIT_TYPE2, "Product Name",     logs, row=2)
            nbr1_model     = get_search_context(SPLIT_TYPE2, "Product Name",     logs, row=4)
            nbr1_serial    = get_search_context(SPLIT_TYPE2, "Serial number",    logs, row=2)
            nbr1_mac       = get_search_context(SPLIT_TYPE2, "Mgmt MAC address", logs, row=3)
            nbr1_mac_colon = mac_addr_formatter('colon', nbr1_mac)
            nbr1_mac_dot   = mac_addr_formatter('dot',   nbr1_mac)

            devinfo.update({'nbr1_product':nbr1_product})
            devinfo.update({'nbr1_model':nbr1_model})
            devinfo.update({'nbr1_serial':nbr1_serial})
            devinfo.update({'nbr1_mac_colon':nbr1_mac_colon})
            devinfo.update({'nbr1_mac_dot':nbr1_mac_dot})

        elif side == "NBR2":
            nbr2_product   = get_search_context(SPLIT_TYPE2, "Product Name",     logs, row=2)
            nbr2_model     = get_search_context(SPLIT_TYPE2, "Product Name",     logs, row=4)
            nbr2_serial    = get_search_context(SPLIT_TYPE2, "Serial number",    logs, row=2)
            nbr2_mac       = get_search_context(SPLIT_TYPE2, "Mgmt MAC address", logs, row=3)
            nbr2_mac_colon = mac_addr_formatter('colon', nbr2_mac)
            nbr2_mac_dot   = mac_addr_formatter('dot',   nbr2_mac)

            devinfo.update({'nbr2_product':nbr2_product})
            devinfo.update({'nbr2_model':nbr2_model})
            devinfo.update({'nbr2_serial':nbr2_serial})
            devinfo.update({'nbr2_mac_colon':nbr2_mac_colon})
            devinfo.update({'nbr2_mac_dot':nbr2_mac_dot})

        return devinfo

    @parsing_func_format
    def get_port_mapping_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-Mapping test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "shutdown", "no-shutdown").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "shutdown":
            if self.config_mode == "CLI":
                target_port = self.config["v_cli_port"]
                port_state = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=1)
                if port_state == "DIS":
                    check = STATUS_OK

            elif self.config_mode == "SHELL":
                target_port = self.config["v_sdk_port"]
                port_state = get_search_context(SPLIT_TYPE1, "Admin", log, row=1)
                if port_state == "Disable":
                    check = STATUS_OK

            content = "포트 disable 시 포트 비활성화 여부가 반영이 되는가?"
            status  = f"EN={port_state}"

        elif action == "no-shutdown":
            if self.config_mode == "CLI":
                target_port = self.config["v_cli_port"]
                port_state = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=1)
                if port_state == "EN":
                    check = STATUS_OK
                    
            elif self.config_mode == "SHELL":
                target_port = self.config["v_sdk_port"]
                port_state = get_search_context(SPLIT_TYPE1, "Admin", log, row=1)
                if port_state == "Enable":
                    check = STATUS_OK

            content = "포트 enable 시 포트 활성화 여부가 반영이 되는가?"
            status  = f"EN={port_state}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_shutdown_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-shutdown test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "shutdown", "no-shutdown").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "shutdown":
            if self.config_mode == "CLI":
                target_port = self.config["v_cli_port"]
                port_state  = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=1)
                port_status = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=2)
                if (port_state == "DIS") and (port_status == "DOWN"):
                    check = STATUS_OK

                content = f"포트 disable 시 포트가 link-down 되는가?"
                status  = f"EN={port_state}/Link={port_status}"

            elif self.config_mode == "SHELL":
                target_port = self.config["v_sdk_port"]
                port_state = get_search_context(SPLIT_TYPE1, "Admin", log, row=1)
                if port_state == "Disable":
                    check = STATUS_OK

                content = f"포트 disable 시 SDK 포트가 link-down 되는가?"
                status  = f"EN={port_state}"

            elif self.config_mode == "NBR1":
                target_port = self.config["v_nbr_port"]
                port_status = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=2)
                if port_status == "DOWN":
                    check = STATUS_OK

                content = f"포트 disable 시 이웃장비 포트가 link-down이 되는가?"
                status  = f"Link={port_status}"

        elif action == "no-shutdown":
            if self.config_mode == "CLI":
                target_port = self.config["v_cli_port"]
                port_state  = get_search_context(SPLIT_TYPE1, f"{target_port} |", log, row=1)
                port_status = get_search_context(SPLIT_TYPE1, f"{target_port} |", log, row=2)
                if (port_state == "EN") and (port_status == "UP"):
                    check = STATUS_OK

                content = f"포트 enable 시 포트가 link-up 되는가?"
                status  = f"EN={port_state}/Link={port_status}"

            elif self.config_mode == "SHELL":
                target_port = self.config["v_sdk_port"]
                port_state = get_search_context(SPLIT_TYPE1, "Admin", log, row=1)
                if port_state == "Enable":
                    check = STATUS_OK

                content = f"포트 enable 시 포트가 link-up 되는가?"
                status  = f"EN={port_state}"

            elif self.config_mode == "NBR1":
                target_port = self.config["v_nbr_port"]
                port_status = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=2)
                if port_status == "UP":
                    check = STATUS_OK

                content = f"포트 enable 시 이웃장비  포트가 link-up이 되는가?"
                status  = f"Link={port_status}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_speed_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-speed test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "diff-speed").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        host_speed  = self.config['host_speed']
        nbr_speed   = self.config['nbr_speed']

        if self.config_mode == "CLI":
            target_port = self.config["v_cli_port"]

            port_speed  = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=3)
            port_status = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=2)
            if host_speed == "AUTO":
                if port_speed == "AUTO":
                    if port_status == "UP":
                        if nbr_speed != "10000": check = STATUS_OK
                    elif port_status == "DOWN":
                        if target_port.startswith("xg") and nbr_speed == "10": check = STATUS_OK
                        elif nbr_speed == "10000": check = STATUS_OK
            else:
                if port_speed == "FORC":
                    if port_status == "UP":
                        if (host_speed == nbr_speed) or (nbr_speed == "AUTO"):
                            check = STATUS_OK
                        if self.config['sdk_type'] == 'BCM':
                            if host_speed == "10" and nbr_speed == "100":
                                return
                    if port_status == "DOWN":
                        if host_speed != nbr_speed: check = STATUS_OK
                        elif (nbr_speed == "AUTO") and (self.config["v_nbr_port"].startswith("xg")) and host_speed == "10": check = STATUS_OK

            content = f"장비 포트 speed({host_speed}) 변경 시 link-up/down 상태가 맞는가?"
            status  = f"{host_speed}/{nbr_speed}={port_status}"

        elif self.config_mode == "SHELL":
            target_port = self.config["v_sdk_port"]
            if self.config["v_cli_port"].startswith("xg"):
                if self.config["10g_phy"] == "default": return

            autonego_state = get_search_context(SPLIT_TYPE1, 'AutoNego', log, row=1)
            port_status    = get_search_context(SPLIT_TYPE2, 'Link',     log, row=1)
            if autonego_state == "Enable":
                if port_status == "UP":
                    if nbr_speed != "10000": check = STATUS_OK
                elif port_status == "DOWN":
                    if self.config["v_cli_port"].startswith("xg") and nbr_speed == "10": check = STATUS_OK
                    elif nbr_speed == "10000": check = STATUS_OK
            elif autonego_state == "Disable":
                if port_status == "UP":
                    if (host_speed == nbr_speed) or (nbr_speed == "AUTO"): check = STATUS_OK
                elif port_status == "DOWN":
                    if host_speed != nbr_speed: check = STATUS_OK
                    elif (nbr_speed == "AUTO") and (self.config["v_nbr_port"].startswith("xg")) and host_speed == "10": check = STATUS_OK

            content = f"장비 포트 speed({host_speed}) 변경 시 link-up/down 상태가 맞는가?"
            status  = f"{host_speed}/{nbr_speed}={port_status}"

        elif self.config_mode == "NBR1":
            target_port = self.config["v_nbr_port"]

            port_speed  = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=3)
            port_status = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=2)
            if nbr_speed == "AUTO":
                if port_speed == "AUTO":
                    if port_status == "UP":
                        if host_speed != "10000": check = STATUS_OK
                    elif port_status == "DOWN":
                        if target_port.startswith("xg") and host_speed == "10": check = STATUS_OK
                        elif host_speed == "10000": check = STATUS_OK
            else:
                if port_speed == "FORC":
                    if port_status == "UP":
                        if (host_speed == nbr_speed) or (host_speed == "AUTO"):
                            check = STATUS_OK
                        if self.config['sdk_type'] == 'BCM':
                            if host_speed == "10" and nbr_speed == "100":
                                return
                    if port_status == "DOWN":
                        if host_speed != nbr_speed: check = STATUS_OK
                        elif (host_speed == "AUTO") and (self.config["v_cli_port"].startswith("xg")) and nbr_speed == "10": check = STATUS_OK

            content = f"이웃 장비 포트의 speed({nbr_speed}) 변경 시 link-up/down 상태가 맞는가?"
            status  = f"{host_speed}/{nbr_speed}={port_status}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_duplex_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-duplex test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "half-duplex", "full-duplex").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "half-duplex":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                duplex = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=5)
                if duplex == "HALF":
                    check = STATUS_OK

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                duplex = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2} :", log, cols=1, row=1)
                if duplex == "100H":
                    check = STATUS_OK

            content = f"포트 half-duplex 설정이  반영이 되는가?"

        elif action == "full-duplex":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                duplex = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=5)
                if duplex == "FULL":
                    check = STATUS_OK

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                duplex = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2} :", log, cols=1, row=1)
                if duplex == "100F":
                    check = STATUS_OK

            content = f"포트 full-duplex 설정이  반영이 되는가?"

        status  = f"Duplex={duplex}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_mdix_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-mdix test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "mdix-auto", "mdix-mdi", "mdix-mdix").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "mdix-auto":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                mode = get_search_context(SPLIT_TYPE1, "show mdi-mdix", log, cols=1, row=1)
                if mode == "AUTO":
                    check = STATUS_OK

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                mode = get_search_context(SPLIT_TYPE1, "Cross Over Mode", log, row=1)
                if mode == "Auto MDI/MDIX":
                    check = STATUS_OK

            content = f"포트에 mdi-mdix auto 설정이 반영되는가?"
            status  = f"Mode={mode}"

        elif action == "mdix-mdi":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                mode = get_search_context(SPLIT_TYPE1, "show mdi-mdix", log, cols=1, row=1)
                if mode == "MDI":
                    check = STATUS_OK

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                mode = get_search_context(SPLIT_TYPE1, "Cross Over Mode", log, row=1)
                if mode == "Force MDI":
                    check = STATUS_OK

            content = f"포트에 mdi-mdix mdi 설정이 반영되는가?"
            status  = f"Mode={mode}"

        elif action == "mdix-mdix":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                mode = get_search_context(SPLIT_TYPE1, "show mdi-mdix", log, cols=1, row=1)
                if mode == "MDIX":
                    check = STATUS_OK

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                mode = get_search_context(SPLIT_TYPE1, "Cross Over Mode", log, row=1)
                if mode == "Force MDIX":
                    check = STATUS_OK

            content = f"포트에 mdi-mdix mdix 설정이 반영되는가?"
            status  = f"Mode={mode}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_flowctrl_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-flowctrl test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "flowctrl-on", "flowctrl-off").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "flowctrl-on":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                flowctrl_send = get_search_context(SPLIT_TYPE1, "show flowcontrol", log, cols=1, row=1)
                flowctrl_rcv  = get_search_context(SPLIT_TYPE1, "show flowcontrol", log, cols=1, row=2)
                if flowctrl_send == flowctrl_rcv == "on":
                    check = STATUS_OK

                status  = f"Send={flowctrl_send}, Recv={flowctrl_rcv}"

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                tx_pause = get_search_context(SPLIT_TYPE1, "TX Pause", log, row=1)
                rx_pause = get_search_context(SPLIT_TYPE1, "RX Pause", log, row=1)
                if tx_pause == rx_pause == "Enable":
                    check = STATUS_OK

                status  = f"Send={tx_pause}, Recv={rx_pause}"

            content = f"포트 flowcontrol send | receive on 설정이 반영되어 있는가?"

        elif action == "flowctrl-off":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                flowctrl_send = get_search_context(SPLIT_TYPE1, "show flowcontrol", log, cols=1, row=1)
                flowctrl_rcv  = get_search_context(SPLIT_TYPE1, "show flowcontrol", log, cols=1, row=2)
                if flowctrl_send == flowctrl_rcv == "off":
                    check = STATUS_OK

                status  = f"Send={flowctrl_send}, Recv={flowctrl_rcv}"

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                tx_pause = get_search_context(SPLIT_TYPE1, "TX Pause", log, row=1)
                rx_pause = get_search_context(SPLIT_TYPE1, "RX Pause", log, row=1)
                if tx_pause == rx_pause == "Disable":
                    check = STATUS_OK

                status  = f"Send={tx_pause}, Recv={rx_pause}"

            content = f"포트 flowcontrol send | receive off 설정이 반영되어 있는가?"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_stormctrl_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-stormctrl test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "storm-set", "storm-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "storm-set":
            if self.config_mode == "CLI":
                target_port = self.config["input_port"]
                stormctrl_bcast = get_search_context(SPLIT_TYPE2, "Storm-Control Status Table", log, cols=4, row=1)
                stormctrl_mcast = get_search_context(SPLIT_TYPE2, "Storm-Control Status Table", log, cols=4, row=2)
                stormctrl_dlf   = get_search_context(SPLIT_TYPE2, "Storm-Control Status Table", log, cols=4, row=3)
                if stormctrl_bcast == stormctrl_mcast == stormctrl_dlf == "100":
                    port_state  = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=1)
                    port_status = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=2)
                    if (port_state == "DIS") and (port_status == "DOWN"):
                        check = STATUS_OK

            content = "storm-control bcast,mcast,dlf 100 설정 후 포트가 shutdown 되었는가?"

        elif action == "storm-unset":
            if self.config_mode == "CLI":
                target_port = self.config["input_port"]
                stormctrl_bcast = get_search_context(SPLIT_TYPE2, "Storm-Control Status Table", log, cols=4, row=1)
                stormctrl_mcast = get_search_context(SPLIT_TYPE2, "Storm-Control Status Table", log, cols=4, row=2)
                stormctrl_dlf   = get_search_context(SPLIT_TYPE2, "Storm-Control Status Table", log, cols=4, row=3)
                if stormctrl_bcast == stormctrl_mcast == stormctrl_dlf == "Disable":
                    port_state  = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=1)
                    port_status = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=2)
                    if (port_state == "EN") and (port_status == "UP"):
                        check = STATUS_OK

            content = "storm-control 설정 해제 후 10초 뒤에 포트가 no shutdown 되었는가?"

        status  = f"Bcast={stormctrl_bcast}/Mcast={stormctrl_mcast}/Ucast={stormctrl_dlf}\nEN={port_state},Link={port_status}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_eee_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-EEE test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "eee-set", "eee-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "eee-set":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                eee_state   = get_search_context(SPLIT_TYPE1, "show eee", log, cols=1, row=1)
                if eee_state == "EN":
                    check = STATUS_OK

                content = "포트 eee설정이 enable 되었는가?"
                status  = f"EEE={eee_state}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                eee_state   = get_search_context(SPLIT_TYPE2, f"Port {target_port} EEE", log, cols=1, row=1) # Host eee port enable
                eee_status  = get_search_context(SPLIT_TYPE2, f"Port {target_port} EEE", log, cols=1, row=3) # link up Neighbor enable eee port
                if eee_state == eee_status == "enable":
                    check = STATUS_OK

                content = "포트 eee설정이 enable 되었는가?\n상대 장비 포트도 enable되었는가?"
                status  = f"EEE={eee_state}, Status={eee_status}"

        elif action == "eee-unset":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                eee_state   = get_search_context(SPLIT_TYPE1, "show eee", log, cols=1, row=1)
                if eee_state == "DIS":
                    check = STATUS_OK

                content = "포트 eee설정이 disable 되었는가?"
                status  = f"EEE={eee_state}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                eee_state   = get_search_context(SPLIT_TYPE2, f"Port {target_port} EEE", log, cols=1, row=1) # Host eee port disable
                eee_status  = get_search_context(SPLIT_TYPE2, f"Port {target_port} EEE", log, cols=1, row=3) # link up Neighbor disable eee port
                if eee_state == eee_status == "disable":
                    check = STATUS_OK

                content = "포트 eee설정이 disable 되었는가?\n상대 장비 포트도 disable되었는가?"
                status  = f"EEE={eee_state}, Status={eee_status}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_jumboframe_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-Jumboframe test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "jumboframe-set", "jumboframe-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "jumboframe-set":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                jumboframe_state = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=6)
                if jumboframe_state == "EN":
                    check = STATUS_OK

                content = "포트 jumbo-frame설정 상태가 on인가?"
                status  = f"State={jumboframe_state}"

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                jumboframe_maxpkt = get_search_context(SPLIT_TYPE1, "Max Packet Length", log, cols=1, row=1)
                if jumboframe_maxpkt == "12288":
                    check = STATUS_OK

                content = "포트 최대 패킷 길이 설정이 12288인가?"
                status  = f"Max-pkt={jumboframe_maxpkt}"

        elif action == "jumboframe-unset":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                jumboframe_state = get_search_context(SPLIT_TYPE1, "show portstatus", log, cols=1, row=6)
                if jumboframe_state == "DIS":
                    check = STATUS_OK

                content = "포트 jumbo-frame설정 상태가 off인가?"
                status  = f"State={jumboframe_state}"

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                jumboframe_maxpkt = get_search_context(SPLIT_TYPE1, "Max Packet Length", log, cols=1, row=1)
                if jumboframe_maxpkt == "1518":
                    check = STATUS_OK

                content = "포트 최대 패킷 길이 설정이 1518인가?"
                status  = f"Max-pkt={jumboframe_maxpkt}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_cable_diag_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-Cable-Diag test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "2pair-set", "4pair-set").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "2pair-set":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                port_state  = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=5, row=1)
                Apair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=6, row=1)
                Bpair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=7, row=1)
                Cpair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=8, row=1)
                Dpair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=9, row=1)
                if (port_state == "OPEN" and Apair_state == Bpair_state == "OK" and Cpair_state == Dpair_state == "OPEN"):
                    check = STATUS_OK

                content = "포트 2pair 케이블 상태가 어떻게 보여지나?"
                status  = f"State={port_state}\nApair=({Apair_state}), Bpair=({Bpair_state}), Cpair=({Cpair_state}), Dpair=({Dpair_state})"

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                porttype = re.search(r'\(([^)]+)\)', log[5]).group(1)
                if porttype == "type FE":
                    rx_chan_state = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2}", log, cols=2, row=1)
                    tx_chan_state = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2}", log, cols=5, row=1)
                    if rx_chan_state == tx_chan_state == "[Normal]":
                        check = STATUS_OK

                content = "포트 2pair 케이블 상태가 어떻게 보여지나?"
                status  = f"Rx={rx_chan_state}, Tx={tx_chan_state}"

        elif action == "4pair-set":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                port_state  = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=5, row=1)
                Apair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=6, row=1)
                Bpair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=7, row=1)
                Cpair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=8, row=1)
                Dpair_state = get_search_context(SPLIT_TYPE1, 'show cable-diagnostic', log, cols=9, row=1)
                if port_state == Apair_state == Bpair_state == Cpair_state == Dpair_state == "OK":
                    check = STATUS_OK

                content = "포트 4pair 케이블 상태가 어떻게 보여지나?"
                status  = f"State={port_state}\nApair=({Apair_state}), Bpair=({Bpair_state}), Cpair=({Cpair_state}), Dpair=({Dpair_state})"

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]
                porttype = re.search(r'\(([^)]+)\)', log[5]).group(1)
                if porttype == "type GE":
                    Achannel_state = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2}", log, cols=2,  row=1)
                    Bchannel_state = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2}", log, cols=5,  row=1)
                    Cchannel_state = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2}", log, cols=8,  row=1)
                    Dchannel_state = get_search_context(SPLIT_TYPE1, f"Port {target_port:>2}", log, cols=11, row=1)
                    if Achannel_state == Bchannel_state == Cchannel_state == Dchannel_state == "[Normal]":
                        check = STATUS_OK

                content = "포트 4pair 케이블 상태가 어떻게 보여지나?"
                status  = f"Apair={Achannel_state}, Bpair={Bchannel_state}, Cpair={Cchannel_state}, Dpair={Dchannel_state}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_mirroring_test_data(self, action=str, log=list, index=0):
        """
        Parse Port-Mirroring test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "mirroring-set", "mirroring-unset", "mirroring-set-statistic", "mirroring-unset-statistic").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "mirroring-set":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                monitor_port  = get_search_context(SPLIT_TYPE1, "Monitor Port",  log, row=1)
                mirrored_port = get_search_context(SPLIT_TYPE2, "Mirrored Port", log, row=2)
                if ((monitor_port == self.config['dev_port1'])
                    and (mirrored_port == self.config['input_port'])):
                    check = STATUS_OK

                content = "포트 미러링이 정상적으로 설정되었는가?"
                status  = f"Monitoring={monitor_port}, Mirrored={mirrored_port}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                mirror_type  = get_search_context(SPLIT_TYPE1, "Mirror Type",            log, row=1)
                monitor_port = get_search_context(SPLIT_TYPE1, "Port ID",                log, row=1)
                ingress_port = get_search_context(SPLIT_TYPE1, "Mirroring Ingress Port", log, row=1)
                if (mirror_type == "Port-Based Mirror"
                    and (monitor_port == self.config['sdk_port1'])
                    and (ingress_port == self.config[self.config['input_port']])):
                    check = STATUS_OK

                content = "포트 미러링이 정상적으로 설정되었는가?"
                status  = f"Monitoring={monitor_port} Ingress-port={ingress_port}"

        elif action == "mirroring-unset":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                monitor_port  = get_search_context(SPLIT_TYPE1, "Monitor Port",  log, row=1)
                if monitor_port == "": monitor_port = "Not setting"
                mirrored_port = get_search_context(SPLIT_TYPE2, "Mirrored Port", log, row=2)
                if mirrored_port == "": mirrored_port = "Not setting"
                if monitor_port == "Not setting" and mirrored_port == "Not setting":
                    check = STATUS_OK

                content = "포트 미러링이 정상적으로 해제되었는가?"
                status  = f"Monitoring={monitor_port}, Mirrored={mirrored_port}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                mirror_type  = get_search_context(SPLIT_TYPE1, "Mirror Type",            log, row=1)
                monitor_port = get_search_context(SPLIT_TYPE1, "Port ID",                log, row=1)
                ingress_port = get_search_context(SPLIT_TYPE1, "Mirroring Ingress Port", log, row=1)
                if ingress_port == "": ingress_port = "Not setting"
                if mirror_type == "Disable" and (int(monitor_port) == 0) and (ingress_port == 'Not setting'):
                    check = STATUS_OK

                content = "포트 미러링이 정상적으로 해제되었는가?"
                status  = f"Monitoring={monitor_port} Ingress-port={ingress_port}"

        elif action == "mirroring-set-statistic":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                monitor_port_stat  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} ",  log, row=3))
                mirrored_port_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=1))
                if (monitor_port_stat > 0 and mirrored_port_stat > 0 and abs(monitor_port_stat - mirrored_port_stat) < MIN_DELAY_LIMIT):
                    check = STATUS_OK

                content = "미러링한 포트의 트래픽이 정상적으로 감지되는가?"
                status  = f"Monitor-txpps={monitor_port_stat}, Mirrored-rxpps={mirrored_port_stat}"

        elif action == "mirroring-unset-statistic":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                rx_monitor_port = int(get_search_context(SPLIT_TYPE1, "port-monitoring", log, cols=1, row=1))
                tx_monitor_port = int(get_search_context(SPLIT_TYPE1, "port-monitoring", log, cols=1, row=3))
                if rx_monitor_port == tx_monitor_port == 0:
                    check = STATUS_OK

                content = "미러링한 포트의 트래픽이 0으로 감지되는가?"
                status  = f"Monitor-txpps={tx_monitor_port}, Mirrored-rxpps={rx_monitor_port}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_lldp_test_data(self, action=str, log=list, index=0):
        """
        Parse LLDP test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "lldp-set", "lldp-set-show", "lldp-unset-show").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "lldp-set":
            target_port = self.config["dev_port1"]

            set_lldp = [line for line in log if " set lldp enable txrx" in line]
            if len(set_lldp) > 0: check = STATUS_OK

            content = "포트 인터페이스 LLDP설정이 정상적으로 등록되어 있는가?"
            status  = f"interface setting={str(bool(check))}"

        elif action == "lldp-set-show":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                 
                mac  = ":".join([format(int(line, 16), '02x') for line in [line.strip() for line in get_search_context(SPLIT_TYPE1, "Chassis MAC", log, row=1).split()]])
                port = get_search_context(SPLIT_TYPE1, "Interface Name", log, row=1)
                if (mac == self.config['nbr1_mac_colon']) and (port == self.config['(nbr1)nbr_port1']):
                    check = STATUS_OK

            elif self.config_mode == "NBR1":
                target_port = self.config["(nbr1)nbr_port1"]
                mac  = ":".join([format(int(line, 16), '02x') for line in [line.strip() for line in get_search_context(SPLIT_TYPE1, "Chassis MAC", log, row=1).split()]])
                port = get_search_context(SPLIT_TYPE1, "Interface Name", log, row=1)
                if (mac == self.config['host_mac_colon']) and (port == self.config['dev_port1']):
                    check = STATUS_OK

            content = "이웃 장비의 LLDP정보를 정상적으로 받았는가?"
            status  = f"Neighbot port={port}\nNeighbor mac={mac}"

        elif action == "lldp-unset-show":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                if "Remote LLDP" not in log:
                    set_lldp = [line for line in log if " set lldp enable txrx" in line]
                    if len(set_lldp) == 0: check = STATUS_OK

            elif self.config_mode == "NBR1":
                target_port = self.config["(nbr1)nbr_port1"]
                if "Remote LLDP" not in log:
                    set_lldp = [line for line in log if " set lldp enable txrx" in line]
                    if len(set_lldp) == 0: check = STATUS_OK

            content = "포트 인터페이스 LLDP설정이 정상적으로 등록해제되어 있는가?"
            status  = f"interface unsetting={str(bool(check))}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_lldp_test_data(self, action=str, log=list, index=0):
        """
        Parse LLDP test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "lldp-set", "lldp-set-show", "lldp-unset-show").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "lldp-set":
            target_port = self.config["dev_port1"]

            set_lldp = [line for line in log if " set lldp enable txrx" in line]
            if len(set_lldp) > 0: check = STATUS_OK

            content = "포트 인터페이스 LLDP설정이 정상적으로 등록되어 있는가?"
            status  = f"interface setting={str(bool(check))}"

        elif action == "lldp-set-show":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                 
                mac  = ":".join([format(int(line, 16), '02x') for line in [line.strip() for line in get_search_context(SPLIT_TYPE1, "Chassis MAC", log, row=1).split()]])
                port = get_search_context(SPLIT_TYPE1, "Interface Name", log, row=1)
                if (mac == self.config['nbr1_mac_colon']) and (port == self.config['(nbr1)nbr_port1']):
                    check = STATUS_OK

            elif self.config_mode == "NBR1":
                target_port = self.config["(nbr1)nbr_port1"]
                mac  = ":".join([format(int(line, 16), '02x') for line in [line.strip() for line in get_search_context(SPLIT_TYPE1, "Chassis MAC", log, row=1).split()]])
                port = get_search_context(SPLIT_TYPE1, "Interface Name", log, row=1)
                if (mac == self.config['host_mac_colon']) and (port == self.config['dev_port1']):
                    check = STATUS_OK

            content = "이웃 장비의 LLDP정보를 정상적으로 받았는가?"
            status  = f"Neighbot port={port}\nNeighbor mac={mac}"

        elif action == "lldp-unset-show":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                if "Remote LLDP" not in log:
                    set_lldp = [line for line in log if " set lldp enable txrx" in line]
                    if len(set_lldp) == 0: check = STATUS_OK

            elif self.config_mode == "NBR1":
                target_port = self.config["(nbr1)nbr_port1"]
                if "Remote LLDP" not in log:
                    set_lldp = [line for line in log if " set lldp enable txrx" in line]
                    if len(set_lldp) == 0: check = STATUS_OK

            content = "포트 인터페이스 LLDP설정이 정상적으로 등록해제되어 있는가?"
            status  = f"interface unsetting={str(bool(check))}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_port_udld_test_data(self, action=str, log=list, index=0):
        """
        Parse UDLD test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "udld-uplink", "udld-advertise", "udld-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "udld-uplink":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                udld_state = get_search_context(SPLIT_TYPE1, "Port administrative", log, row=1)
                if udld_state == "Enable":
                    port_state = get_search_context(SPLIT_TYPE1, "Current operational state", log, row=1)
                    if port_state == "Link UP":
                        check = STATUS_OK

                content = "이웃 장비 포트에 udld설정 시 uplink 상태를 정상적으로 보여주고 있는가?"

            elif self.config_mode == "NBR1":
                target_port = self.config["(nbr1)nbr_port1"]
                udld_state = get_search_context(SPLIT_TYPE1, "Port administrative", log, row=1)
                if udld_state == "Enable":
                    port_state = get_search_context(SPLIT_TYPE1, "Current operational state", log, row=1)
                    if port_state == "Link UP":
                        check = STATUS_OK

                content = "이웃 장비 포트에 udld설정 시 uplink 상태를 정상적으로 보여주고 있는가?"

            status  = f"Port administrative={udld_state}\nCurrent operational state={port_state}"

        elif action == "udld-advertise":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                udld_state = get_search_context(SPLIT_TYPE1, "Port administrative", log, row=1)
                if udld_state == "Enable":
                    nbr_host    = get_search_context(SPLIT_TYPE1, "Device name", log, row=1)
                    nbr_serial  = get_search_context(SPLIT_TYPE1, "Device ID", log, row=1)
                    nbr_port    = get_search_context(SPLIT_TYPE1, "Port ID", log, row=1)
                    host_serial = get_search_context(SPLIT_TYPE1, "Neighbor echo 1 device", log, row=1)
                    host_port   = get_search_context(SPLIT_TYPE1, "Neighbor echo 1 port", log, row=1)
                    #if (nbr_product == self.config['nbr1_product']
                    if (nbr_host == self.config['(nbr1)dev_prompt']
                        and nbr_serial == self.config['nbr1_serial']
                        and nbr_port == self.config['(nbr1)nbr_port1']
                        and host_serial == self.config['host_serial']
                        and host_port == target_port):
                        check = STATUS_OK

                content = "테스트 장비 포트에 udld설정 시 advertise 상태를 정상적으로 보여주고 있는가?"
                status  = f"Neighbor Device name={nbr_host}"
                status += f"\nNeighbot Device ID={nbr_serial}"
                status += f"\nNeighbor Port ID={nbr_port}"
                status += f"\nHost Serial={host_serial}"
                status += f"\nHost port={host_port}"

            elif self.config_mode == "NBR1":
                target_port = self.config["(nbr1)nbr_port1"]
                udld_state = get_search_context(SPLIT_TYPE1, "Port administrative", log, row=1)
                if udld_state == "Enable":
                    host_host   = get_search_context(SPLIT_TYPE1, "Device name", log, row=1)
                    host_serial = get_search_context(SPLIT_TYPE1, "Device ID", log, row=1)
                    host_port   = get_search_context(SPLIT_TYPE1, "Port ID", log, row=1)
                    nbr_serial  = get_search_context(SPLIT_TYPE1, "Neighbor echo 1 device", log, row=1)
                    nbr_port    = get_search_context(SPLIT_TYPE1, "Neighbor echo 1 port", log, row=1)
                    #if (host_product == self.config['host_product']
                    if (host_host == self.config['dev_prompt']
                        and host_serial == self.config['host_serial']
                        and host_port == self.config['dev_port1']
                        and nbr_serial == self.config['nbr1_serial']
                        and nbr_port == target_port):
                        check = STATUS_OK

                content = "이웃 장비 포트에 udld설정 시 advertise 상태를 정상적으로 보여주고 있는가?"
                status  = f"Neighbor Device name={host_host}"
                status += f"\nNeighbot Device ID={host_serial}"
                status += f"\nNeighbor Port ID={host_port}"
                status += f"\nHost Serial={nbr_serial}"
                status += f"\nHost port={nbr_port}"

        elif action == "udld-unset":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                udld_state = get_search_context(SPLIT_TYPE1, "Port administrative", log, row=1)
                if udld_state == "Disable":
                    check = STATUS_OK

                content = "테스트 장비 포트에 udld해제 시 disable 상태를 정상적으로 보여주고 있는가?"

            elif self.config_mode == "NBR1":
                target_port = self.config["(nbr1)nbr_port1"]
                udld_state = get_search_context(SPLIT_TYPE1, "Port administrative", log, row=1)
                if udld_state == "Disable":
                    check = STATUS_OK

                content = "이웃 포트에 udld해제 시 disable 상태를 정상적으로 보여주고 있는가?"

            status  = f"Port administrative={udld_state}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_vlan_test_data(self, action=str, log=list, index=0):
        """
        Parse VLAN test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "access-set", "hybrid-set", "trunk-set").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "access-set":
            if self.config_mode == "CLI":
                target_port = self.config["dev_port1"]
                vid100       = get_search_context(SPLIT_TYPE2, "VLAN0100", log, row=int(self.config['dev_port1'][2:])+2)
                rx_port_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=1)) # input_port rx
                tx_port_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} ",  log, row=3)) # dev_port1 tx
                if vid100 == 'U':
                    if rx_port_stat > 0 and tx_port_stat > 0 and abs(rx_port_stat - tx_port_stat) < MIN_DELAY_LIMIT:
                        check = STATUS_OK

                # progress log
                content = "access vlan 정상적으로 설정되었는가?\n트래픽이 정상적으로 흐르는가?"
                status  = f"VLAN0100={vid100}"
                status += f"\n{self.config['input_port']}-rxpps={rx_port_stat}"
                status += f"\n{self.config['dev_port1']}-txpps={tx_port_stat}"

            elif self.config_mode == "SHELL":
                target_port    = self.config["sdk_port1"]
                ports          = [int(target_port)]
                memps_line     = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 1", log, cols=2, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 1", log, cols=3, row=1)
                vid1_memps     = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid1_untagps   = rtk_sdk_parse_match('ports', untagps_line, ports)
                memps_line     = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 100", log, cols=2, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 100", log, cols=3, row=1)
                vid100_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid100_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)
                pvid_inner     = get_search_context(SPLIT_TYPE1, "Port based vlan",            log, cols=1, row=1)
                pvid_outer     = get_search_context(SPLIT_TYPE1, "Outer tag port based vlan",  log, cols=1, row=1)
                accept_frame   = get_search_context(SPLIT_TYPE1, "Accept frame type of ports", log, cols=1, row=1)
                if (vid1_memps == vid1_untagps == False and vid100_memps == vid100_untagps == True
                    and pvid_inner == '100'
                    and pvid_outer == '1'
                    and accept_frame == 'accept untag frame only'):
                    check = STATUS_OK

                # progress log
                content = "access vlan 정상적으로 설정되었는가?"
                status  = f"vid1-exclude-memports={str(not vid1_memps)}"
                status += f"\nvid1-exclude-tagports={str(not vid1_untagps)}"
                status += f"\nvid100-include-memports={str(vid100_memps)}"
                status += f"\nvid100-include-tagports={str(vid100_untagps)}"
                status += f"\npvid[inner={pvid_inner} outer={pvid_outer} frame={accept_frame}]"

        elif action == "hybrid-set":
            if self.config_mode == "CLI":
                target_port   = self.config["dev_port1"]
                vid1          = get_search_context(SPLIT_TYPE2, "default",  log, row=int(self.config['dev_port1'][2:])+2)
                vid100        = get_search_context(SPLIT_TYPE2, "VLAN0100", log, row=int(self.config['dev_port1'][2:])+2)
                rx_port1_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} |",  log, row=1))  # input_port rx
                tx_port1_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} |",   log, row=3))  # dev_port1 tx
                tx_port2_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port2']} |",   log, row=3))  # dev_port2 tx
                tx_port3_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port3']} |",   log, row=3))  # dev_port3 tx
                if vid100 == 'U' and vid1 == 'u':
                    if (rx_port1_stat > 0 and tx_port1_stat > 0 and tx_port2_stat > 0 and tx_port3_stat > 0
                        and abs(rx_port1_stat - tx_port1_stat) < MIN_DELAY_LIMIT
                        and abs(rx_port1_stat - tx_port2_stat) < MIN_DELAY_LIMIT
                        and abs(rx_port1_stat - tx_port3_stat) < MIN_DELAY_LIMIT):
                        check = STATUS_OK

                # progress log
                content = "hybrid vlan 정상적으로 설정되었는가?\n트래픽이 정상적으로 흐르는가?"
                status  = f"default={vid1}, VLAN0100={vid100}"
                status += f"\n{self.config['input_port']}-rxpps={str(rx_port1_stat)}"
                status += f"\n{self.config['dev_port1']}-txpps={str(tx_port1_stat)}"
                status += f"\n{self.config['dev_port2']}-txpps={str(tx_port2_stat)}"
                status += f"\n{self.config['dev_port3']}-txpps={str(tx_port3_stat)}"

            elif self.config_mode == "SHELL":
                target_port = self.config["sdk_port1"]

                ports          = [int(target_port)]
                memps_line     = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 1", log, cols=2, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 1", log, cols=3, row=1)
                vid1_memps     = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid1_untagps   = rtk_sdk_parse_match('ports', untagps_line, ports)
                memps_line     = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 100", log, cols=2, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 100", log, cols=3, row=1)
                vid100_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid100_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)
                pvid_inner     = get_search_context(SPLIT_TYPE1, "Port based vlan",            log, cols=1, row=1)
                pvid_outer     = get_search_context(SPLIT_TYPE1, "Outer tag port based vlan",  log, cols=1, row=1)
                accept_frame   = get_search_context(SPLIT_TYPE1, "Accept frame type of ports", log, cols=1, row=1)
                if (vid1_memps == vid1_untagps == vid100_memps == vid100_untagps == True
                    and pvid_inner == '100'
                    and pvid_outer == '1'
                    and accept_frame == 'accept all frame'):
                    check = STATUS_OK

                # progress log
                content = "hybrid vlan 정상적으로 설정되었는가?"
                status  = f"vid1-include-memports={str(vid1_memps)}"
                status += f"\nvid1-include-tagports={str(vid1_untagps)}"
                status += f"\nvid100-include-memports={str(vid100_memps)}"
                status += f"\nvid100-include-tagports={str(vid100_untagps)}"
                status += f"\npvid[inner={pvid_inner} outer={pvid_outer} frame={accept_frame}]"

        elif action == "trunk-set":
            if self.config_mode == "CLI":
                target_port   = self.config["dev_port1"]
                vid1          = get_search_context(SPLIT_TYPE2, "default",  log, row=int(self.config['dev_port1'][2:])+2)
                vid100        = get_search_context(SPLIT_TYPE2, "VLAN0100", log, row=int(self.config['dev_port1'][2:])+2)
                rx_port1_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} |",  log, row=1))  # input_port rx
                tx_port1_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} |",   log, row=3))  # dev_port1 tx
                tx_port2_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port2']} |",   log, row=3))  # dev_port2 tx
                tx_port3_stat = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port3']} |",   log, row=3))  # dev_port3 tx
                if vid100 == 't' and vid1 == 'T':
                    if (rx_port1_stat > 0 and tx_port1_stat > 0 and tx_port2_stat > 0 and tx_port3_stat > 0
                        and abs(rx_port1_stat - tx_port1_stat) < MIN_DELAY_LIMIT
                        and abs(rx_port1_stat - tx_port2_stat) < MIN_DELAY_LIMIT
                        and abs(rx_port1_stat - tx_port3_stat) < MIN_DELAY_LIMIT):
                        check = STATUS_OK

                # progress log
                content = "trunk vlan 정상적으로 설정되었는가?\n트래픽이 정상적으로 흐르는가?"
                status  = f"default={vid1}, VLAN0100={vid100}"
                status += f"\n{self.config['input_port']}-rxpps={str(rx_port1_stat)}"
                status += f"\n{self.config['dev_port1']}-txpps={str(tx_port1_stat)}"
                status += f"\n{self.config['dev_port2']}-txpps={str(tx_port2_stat)}"
                status += f"\n{self.config['dev_port3']}-txpps={str(tx_port3_stat)}"

            elif self.config_mode == "SHELL":
                target_port    = self.config["sdk_port1"]
                ports          = [int(target_port)]
                memps_line     = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 1", log, cols=2, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 1", log, cols=3, row=1)
                vid1_memps     = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid1_untagps   = rtk_sdk_parse_match('ports', untagps_line, ports)
                memps_line     = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 100", log, cols=2, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, "vlan get vlan-table vid 100", log, cols=3, row=1)
                vid100_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid100_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)
                pvid_inner     = get_search_context(SPLIT_TYPE1, "Port based vlan",            log, cols=1, row=1)
                pvid_outer     = get_search_context(SPLIT_TYPE1, "Outer tag port based vlan",  log, cols=1, row=1)
                accept_frame   = get_search_context(SPLIT_TYPE1, "Accept frame type of ports", log, cols=1, row=1)
                if (vid1_memps == vid100_memps == True and vid1_untagps == vid100_untagps == False
                    and pvid_inner == '1'
                    and pvid_outer == '1'
                    and accept_frame == 'accept all frame'):
                    check = STATUS_OK

                # progress log
                content = "trunk vlan 정상적으로 설정되었는가?"
                status  = f"vid1-include-memports={str(vid1_memps)}"
                status += f"\nvid1-exclude-tagports={str(not vid1_untagps)}"
                status += f"\nvid100-include-memports={str(vid100_memps)}"
                status += f"\nvid100-exclude-tagports={str(not vid100_untagps)}"
                status += f"\npvid[inner={pvid_inner} outer={pvid_outer} frame={accept_frame}]"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_lacp_test_data(self, action=str, log=list, index=0):
        """
        Parse LACP test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "lacp-set-show", "lacp-unset-show").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "lacp-set-show":
            target_port = f"{self.config['dev_port1']},{self.config['dev_port2']}"
            act        = get_search_context(SPLIT_TYPE1, "show portstatus | in agg1 ", log, cols=1, row=1)
            dev_state1 = get_search_context(SPLIT_TYPE1, f"show portstatus | in {self.config['dev_port1']} ", log, cols=1, row=7)
            dev_state2 = get_search_context(SPLIT_TYPE1, f"show portstatus | in {self.config['dev_port2']} ", log, cols=1, row=7)

            dev_port1 = get_search_context(SPLIT_TYPE2, f"Link: {self.config['dev_port1']}", log, row=2)
            dev_port2 = get_search_context(SPLIT_TYPE2, f"Link: {self.config['dev_port2']}", log, row=2)

            agg1_rx = get_integer_val(get_search_context(SPLIT_TYPE2, "AGGREGATOR TRAFFIC", log, cols=6, row=1))
            dev1_rx = get_integer_val(get_search_context(SPLIT_TYPE2, "AGGREGATOR TRAFFIC", log, cols=7, row=1)[:-1])
            dev2_rx = get_integer_val(get_search_context(SPLIT_TYPE2, "AGGREGATOR TRAFFIC", log, cols=8, row=1)[:-1])

            agg1_tx = get_integer_val(get_search_context(SPLIT_TYPE2, "AGGREGATOR TRAFFIC", log, cols=6, row=3))
            dev1_tx = get_integer_val(get_search_context(SPLIT_TYPE2, "AGGREGATOR TRAFFIC", log, cols=7, row=3)[:-1])
            dev2_tx = get_integer_val(get_search_context(SPLIT_TYPE2, "AGGREGATOR TRAFFIC", log, cols=8, row=3)[:-1])

            host_agg1_mac0 = self.config['host_mac_colon'].split(':')
            host_agg1_mac0[-1] = format(int(host_agg1_mac0[-1], 16)+1, '02x')
            host_agg1_mac1 = ':'.join([get_search_context(SPLIT_TYPE1, "Mac address", log, row=i) for i in range(1, 7)])

            nbr_agg1_mac0 = self.config['nbr1_mac_colon'].split(':')
            nbr_agg1_mac0[-1] = format(int(nbr_agg1_mac0[-1], 16)+1, '02x')
            nbr_agg1_mac1  = get_search_context(SPLIT_TYPE1, "Partner LAG-", log, row=1).replace('-', ':')

            lacp_port1 = get_idx(f"interface {self.config['dev_port1']}", log)
            lacp_port2 = get_idx(f"interface {self.config['dev_port2']}", log)
            if (act == 'EN' and dev_state1 == 'FWD' and dev_state2 == 'FWD'
                and dev_port1 == self.config['dev_port1'] and dev_port2 == self.config['dev_port2']
                and agg1_rx == (dev1_rx + dev2_rx) and agg1_tx == (dev1_tx + dev2_tx)
                and ':'.join(host_agg1_mac0) == host_agg1_mac1 and ':'.join(nbr_agg1_mac0) == nbr_agg1_mac1):
                check = STATUS_OK

            content = "lacp설정 시 lacp에 대한 정보와 트래픽이 옳게 표시되는가?"
            status  = f"Port state=(agg1={act}, {self.config['dev_port1']}={dev_state1}, {self.config['dev_port1']}={dev_state2})"
            status += f"\nAgg1=(Mac-adress={host_agg1_mac1}, Partner-LAG={nbr_agg1_mac1})"
            status += f"\nEtherchannel=(link1={dev_port1}, link2={dev_port2})"
            status += f"\nrx-statistic=(agg1-rx={agg1_rx}, {self.config['dev_port1']}-rx={dev1_rx}, {self.config['dev_port2']}-rx={dev2_rx})"
            status += f"\ntx-statistic=(agg1-tx={agg1_tx}, {self.config['dev_port1']}-tx={dev1_tx}, {self.config['dev_port2']}-tx={dev2_tx})"

        elif action == "lacp-unset-show":
            target_port = f"{self.config['dev_port1']},{self.config['dev_port2']}"
            dev_state1 = get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} |", log, row=7)
            dev_state2 = get_search_context(SPLIT_TYPE1, f"{self.config['dev_port2']} |", log, row=7)

            agg1_intf = get_idx("Interface not found", log)
            dev1_intf = get_idx(f"Can't find interface {self.config['dev_port1']}.", log)
            dev2_intf = get_idx(f"Can't find interface {self.config['dev_port2']}.", log)
            if (dev_state1 == 'FWD' and dev_state2 == 'FWD' and len(agg1_intf) == 1 and len(dev1_intf) == 1 and len(dev2_intf) == 1):
                check = STATUS_OK

            content = "lacp설정 해제 시 lacp설정이  정상적으로 해제되었나?"
            status  = f"Port state=({self.config['dev_port1']}={dev_state1}, {self.config['dev_port1']}={dev_state2})"
            status += f"\nMac-table=(agg1={'not-found' if len(agg1_intf) > 0 else 'found'})"
            status += f"\nPort Interface=({self.config['dev_port1']}={'lacp Not setting' if len(dev1_intf) > 0 else 'lacp set'})"
            status += f"\nPort Interface=({self.config['dev_port2']}={'lacp Not setting' if len(dev2_intf) > 0 else 'lacp set'})"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_stp_test_data(self, action=str, log=list, index=0):
        """
        Parse Spanning-Tree test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "root-bridge-set1", "non-root-bridge-set", "root-bridge-set2", "port-priority-set1", "port-priority-set2", "port-cost-set1", "port-cost-set2", "port-failover1", "port-failover2").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        config = f"({self.config_mode.lower()})" if self.config_mode != 'CLI' else ""

        if action == "root-bridge-set1":
            port1       = self.config[config+'dev_port1']
            port2       = self.config[config+'dev_port2']
            port3       = self.config[config+'dev_port4']
            txrx_port1  = self.config[config+'input_port']
            txrx_port2  = self.config[config+'dev_port4']
            content     = "[A장비 확인] rpvst+ 설정 후 A장비 priority를 낮게 변경한 후 A장비가 root-bridge로 변경되었는가?"

        elif action == "non-root-bridge-set":
            port1      = self.config[config+'dev_port1']
            port2      = self.config[config+'dev_port2']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = None
            content    = "[A장비 확인] rpvst+ 설정 후 A장비 priority를 높게 변경한 후 A장비가 Non-root-bridge로 변경되었는가?"

        elif action == "root-bridge-set2":
            port1      = self.config[config+'nbr_port1']
            port2      = self.config[config+'nbr_port2']
            port3      = self.config[config+'dev_port1']
            txrx_port1 = self.config[config+'dev_port1']
            txrx_port2 = None
            content    = "[B장비 확인] rpvst+ 설정 후 B장비 priority를 낮게 변경한 후 B장비가 root-bridge로 변경되었는가?"

        elif action == "port-priority-set1":
            port1      = self.config[config+'dev_port1']
            port2      = self.config[config+'dev_port2']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port1']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 priority 변경 후 A장비 루트포트가 P1({port1})으로 변경되었는가?"

        elif action == "port-priority-set2":
            port1      = self.config[config+'dev_port1']
            port2      = self.config[config+'dev_port2']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port2']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 priority 변경 후 A장비 루트포트가 P2({port2})으로 변경되었는가?"

        elif action == "port-cost-set1":
            port1      = self.config[config+'dev_port1']
            port2      = self.config[config+'dev_port2']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port1']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 cost 변경 후 A장비 루트포트가 P1({port1})으로 변경되었는가?"

        elif action == "port-cost-set2":
            port1      = self.config[config+'dev_port1']
            port2      = self.config[config+'dev_port2']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port2']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 cost 변경 후 A장비 루트포트가 P2({port2})으로 변경되었는가?"

        elif action == "port-failover1":
            port1      = self.config[config+'dev_port1']
            port2      = self.config[config+'dev_port2']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port1']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 P2({port2})포트 절체 후 A장비 루트포트가 P1({port1})으로 변경되었는가?"

        elif action == "port-failover2":
            port1      = self.config[config+'dev_port1']
            port2      = self.config[config+'dev_port2']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port4']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 P1({port1})포트 추가 절체 후 A장비 루트포트가 P3({port3})으로 변경되었는가?"

        else:
            return

        target_port = f"{txrx_port1},{port1},{port2},{port3}"

        stp_info = False
        stp_stat = False

        rootport = get_search_context(SPLIT_TYPE2, "root port", log, row=2)
        cost     = get_search_context(SPLIT_TYPE2, "root port", log, row=6)
        # spanning-tree info port1
        p1_cost  = get_search_context(SPLIT_TYPE2, f"{port1}:", log, row=6)
        if p1_cost == '': p1_cost = 'None'
        p1_role  = get_search_context(SPLIT_TYPE2, f"{port1}:", log, row=9)
        if p1_role == '': p1_role = 'None'
        p1_stat  = get_search_context(SPLIT_TYPE2, f"{port1}:", log, row=11)
        if p1_stat == '': p1_stat = 'None'
        # spanning-tree info port2
        p2_cost  = get_search_context(SPLIT_TYPE2, f"{port2}:", log, row=6)
        if p2_cost == '': p2_cost = 'None'
        p2_role  = get_search_context(SPLIT_TYPE2, f"{port2}:", log, row=9)
        if p2_role == '': p2_role = 'None'
        p2_stat  = get_search_context(SPLIT_TYPE2, f"{port2}:", log, row=11)
        if p2_stat == '': p2_stat = 'None'
        # spanning-tree info port3
        p3_cost  = get_search_context(SPLIT_TYPE2, f"{port3}:", log, row=6)
        if p3_cost == '': p3_cost = 'None'
        p3_role  = get_search_context(SPLIT_TYPE2, f"{port3}:", log, row=9)
        if p3_role == '': p3_role = 'None'
        p3_stat  = get_search_context(SPLIT_TYPE2, f"{port3}:", log, row=11)
        if p3_stat == '': p3_stat = 'None'

        if action == "root-bridge-set1" or action == "root-bridge-set2":
            if (rootport == '---' and cost == '0'
                and p1_cost == '20000' and p1_role == 'Designated' and p1_stat == 'Forwarding'
                and p2_cost == '20000' and p2_role == 'Designated' and p2_stat == 'Forwarding'
                and p3_cost == '20000' and p3_role == 'Designated' and p3_stat == 'Forwarding'):
                stp_info = True
        elif action == "non-root-bridge-set":
            if rootport == port1:
                self.config['rootport'] = 'nbr_port1'
                if (p1_cost == '20000'     and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                    and p2_cost == '20000' and p2_role == 'Alternate'  and p2_stat == 'Discarding'
                    and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                    stp_info = True
            elif rootport == port2:
                self.config['rootport'] = 'nbr_port2'
                if (p1_cost == '20000'     and p1_role == 'Alternate'  and p1_stat == 'Discarding'
                    and p2_cost == '20000' and p2_role == 'Rootport'   and p2_stat == 'Forwarding'
                    and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                    stp_info = True
        elif action == "port-priority-set1":
            if (rootport == port1 and cost == '20000'
                and p1_cost == '20000' and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                and p2_cost == '20000' and p2_role == 'Alternate'  and p2_stat == 'Discarding'
                and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                stp_info = True
        elif action == "port-priority-set2":
            if (rootport == port2 and cost == '20000'
                and p1_cost == '20000' and p1_role == 'Alternate'  and p1_stat == 'Discarding'
                and p2_cost == '20000' and p2_role == 'Rootport'   and p2_stat == 'Forwarding'
                and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                stp_info = True
        elif action == "port-cost-set1":
            if (rootport == port1 and cost == '15000'
                and p1_cost == '15000' and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                and p2_cost == '20000' and p2_role == 'Alternate'  and p2_stat == 'Discarding'
                and p3_cost == '20000' and p3_role == 'Designated' and p3_stat == 'Forwarding'):
                stp_info = True
        elif action == "port-cost-set2":
            if (rootport == port2 and cost == '20000'
                and p1_cost == '25000' and p1_role == 'Alternate'  and p1_stat == 'Discarding'
                and p2_cost == '20000' and p2_role == 'Rootport'   and p2_stat == 'Forwarding'
                and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                stp_info = True
        elif action == "port-failover1":
            if (rootport == port1 and cost == '25000'
                and p1_cost == '25000' and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                and p2_cost == 'None'  and p2_role == 'None'       and p2_stat == 'None'
                and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                stp_info = True
        elif action == "port-failover2":
            if (rootport == port3 and cost == '40000'
                and p1_cost == 'None'  and p1_role == 'None'       and p1_stat == 'None'
                and p2_cost == 'None'  and p2_role == 'None'       and p2_stat == 'None'
                and p3_cost == '20000' and p3_role == 'Rootport'   and p3_stat == 'Forwarding'):
                stp_info = True

        if self.config_mode == "NBR1":
            modelname = self.config['nbr1_model']
            if txrx_port2 == None and rootport == '---':
                if '(nbr1)'+self.config['rootport'] in self.config:
                    txrx_port2 = self.config['(nbr1)'+self.config['rootport']]
                else:
                    txrx_port2 = self.config['(nbr1)nbr_port1']
        elif self.config_mode == "NBR2":
            modelname = self.config['nbr2_model']
            if txrx_port2 == None and rootport == '---':
                if '(nbr2)'+self.config['rootport'] in self.config:
                    txrx_port2 = self.config['(nbr2)'+self.config['rootport']]
                else:
                    txrx_port2 = self.config['(nbr2)nbr_port1']
        else:
            modelname = self.config['host_model']
            if txrx_port2 == None and rootport == '---':
                if self.config['rootport'] in self.config:
                    txrx_port2 = self.config[self.config['rootport']]
                else:
                    txrx_port2 = self.config['nbr_port1']

        if txrx_port2 == None and rootport != '---':
            txrx_port2 = rootport

        if txrx_port2 == port1:
            pos   = 'P1'
            state = p1_stat
        elif txrx_port2 == port2:
            pos   = 'P2'
            state = p2_stat
        elif txrx_port2 == port3:
            pos   = 'P3'
            state = p3_stat
        else:
            pos = state = 'unKnown'

        # spanning-tree port-monitoring pkt statistic
        in_pkt_rx    = int(get_search_context(SPLIT_TYPE1, f"{txrx_port1} |", log, row=1))
        in_pkt_tx    = int(get_search_context(SPLIT_TYPE1, f"{txrx_port1} |", log, row=3))
        p_pkt_rx     = int(get_search_context(SPLIT_TYPE1, f"{txrx_port2} |", log, row=1))
        p_pkt_tx     = int(get_search_context(SPLIT_TYPE1, f"{txrx_port2} |", log, row=3))
        if p1_stat == 'Discarding': p1_pktdis_tx = int(get_search_context(SPLIT_TYPE1, f"{port1} |", log, row=3))
        else:                       p1_pktdis_tx = -1
        if p2_stat == 'Discarding': p2_pktdis_tx = int(get_search_context(SPLIT_TYPE1, f"{port2} |", log, row=3))
        else:                       p2_pktdis_tx = -1
        if p3_stat == 'Discarding': p3_pktdis_tx = int(get_search_context(SPLIT_TYPE1, f"{port3} |", log, row=3))
        else:                       p3_pktdis_tx = -1

        pkt_delay = abs(in_pkt_rx - p_pkt_tx)
        if (in_pkt_rx > 0 and p_pkt_tx > 0
            and pkt_delay < MIN_DELAY_LIMIT
            and ((p1_pktdis_tx < 0) or (p1_pktdis_tx == 0))
            and ((p2_pktdis_tx < 0) or (p2_pktdis_tx == 0))
            and ((p3_pktdis_tx < 0) or (p3_pktdis_tx == 0))):
            stp_stat = True

        if stp_info == stp_stat == True:
            check = STATUS_OK

        status  = "* rpvst+ info"
        status += f"\n  Spanning-tree: model={modelname}, rootport={rootport}, cost={cost}"
        status += f"\n  {port1:<4}: pos=P1, cost={p1_cost:<5}, role={p1_role:<10}, state={p1_stat}"
        status += f"\n  {port2:<4}: pos=P2, cost={p2_cost:<5}, role={p2_role:<10}, state={p2_stat}"
        status += f"\n  {port3:<4}: pos=P3, cost={p3_cost:<5}, role={p3_role:<10}, state={p3_stat}"
        status += "\n* rpvst+ statistics"
        status += f"\n  {txrx_port1:<4}: pos=TC, state=FWD, rxpps={in_pkt_rx:<5}"
        status += f"\n  {txrx_port2:<4}: pos={pos}, state={state}, txpps={p_pkt_tx}"
        if p1_stat == 'Discarding': status += f"\n  {port1:<4}: pos=P1, state=DIS, txpps={p1_pktdis_tx}"
        if p2_stat == 'Discarding': status += f"\n  {port2:<4}: pos=P2, state=DIS, txpps={p2_pktdis_tx}"
        if p3_stat == 'Discarding': status += f"\n  {port3:<4}: pos=P3, state=DIS, txpps={p3_pktdis_tx}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_private_vlan_test_data(self, action=str, log=list, index=0):
        """
        Parse Private-VLAN test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "private-vlan-set", "primary-port-statistic", "common1-port-statistic", "common2-port-statistic", "isolated-port-statistic", "private-vlan-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "private-vlan-set":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['dev_port1']},{self.config['dev_port2']},{self.config['dev_port3']}"

                com_idx  = get_idx("  community", log)
                if len(com_idx) == 0: com_idx = 0
                else: com_idx = com_idx[0]
                isol_idx = get_idx("   isolated", log)
                if len(isol_idx) == 0: isol_idx = 0
                else: isol_idx = isol_idx[0]

                pri0_vlan  = get_search_context(SPLIT_TYPE2, self.config['input_port'], log[com_idx])
                pri1_vlan  = get_search_context(SPLIT_TYPE2, self.config['input_port'], log[isol_idx])
                com0_vlan = get_search_context(SPLIT_TYPE2, self.config['dev_port1'], log[com_idx], row=1)
                com1_vlan = get_search_context(SPLIT_TYPE2, self.config['dev_port2'], log[com_idx], row=1)
                isol_vlan = get_search_context(SPLIT_TYPE2, self.config['dev_port3'], log[isol_idx], row=1)
                if pri0_vlan == pri1_vlan == '100' and com0_vlan == com1_vlan == '200' and isol_vlan == '300':
                    check = STATUS_OK

                content = "private-vlan 설정 정보가 정상적으로 설정되었는가?"
                status  = f"primary[vlan{pri0_vlan}]={self.config['input_port']} <-> community[vlan{com0_vlan}]={self.config['dev_port1']},{self.config['dev_port2']}"
                status += f"\nprimary[vlan{pri1_vlan}]={self.config['input_port']} <-> isolated[vlan{isol_vlan}]={self.config['dev_port3']}"

            elif self.config_mode == "SHELL":
                target_port = f"{self.config[self.config['input_port']]},{self.config['sdk_port1']},{self.config['sdk_port2']},{self.config['sdk_port3']}"
                pri_port       = self.config[self.config['input_port']]
                ports          = [int(pri_port), int(self.config['sdk_port1']), int(self.config['sdk_port2']), int(self.config['sdk_port3'])]
                memps_line     = get_search_context(SPLIT_TYPE0, 'Vlan 100', log, cols=1, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, 'Vlan 100', log, cols=2, row=1)
                vid100_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid100_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)

                ports          = [int(pri_port), int(self.config['sdk_port1']), int(self.config['sdk_port2'])]
                memps_line     = get_search_context(SPLIT_TYPE0, 'Vlan 200', log, cols=1, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, 'Vlan 200', log, cols=2, row=1)
                vid200_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid200_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)

                ports          = [int(pri_port), int(self.config['sdk_port3'])]
                memps_line     = get_search_context(SPLIT_TYPE0, 'Vlan 300', log, cols=1, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, 'Vlan 300', log, cols=2, row=1)
                vid300_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid300_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)

                lo_vid     = get_search_context(SPLIT_TYPE2, 'port dump isolation vlan-based', log, cols=3, row=1)
                up_vid     = get_search_context(SPLIT_TYPE2, 'port dump isolation vlan-based', log, cols=3, row=2)
                trust_port = get_search_context(SPLIT_TYPE2, 'port dump isolation vlan-based', log, cols=3, row=3)
                state      = get_search_context(SPLIT_TYPE2, 'port dump isolation vlan-based', log, cols=3, row=4)

                com1_vid   = get_search_context(SPLIT_TYPE1, f"Port {self.config['sdk_port1']}", log, row=1)
                com2_vid   = get_search_context(SPLIT_TYPE1, f"Port {self.config['sdk_port2']}", log, row=1)
                isol_vid   = get_search_context(SPLIT_TYPE1, f"Port {self.config['sdk_port3']}", log, row=1)

                if (vid100_memps == vid100_untagps == vid200_memps == vid200_untagps == vid300_memps == vid300_untagps == True
                    and lo_vid == up_vid == '100' and trust_port == pri_port and state == 'Enable'
                    and com1_vid == com2_vid == '200' and isol_vid == '100'):
                    check = STATUS_OK

                # progress log
                content = "private-vlan 설정 정보가 SDK상에서 정상적으로 설정되었는가?"
                status  = f"vid100-include-memports={str(vid100_memps)}"
                status += f"\nvid100-include-untagports={str(vid100_untagps)}"
                status += f"\nvid200-include-memports={str(vid200_memps)}"
                status += f"\nvid200-include-untagports={str(vid200_untagps)}"
                status += f"\nvid300-include-memports={str(vid300_memps)}"
                status += f"\nvid300-include-untagports={str(vid300_untagps)}"
                status += f"\nlo-vid={lo_vid}, up-vid={up_vid}, trust-port={trust_port}, state={state}"
                status += f"\nvid{com1_vid}=port{self.config['sdk_port1']}"
                status += f"\nvid{com2_vid}=port{self.config['sdk_port2']}"
                status += f"\nvid{isol_vid}=port{self.config['sdk_port3']}"

        elif action == "primary-port-traffic-test":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['dev_port1']},{self.config['dev_port2']},{self.config['dev_port3']}"
                input_port_rx = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=1))  # input_port rx
                dev_port1_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} ",  log, row=3))  # dev_port1 tx
                dev_port2_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port2']} ",  log, row=3))  # dev_port2 tx
                dev_port3_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port3']} ",  log, row=3))  # dev_port3 tx
                if (input_port_rx > 0 and dev_port1_tx > 0 and dev_port2_tx > 0 and dev_port3_tx > 0
                    and abs(input_port_rx - dev_port1_tx) < MIN_DELAY_LIMIT
                    and abs(input_port_rx - dev_port2_tx) < MIN_DELAY_LIMIT
                    and abs(input_port_rx - dev_port3_tx) < MIN_DELAY_LIMIT):
                    check = STATUS_OK

                # progress log
                content = "primary 포트에서 common1, common2, isolated 포트로 트래픽이 정상적으로 흐르고 있는가?"
                status  = f"{self.config['input_port']}-rxpps={str(input_port_rx)}[Primary]"
                status += f"\n{self.config['dev_port1']}-tx-pps={str(dev_port1_tx)}[Community]"
                status += f"\n{self.config['dev_port2']}-tx-pps={str(dev_port2_tx)}[Community]"
                status += f"\n{self.config['dev_port3']}-tx-pps={str(dev_port3_tx)}[Isolated]"

        elif action == "common1-port-traffic-test":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['dev_port1']},{self.config['dev_port2']},{self.config['dev_port3']}"
                input_port_tx = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=3))  # input_port tx
                input_port_rx = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=1))  # input_port rx
                dev_port1_rx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} ",  log, row=1))  # dev_port1 rx
                dev_port2_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port2']} ",  log, row=3))  # dev_port2 tx
                dev_port3_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port3']} ",  log, row=3))  # dev_port3 tx
                if (input_port_rx > 0 and input_port_tx > 0 and dev_port1_rx > 0 and dev_port2_tx > 0 and dev_port3_tx > 0
                    and abs(dev_port1_rx - input_port_tx) < MIN_DELAY_LIMIT
                    and abs((dev_port1_rx + input_port_rx) - dev_port2_tx) < MIN_DELAY_LIMIT
                    and abs(input_port_rx - dev_port3_tx) < MIN_DELAY_LIMIT):
                    check = STATUS_OK

                # progress log
                content = "common1 포트에서 primary, common2 포트로 트래픽이 정상적으로 흐르고 있는가?"
                status  = f"{self.config['dev_port1']}-rxpps={str(dev_port1_rx)}[Community]"
                status += f"\n{self.config['input_port']}-txpps={str(input_port_tx)}[Primary]"
                status += f"\n{self.config['dev_port2']}-txpps={str(dev_port2_tx)}[Community]"
                status += f"\n{self.config['dev_port3']}-txpps={str(dev_port3_tx)}[Isolated]"

        elif action == "common2-port-traffic-test":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['dev_port1']},{self.config['dev_port2']},{self.config['dev_port3']}"
                input_port_tx = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=3))  # input_port tx
                input_port_rx = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=1))  # input_port rx
                dev_port1_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} ",  log, row=3))  # dev_port1 tx
                dev_port2_rx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port2']} ",  log, row=1))  # dev_port2 rx
                dev_port3_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port3']} ",  log, row=3))  # dev_port3 tx
                if (input_port_rx > 0 and input_port_tx > 0 and dev_port1_tx > 0 and dev_port2_rx > 0 and dev_port3_tx > 0
                    and abs(dev_port2_rx - input_port_tx) < MIN_DELAY_LIMIT
                    and abs((dev_port2_rx + input_port_rx) - dev_port1_tx) < MIN_DELAY_LIMIT
                    and abs(input_port_rx - dev_port3_tx) < MIN_DELAY_LIMIT):
                    check = STATUS_OK

                # progress log
                content = "common2 포트에서 primary, common1 포트로 트래픽이 정상적으로 흐르고 있는가?"
                status  = f"{self.config['dev_port2']}-rxpps={str(dev_port2_rx)}[Community]"
                status += f"\n{self.config['input_port']}-txpps={str(input_port_tx)}[Primary]"
                status += f"\n{self.config['dev_port1']}-txpps={str(dev_port1_tx)}[Community]"
                status += f"\n{self.config['dev_port3']}-txpps={str(dev_port3_tx)}[Isolated]"

        elif action == "isolated-port-traffic-test":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['dev_port1']},{self.config['dev_port2']},{self.config['dev_port3']}"
                input_port_tx = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=3))  # input_port tx
                input_port_rx = int(get_search_context(SPLIT_TYPE1, f"{self.config['input_port']} ", log, row=1))  # input_port rx
                dev_port1_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port1']} ",  log, row=3))  # dev_port1 tx
                dev_port2_tx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port2']} ",  log, row=3))  # dev_port2 tx
                dev_port3_rx  = int(get_search_context(SPLIT_TYPE1, f"{self.config['dev_port3']} ",  log, row=1))  # dev_port3 rx
                if (input_port_tx > 0 and dev_port3_rx > 0 and abs(dev_port3_rx - input_port_tx) < MIN_DELAY_LIMIT):
                    check = STATUS_OK

                # progress log
                content = "isolated 포트에서 primary 포트로 트래픽이 정상적으로 흐르고 있는가?"
                status  = f"{self.config['dev_port3']}-rxpps={str(dev_port3_rx)}[Primary]"
                status += f"\n{self.config['input_port']}-txpps={str(input_port_tx)}[Isolated]"

        elif action == "private-vlan-unset":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['dev_port1']},{self.config['dev_port2']},{self.config['dev_port3']}"
                vlan = dict()
                for idx, port in enumerate(target_port.split(',')):
                    if port.startswith('ge'):
                        geport = get_search_context(SPLIT_TYPE1, 'SWITCH MODE', log, row=1)
                        vlan[port] = get_search_context(SPLIT_TYPE2, '', geport, row=int(port[2:])-1)
                    elif port.startswith('xg'):
                        xgport = get_search_context(SPLIT_TYPE1, 'SWITCH MODE', log, row=2)
                        vlan[port] = get_search_context(SPLIT_TYPE2, '', xgport, row=int(port[2:])-1)
                    else:
                        break

                if (idx+1) == len(vlan) and len(target_port.split(',')) == len([v for p, v in vlan.items() if v != 'P']):
                    check = STATUS_OK

                content = "private-vlan 해제 후 설정 정보에서 정상적으로 해제되었는가?"
                status  = ', '.join([f"{p}={v}" for p, v in vlan.items()])

            elif self.config_mode == "SHELL":
                target_port = f"{self.config[self.config['input_port']]},{self.config['sdk_port1']},{self.config['sdk_port2']},{self.config['sdk_port3']}"
                ports          = [int(self.config[self.config['input_port']])]
                memps_line     = get_search_context(SPLIT_TYPE0, 'Vlan 100', log, cols=1, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, 'Vlan 100', log, cols=2, row=1)
                vid100_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid100_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)

                ports          = [int(self.config[self.config['input_port']])]
                memps_line     = get_search_context(SPLIT_TYPE0, 'Vlan 200', log, cols=1, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, 'Vlan 200', log, cols=2, row=1)
                vid200_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid200_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)

                ports          = [int(self.config[self.config['input_port']])]
                memps_line     = get_search_context(SPLIT_TYPE0, 'Vlan 300', log, cols=1, row=1)
                untagps_line   = get_search_context(SPLIT_TYPE0, 'Vlan 300', log, cols=2, row=1)
                vid300_memps   = rtk_sdk_parse_match('ports', memps_line,   ports)
                vid300_untagps = rtk_sdk_parse_match('ports', untagps_line, ports)

                dump = int(get_search_context(SPLIT_TYPE1, 'Total Number Of Entries', log, row=1))

                vid100 = get_search_context(SPLIT_TYPE1, f"Port {self.config['sdk_port1']}", log, row=1)
                vid200 = get_search_context(SPLIT_TYPE1, f"Port {self.config['sdk_port2']}", log, row=1)
                vid300 = get_search_context(SPLIT_TYPE1, f"Port {self.config['sdk_port3']}", log, row=1)

                if (vid100_memps == vid100_untagps == vid200_memps == vid200_untagps == vid300_memps == vid300_untagps == False
                    and dump == 0 and vid100 == '100' and vid200 == '200' and vid300 == '300'):
                    check = STATUS_OK

                # progress log
                content = "private-vlan 해제 후 설정 정보에서 정상적으로 해제되었는가?"
                status  = f"vid100-exclude-memports  ={str(not vid100_memps)}"
                status += f"\nvid100-exclude-untagports={str(not vid100_untagps)}"
                status += f"\nvid200-exclude-memports  ={str(not vid200_memps)}"
                status += f"\nvid200-exclude-untagports={str(not vid200_untagps)}"
                status += f"\nvid300-exclude-memports  ={str(not vid300_memps)}"
                status += f"\nvid300-exclude-untagports={str(not vid300_untagps)}"
                status += f"\nentry-count={dump}"
                status += f"\nvid{vid100}=port{self.config['sdk_port1']}"
                status += f"\nvid{vid200}=port{self.config['sdk_port2']}"
                status += f"\nvid{vid300}=port{self.config['sdk_port3']}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_voice_vlan_test_data(self, action=str, log=list, index=0):
        """
        Parse Voice-VLAN test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "voice_vlan_set", "voice_vlan_unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "voice-vlan-set":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                vlan       = get_search_context(SPLIT_TYPE1, "Voice Vlan ID",       log, row=1)
                dscp       = get_search_context(SPLIT_TYPE1, "Voice Vlan DSCP",     log, row=1)
                prio       = get_search_context(SPLIT_TYPE1, "Voice Vlan Priority", log, row=1)
                port       = get_search_context(SPLIT_TYPE2, "Voice Vlan Port",     log, cols=1)
                oui_addr   = get_search_context(SPLIT_TYPE2, "OUI Address",         log, cols=2, row=1)
                oui_mask   = get_search_context(SPLIT_TYPE2, "OUI Mask",            log, cols=2, row=2)
                oui_vender = get_search_context(SPLIT_TYPE2, "Vender",              log, cols=2, row=3)
                if (vlan == self.config['id'] and dscp == self.config['dscp'] and  prio == self.config['prio'] and port == target_port
                    and oui_addr == self.config['oui_addr'] and oui_mask == self.config['oui_mask'] and oui_vender == self.config['oui_vender']):
                    check = STATUS_OK

                content = "voice-vlan 설정 정보가 정상적으로 등록되었는가?"
                status  = f"port={port} voice-vlan={vlan} dscp={dscp} prio={prio}"
                status += f"\noui-addr={oui_addr}"
                status += f"\noui-mask={oui_mask}"
                status += f"\noui-vender={oui_vender}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                if self.config['board_type'] == 'RTL9310':
                    mac0  = get_search_context(SPLIT_TYPE2, f"entry {self.config['st_entry']},", log, cols=2, row=8)
                    mac1  = get_search_context(SPLIT_TYPE2, f"entry {self.config['st_entry']},", log, cols=2, row=9)
                    mac2  = get_search_context(SPLIT_TYPE2, f"entry {self.config['st_entry']},", log, cols=2, row=10)
                    st_oui_addr = f"{mac0}.{mac1}.{mac2}".upper()

                    mac0  = get_search_context(SPLIT_TYPE2, f"entry {self.config['ed_entry']},", log, cols=2, row=8)
                    mac1  = get_search_context(SPLIT_TYPE2, f"entry {self.config['ed_entry']},", log, cols=2, row=9)
                    mac2  = get_search_context(SPLIT_TYPE2, f"entry {self.config['ed_entry']},", log, cols=2, row=10)
                    ed_oui_addr = f"{mac0}.{mac1}.{mac2}".upper()
                else:
                    mac0  = get_search_context(SPLIT_TYPE2, f"entry {self.config['st_entry']},", log, cols=2, row=6)
                    mac1  = get_search_context(SPLIT_TYPE2, f"entry {self.config['st_entry']},", log, cols=2, row=7)
                    mac2  = get_search_context(SPLIT_TYPE2, f"entry {self.config['st_entry']},", log, cols=2, row=8)
                    st_oui_addr = f"{mac0}.{mac1}.{mac2}".upper()

                    mac0  = get_search_context(SPLIT_TYPE2, f"entry {self.config['ed_entry']},", log, cols=2, row=6)
                    mac1  = get_search_context(SPLIT_TYPE2, f"entry {self.config['ed_entry']},", log, cols=2, row=7)
                    mac2  = get_search_context(SPLIT_TYPE2, f"entry {self.config['ed_entry']},", log, cols=2, row=8)
                    ed_oui_addr = f"{mac0}.{mac1}.{mac2}".upper()

                if st_oui_addr == self.config['oui_addr']:
                    oui_addr = st_oui_addr
                    self.config['entry'] = self.config['st_entry']
                elif ed_oui_addr == self.config['oui_addr']:
                    oui_addr = ed_oui_addr
                    self.config['entry'] = self.config['ed_entry']
                else:
                    oui_addr = self.config['default_oui_addr']
                    self.config['entry'] = self.config['st_entry']

                if self.config['board_type'] == 'RTL9310':
                    mask0 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=8)
                    mask1 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=9)
                    mask2 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=10)
                else:
                    mask0 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=6)
                    mask1 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=7)
                    mask2 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=8)

                oui_mask = f"{mask0}.{mask1}.{mask2}".upper()

                if get_search_context(SPLIT_TYPE1, "Inner Priority action state", log[get_idx(f"index {self.config['entry']}", log)[0]:], row=1) == "Enable":
                    prio = get_search_context(SPLIT_TYPE1, "new priority", log[get_idx(f"index {self.config['entry']}", log)[0]:], row=2)

                if get_search_context(SPLIT_TYPE1, "Remark action state", log[get_idx(f"index {self.config['entry']}", log)[0]:], row=1) == "Enable":
                    dscp = get_search_context(SPLIT_TYPE2, "remark DSCP", log[get_idx(f"index {self.config['entry']}", log)[0]:], row=2)

                if oui_addr == self.config['oui_addr'] and oui_mask == self.config['oui_mask'] and prio == self.config['prio'] and dscp == self.config['dscp']:
                    check = STATUS_OK

                content = "acl entry에 voice-vlan 설정 정보가 정상적으로 등록되었는가?"
                status  = f"voice-vlan acl {self.config['acl_phase']} phase {self.config['entry']} entry"
                status += f"\ndscp={dscp} prio={prio}"
                status += f"\noui-addr={oui_addr}"
                status += f"\noui-mask={oui_mask}"

        elif action == "voice-vlan-unset":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                vlan       = get_search_context(SPLIT_TYPE1, "Voice Vlan ID",       log, row=1)
                dscp       = get_search_context(SPLIT_TYPE1, "Voice Vlan DSCP",     log, row=1)
                prio       = get_search_context(SPLIT_TYPE1, "Voice Vlan Priority", log, row=1)
                port       = get_search_context(SPLIT_TYPE2, "Voice Vlan Port",     log, cols=1)
                oui_addr   = get_search_context(SPLIT_TYPE2, "OUI Address",         log, cols=2, row=1)
                oui_mask   = get_search_context(SPLIT_TYPE2, "OUI Mask",            log, cols=2, row=2)
                oui_vender = get_search_context(SPLIT_TYPE2, "Vender",              log, cols=2, row=3)
                if (vlan == "1" and dscp == self.config['default_dscp'] and  prio == self.config['default_prio'] and port == "None"
                    and oui_addr == "" and oui_mask == "" and oui_vender == ""):
                    check = STATUS_OK

                content = "voice-vlan 설정 정보가 정상적으로 해제되었는가?"
                status  = f"port={port} voice-vlan={vlan} dscp={dscp} prio={prio}"
                status += f"\noui-addr={oui_addr if oui_addr != '' else 'Not setting'}"
                status += f"\noui-mask={oui_mask if oui_mask != '' else 'Not setting'}"
                status += f"\noui-vender={oui_vender if oui_vender != '' else 'Not setting'}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                if self.config['board_type'] == 'RTL9310':
                    mac0  = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=2, row=8)
                    mac1  = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=2, row=9)
                    mac2  = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=2, row=10)
                else:
                    mac0  = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=2, row=6)
                    mac1  = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=2, row=7)
                    mac2  = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=2, row=8)

                oui_addr = f"{mac0}.{mac1}.{mac2}".upper()

                if self.config['board_type'] == 'RTL9310':
                    mask0 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=8)
                    mask1 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=9)
                    mask2 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=10)
                else:
                    mask0 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=6)
                    mask1 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=7)
                    mask2 = get_search_context(SPLIT_TYPE2, f"entry {self.config['entry']},", log, cols=3, row=8)

                oui_mask = f"{mask0}.{mask1}.{mask2}".upper()

                prio = get_search_context(SPLIT_TYPE1, "Inner Priority action state", log, row=1)
                dscp = get_search_context(SPLIT_TYPE1, "Remark action state", log, row=1)

                if oui_addr == self.config['default_oui_addr'] and oui_mask == self.config['default_oui_mask'] and prio == dscp == "Disable":
                    check = STATUS_OK

                content = "acl entry에 voice-vlan 설정 정보가 정상적으로 해제되었는가?"
                status  = f"voice-vlan acl {self.config['acl_phase']} phase {self.config['entry']} entry"
                status += f"\ndscp={dscp} prio={prio}"
                status += f"\noui-mask={oui_mask}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])


    @parsing_func_format
    def get_ping_test_data(self, action=str, log=list, index=0):
        """
        Parse Ping test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "ping-set").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "ping-set":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                intf   = get_search_context(SPLIT_TYPE2, "Interface",  log, cols=1, row=0)
                ipaddr = get_search_context(SPLIT_TYPE2, "IP-Address", log, cols=1, row=1)
                stat   = get_search_context(SPLIT_TYPE2, "Status",     log, cols=1, row=2)
                proto  = get_search_context(SPLIT_TYPE2, "Protocol",   log, cols=1, row=3)
                if intf[4:] == self.config['vlan'] and ipaddr == self.config['host_ip'] and stat == "up" and proto == "up":
                    check = STATUS_OK

                content = "vlan 인터페이스에 ip 설정이 정상적으로 등록되었는가?"
                status  = f"interface={intf}\nipaddr={ipaddr}\nstatus={stat}\nprotocol={proto}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                rcvpkt = get_integer_val(get_search_context(SPLIT_TYPE2, "ping statistics", log, cols=1, row=3))
                if rcvpkt == 10:
                    check = STATUS_OK

                content = "ping 10회 시도 시 send, receive 모두 동일한가?"
                status  = f"ping=[10/{rcvpkt}]"

            elif self.config_mode == "NBR1":
                target_port = self.config['(nbr1)nbr_port1']
                intf   = get_search_context(SPLIT_TYPE2, "Interface",  log, cols=1, row=0)
                ipaddr = get_search_context(SPLIT_TYPE2, "IP-Address", log, cols=1, row=1)
                stat   = get_search_context(SPLIT_TYPE2, "Status",     log, cols=1, row=2)
                proto  = get_search_context(SPLIT_TYPE2, "Protocol",   log, cols=1, row=3)
                if intf[4:] == self.config['vlan'] and ipaddr == self.config['neighbor_ip'] and stat == "up" and proto == "up":
                    check = STATUS_OK

                content = "vlan 인터페이스에 ip 설정이 정상적으로 등록해제되었는가?"
                status  = f"interface={intf}\nipaddr={ipaddr}\nstatus={stat}\nprotocol={proto}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_static_route_test_data(self, action=str, log=list, index=0):
        """
        Parse Route test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "route-set", "route-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "route-set":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                intf   = get_search_context(SPLIT_TYPE2, "Interface",  log, cols=1, row=0)
                ipaddr = get_search_context(SPLIT_TYPE2, "IP-Address", log, cols=1, row=1)
                stat   = get_search_context(SPLIT_TYPE2, "Status",     log, cols=1, row=2)
                proto  = get_search_context(SPLIT_TYPE2, "Protocol",   log, cols=1, row=3)
                route  = get_search_context(SPLIT_TYPE2, "S*",         log, row=1)
                gwip   = get_search_context(SPLIT_TYPE2, "S*",         log, row=4)
                vlan   = get_search_context(SPLIT_TYPE2, "S*",         log, row=5)
                if (route == f"{self.config['route_ip']}/{self.config['route_ip_prefix']}"
                    and gwip == self.config['gatewayip']
                    and vlan[4:] == self.config['vlan']
                    and intf[4:] == self.config['vlan']
                    and ipaddr == self.config['host_ip']
                    and stat == "up" and proto == "up"):
                    check = STATUS_OK

                content = "vlan 인터페이스에 ip 설정이 정상적으로 등록되었는가?"
                status  = f"interface={intf}\nipaddr={ipaddr}\nstatus={stat}\nprotocol={proto}"
                status += f"\nrouteip={route}\ngwip={gwip}\nroute-interface={vlan}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                rcvpkt  = get_integer_val(get_search_context(SPLIT_TYPE2, "ping statistics", log, cols=1, row=3))
                hostip  = get_search_context(SPLIT_TYPE2, self.config['host_ip'], log, row=2)
                mask    = apply_prefix(self.config['gatewayip'], int(self.config['host_ip_prefix']))
                routeip = get_search_context(SPLIT_TYPE2, mask, log, row=2)
                if rcvpkt == 10 and hostip == self.config['host_ip'] and routeip == mask:
                    check = STATUS_OK

                content = "ping 10회 시도 시 send, receive 모두 동일한가?\nstatic route설정이 정상적으로 등록되었는가?"
                status  = f"ping=[10/{rcvpkt}]\nhost-ip-dump={hostip}\nroute-ip-dump={routeip}"

        elif action == "route-unset":
            if self.config_mode == "CLI":
                target_port = self.config['dev_port1']
                intf   = get_search_context(SPLIT_TYPE2, "Interface",  log, cols=1, row=0)
                ipaddr = get_search_context(SPLIT_TYPE2, "IP-Address", log, cols=1, row=1)
                stat   = get_search_context(SPLIT_TYPE2, "Status",     log, cols=1, row=2)
                proto  = get_search_context(SPLIT_TYPE2, "Protocol",   log, cols=1, row=3)
                route  = get_search_context(SPLIT_TYPE2, "S*",         log)
                if route == "" and intf[4:] == self.config['vlan'] and ipaddr == "unassigned" and stat == "up" and proto == "down":
                    check = STATUS_OK

                content = "vlan 인터페이스에 ip 설정이 정상적으로 해제되었는가?"
                status  = f"intf={intf}\nipaddr={ipaddr}\nstatus={stat}\nprotocol={proto}\nrouteip={route if route != '' else 'Not setting'}"

            elif self.config_mode == "SHELL":
                target_port = self.config['sdk_port1']
                connect = get_search_context(SPLIT_TYPE1, "Network is unreachable", log, row=1)
                if connect == "": connect = "network still alive!"
                hostip  = get_search_context(SPLIT_TYPE2, self.config['host_ip'], log, row=2)
                if hostip == "": hostip = "Not setting"
                mask    = apply_prefix(self.config['gatewayip'], int(self.config['host_ip_prefix']))
                routeip = get_search_context(SPLIT_TYPE2, mask, log, row=2)
                if routeip == "": routeip = "Not setting"

                if connect != "" and hostip == "Not setting" and routeip == "Not setting":
                    check = STATUS_OK

                content = "ping 10회 시도 시 not search 에러가 발생하는가?\nl3 dump 테이블에 host ip 및 route ip 정보가 정상적으로 해제되었는가?"
                status  = f"network={connect}\nhost-ip-dump={hostip}\nroute-ip-dump={routeip}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_igmp_snooping_test_data(self, action=str, log=list, index=0):
        """
        Parse IGMP snooping test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "igmp-snooping-set", "igmp-group-mac-show", "igmp-group-timeout", "igmp-snooping-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "igmp-snooping-set":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['output_port']}"
                mrouter = get_search_context(SPLIT_TYPE2, "VLAN 1", log, row=1)
                mport   = get_search_context(SPLIT_TYPE2, "Mrouter", log, row=1)
                if (mrouter == '1') and (mport == self.config['input_port']):
                    check = STATUS_OK

                content = "Mrouter 설정이 정상적으로 등록되었는가?"
                status  = f"mroute vlan={mrouter}, mroute interface={mport}"

        elif action == "igmp-group-mac-show":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['output_port']}"
                input_mac  = get_idx(f"{self.config['input_port']} | 0100.5e00.", log)
                output_mac = get_idx(f"{self.config['output_port']} | 0100.5e00.", log)
                group_ip   = get_idx(f"224.0.1.", log)
                if len(input_mac) == len(output_mac) == len(group_ip) == 10:
                    check = STATUS_OK

                content = "IGMP query 및 report 패킷의 Mac주소가 Mac table에 등록되어 있는가?"
                content += "\nIGMP query 및 report 패킷의 group주소가 group Membership에 등록되어 있는가?"
                status  = f"IGMP Query side Mac table=[10/{len(input_mac)}]"
                status += f"\nIGMP Report side Mac table=[10/{len(output_mac)}]"
                status += f"\nIGMP Group Membership=[10/{len(group_ip)}]"

            elif self.config_mode == "SHELL":
                target_port = f"{self.config[self.config['input_port']]},{self.config[self.config['output_port']]}"
                mmac_list    = get_idx(f"01:00:5E:00:", log)
                mports_list  = get_search_context(SPLIT_TYPE1, "01:00:5E:00:", log, row=3)
                mports_check = rtk_sdk_parse_match('ports', mports_list, [int(port) for port in target_port.split(',')])
                if len(mmac_list) == 10 and mports_check == True:
                    check = STATUS_OK

                content = "l2 table에 IGMP Multicast 패킷 Mac이 정상적으로 등록되어있는가?"
                status  = f"등록된 IGMP Mac=[10/{len(mmac_list)}], Ports={mports_list}"

        elif action == "igmp-group-timeout":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['output_port']}"
                group_mac = get_idx(f"{self.config['output_port']} | 0100.5e00.", log)
                group_ip  = get_idx(f"224.0.1.", log)
                if len(group_mac) == len(group_ip) == 0:
                    check = STATUS_OK

                content = "Group Membership timeout 이후 Mac table에서 IGMP Mac이 등록해제되었는가?"
                content += "\nGroup Membership timeout 이후 group정보에 join이 등록해제되었는가?"
                status  = f"Mac table=[10/{len(group_mac)}]"
                status += f"\nIGMP Group Membership=[10/{len(group_ip)}]"

        elif action == "igmp-snooping-unset":
            if self.config_mode == "CLI":
                target_port = f"{self.config['input_port']},{self.config['output_port']}"
                mac     = get_idx("0100.5e00.", log)
                mrouter = get_search_context(SPLIT_TYPE2, "VLAN 1", log, row=1)
                if mrouter == "": mrouter = 'Not Setting'
                mport   = get_search_context(SPLIT_TYPE2, "Mrouter", log, row=1)
                if mport == "": mport = 'Not Setting'

                if (len(mac) == 0 and mrouter == mport == 'Not Setting'):
                    check = STATUS_OK

                content = "Mrouter 설정이 정상적으로 등록해제되었는가?"
                status  = f"mroute vlan={mrouter}, mroute interface={mport}"
                status += f"\nMac table=[10/{len(mac)}]"

            elif self.config_mode == "SHELL":
                target_port = f"{self.config[self.config['input_port']]},{self.config[self.config['output_port']]}"
                mmac_list    = get_idx(f"01:00:5E:00:", log)
                mports_list  = get_search_context(SPLIT_TYPE1, "01:00:5E:00:", log, row=3)
                if len(mmac_list) == 0:
                    check = STATUS_OK

                content = "l2 table에 IGMP Multicast 패킷 Mac이 정상적으로 등록해제되어있는가?"
                status  = f"등록된 IGMP Mac=[10/{len(mmac_list)}]"

        else:
            return

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_l2_smoke_test_data(self, action=str, log=list, index=0):
        """
        Parse IGMP & STP & LACP composite test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "root-bridge-set1", "non-root-bridge-set", "root-bridge-set2", "port-priority-set1", "port-priority-set2", "port-cost-set1", "port-cost-set2", "port-failover1", "port-failover2", "igmp-group-show").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        config = f"({self.config_mode.lower()})" if self.config_mode != 'CLI' else ""

        if action == "root-bridge-set1":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port4']
            content    = "[A장비 확인] rpvst+ 설정 후 A장비 priority를 낮게 변경한 후 A장비가 root-bridge로 변경되었는가?"

        elif action == "non-root-bridge-set":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = None
            content    = "[A장비 확인] rpvst+ 설정 후 A장비 priority를 높게 변경한 후 A장비가 Non-root-bridge로 변경되었는가?"

        elif action == "root-bridge-set2":
            port1      = 'agg1'
            agg_port1  = self.config[config+'nbr_port1']
            agg_port2  = self.config[config+'nbr_port2']
            port2      = self.config[config+'nbr_port3']
            port3      = 'agg2'
            txrx_port1 = 'agg2'
            txrx_port2 = None
            content    = "[B장비 확인] rpvst+ 설정 후 B장비 priority를 낮게 변경한 후 B장비가 root-bridge로 변경되었는가?"

        elif action == "port-priority-set1":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = 'agg1'
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 priority 변경 후 A장비 루트포트가 P1({port1})으로 변경되었는가?"

        elif action == "port-priority-set2":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port3']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 priority 변경 후 A장비 루트포트가 P2({port2})으로 변경되었는가?"

        elif action == "port-cost-set1":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = 'agg1'
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 cost 변경 후 A장비 루트포트가 P1({port1})으로 변경되었는가?"

        elif action == "port-cost-set2":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port3']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 cost 변경 후 A장비 루트포트가 P2({port2})으로 변경되었는가?"

        elif action == "port-failover1":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = 'agg1'
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 P2({port2})포트 절체 후 A장비 루트포트가 P1({port1})으로 변경되었는가?"

        elif action == "port-failover2":
            port1      = 'agg1'
            agg_port1  = self.config[config+'dev_port1']
            agg_port2  = self.config[config+'dev_port2']
            port2      = self.config[config+'dev_port3']
            port3      = self.config[config+'dev_port4']
            txrx_port1 = self.config[config+'input_port']
            txrx_port2 = self.config[config+'dev_port4']
            content    = f"[A장비 확인] rpvst+ 설정 후 B장비(root)의 포트 P2({port1})포트 추가 절체 후 A장비 루트포트가 P3({port3})으로 변경되었는가?"

        elif action == "igmp-group-show":
            port1      = 'agg1'
            agg_port1  = self.config[config+'nbr_port1']
            agg_port2  = self.config[config+'nbr_port2']
            port2      = self.config[config+'nbr_port3']
            port3      = 'agg2'
            txrx_port1 = self.config[config+'input_port']
            content    = f"[B장비 확인]  \"{self.config['pre-action']}\"에서 변경된 망에서 B장비의 Mroute 포트와 Membership 포트가 맞는가?"
            content   += f"\n[B장비 확인] \"{self.config['pre-action']}\"에서 변경된 망에서 B장비의 Mac table에 Membership 패킷이 모두 등록되어 있는가?"

        else:
            return

        target_port = f"{txrx_port1},{port1},{port2},{port3}"

        if action == 'igmp-group-show':
            if self.config['pre-action'] == 'root-bridge-set1':
                mroute_p = mjoin_p = port1
            elif self.config['pre-action'] == 'non-root-bridge-set':
                mroute_p = port1
                mjoin_p  = port3
            elif self.config['pre-action'] == 'root-bridge-set2':
                mroute_p = port1
                mjoin_p  = port3
            elif self.config['pre-action'] == 'port-priority-set1':
                mroute_p = port1
                mjoin_p  = port3
            elif self.config['pre-action'] == 'port-priority-set2':
                mroute_p = port2
                mjoin_p  = port3
            elif self.config['pre-action'] == 'port-cost-set1':
                mroute_p = port1
                mjoin_p  = port3
            elif self.config['pre-action'] == 'port-cost-set2':
                mroute_p = port2
                mjoin_p  = port3
            elif self.config['pre-action'] == 'port-failover1':
                mroute_p = port1
                mjoin_p  = port3
            elif self.config['pre-action'] == 'port-failover2':
                mroute_p = mjoin_p = port3

            mrouter = get_search_context(SPLIT_TYPE2, f"Mrouter--> {mroute_p}", log, row=1)
            mgroup  = 0
            for mc in get_idx("224.0.1.", log):
                mjoin = get_search_context(SPLIT_TYPE2, f"{mjoin_p}", log[int(mc)], row=1)
                if mjoin != "": mgroup += 1

            mmac    = 0
            for mc in get_idx("0100.5e00.", log):
                mjoin = get_search_context(SPLIT_TYPE2, f"{mjoin_p}", log[int(mc)], row=1)
                if mjoin != "": mmac += 1

            if mrouter == mroute_p and mgroup == 10 and mmac == 10:
                check = STATUS_OK

            status  = f"Mroute={mrouter}"
            status += f"\nMembership={mjoin_p}, Membership-group=[10/{mgroup}], Membership-mac=[10/{mmac}]"

        else:
            self.config['pre-action'] = action

            stp_info = False
            stp_stat = False

            rootport = get_search_context(SPLIT_TYPE2, "root port", log, row=2)
            cost     = get_search_context(SPLIT_TYPE2, "root port", log, row=6)
            # spanning-tree info port1
            p1_cost  = get_search_context(SPLIT_TYPE2, f"{port1}:", log, row=6)
            if p1_cost == '': p1_cost = 'None'
            p1_role  = get_search_context(SPLIT_TYPE2, f"{port1}:", log, row=9)
            if p1_role == '': p1_role = 'None'
            p1_stat  = get_search_context(SPLIT_TYPE2, f"{port1}:", log, row=11)
            if p1_stat == '': p1_stat = 'None'

            # spanning-tree info port2
            p2_cost  = get_search_context(SPLIT_TYPE2, f"{port2}:", log, row=6)
            if p2_cost == '': p2_cost = 'None'
            p2_role  = get_search_context(SPLIT_TYPE2, f"{port2}:", log, row=9)
            if p2_role == '': p2_role = 'None'
            p2_stat  = get_search_context(SPLIT_TYPE2, f"{port2}:", log, row=11)
            if p2_stat == '': p2_stat = 'None'

            # spannig-tree info port3
            p3_cost  = get_search_context(SPLIT_TYPE2, f"{port3}:", log, row=6)
            if p3_cost == '': p3_cost = 'None'
            p3_role  = get_search_context(SPLIT_TYPE2, f"{port3}:", log, row=9)
            if p3_role == '': p3_role = 'None'
            p3_stat  = get_search_context(SPLIT_TYPE2, f"{port3}:", log, row=11)
            if p3_stat == '': p3_stat = 'None'

            if action == "root-bridge-set1" or action == "root-bridge-set2":
                if (rootport == '---' and cost == '0'
                    and p1_cost == '20000' and p1_role == 'Designated' and p1_stat == 'Forwarding'
                    and p2_cost == '20000' and p2_role == 'Designated' and p2_stat == 'Forwarding'
                    and p3_cost == '20000' and p3_role == 'Designated' and p3_stat == 'Forwarding'):
                    stp_info = True
            elif action == "non-root-bridge-set":
                if rootport == port1:
                    self.config['rootport'] = 'agg1'
                    if (p1_cost == '20000'     and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                        and p2_cost == '20000' and p2_role == 'Alternate'  and p2_stat == 'Discarding'
                        and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                        stp_info = True
                elif rootport == port2:
                    self.config['rootport'] = 'nbr_port3'
                    if (p1_cost == '20000'     and p1_role == 'Alternate'  and p1_stat == 'Discarding'
                        and p2_cost == '20000' and p2_role == 'Rootport'   and p2_stat == 'Forwarding'
                        and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                        stp_info = True
            elif action == "port-priority-set1":
                if (rootport == port1 and cost == '20000'
                    and p1_cost == '20000' and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                    and p2_cost == '20000' and p2_role == 'Alternate'  and p2_stat == 'Discarding'
                    and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                    stp_info = True
            elif action == "port-priority-set2":
                if (rootport == port2 and cost == '20000'
                    and p1_cost == '20000' and p1_role == 'Alternate'  and p1_stat == 'Discarding'
                    and p2_cost == '20000' and p2_role == 'Rootport'   and p2_stat == 'Forwarding'
                    and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                    stp_info = True
            elif action == "port-cost-set1":
                if (rootport == port1 and cost == '15000'
                    and p1_cost == '15000' and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                    and p2_cost == '20000' and p2_role == 'Alternate'  and p2_stat == 'Discarding'
                    and p3_cost == '20000' and p3_role == 'Designated' and p3_stat == 'Forwarding'):
                    stp_info = True
            elif action == "port-cost-set2":
                if (rootport == port2 and cost == '20000'
                    and p1_cost == '25000' and p1_role == 'Alternate'  and p1_stat == 'Discarding'
                    and p2_cost == '20000' and p2_role == 'Rootport'   and p2_stat == 'Forwarding'
                    and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                    stp_info = True
            elif action == "port-failover1":
                if (rootport == port1 and cost == '25000'
                    and p1_cost == '25000' and p1_role == 'Rootport'   and p1_stat == 'Forwarding'
                    and p2_cost == 'None'  and p2_role == 'None'       and p2_stat == 'None'
                    and p3_cost == '20000' and p3_role == 'Alternate'  and p3_stat == 'Discarding'):
                    stp_info = True
            elif action == "port-failover2":
                if (rootport == port3 and cost == '40000'
                    and p1_cost == 'None'  and p1_role == 'None'       and p1_stat == 'None'
                    and p2_cost == 'None'  and p2_role == 'None'       and p2_stat == 'None'
                    and p3_cost == '20000' and p3_role == 'Rootport'   and p3_stat == 'Forwarding'):
                    stp_info = True

            if self.config_mode == "NBR1":
                modelname = self.config['nbr1_model']
                if txrx_port2 == None and rootport == '---':
                    if self.config['rootport'] == 'agg1':
                        txrx_port2 = 'agg1'
                        if index == 0:
                            agg_port1 = self.config['(nbr1)dev_port1']
                            agg_port2 = self.config['(nbr1)dev_port2']
                        else:
                            agg_port1 = self.config['(nbr1)nbr_port1']
                            agg_port2 = self.config['(nbr1)nbr_port2']
                    else:
                        if self.config['rootport'] in self.config:
                            txrx_port2 = self.config['(nbr1)'+self.config['rootport']]
                        else:
                            txrx_port2 = 'agg1'
                            agg_port1 = self.config[config+'dev_port1']
                            agg_port2 = self.config[config+'dev_port2']

            elif self.config_mode == "NBR2":
                modelname = self.config['nbr2_model']
                if txrx_port2 == None and rootport == '---':
                    if self.config['rootport'] == 'agg1':
                        txrx_port2 = 'agg1'
                        if index == 0:
                            agg_port1 = self.config['(nbr2)dev_port1']
                            agg_port2 = self.config['(nbr2)dev_port2']
                        else:
                            agg_port1 = self.config['(nbr2)nbr_port1']
                            agg_port2 = self.config['(nbr2)nbr_port2']
                    else:
                        if self.config['rootport'] in self.config:
                            txrx_port2 = self.config['(nbr2)'+self.config['rootport']]
                        else:
                            txrx_port2 = 'agg1'
                            agg_port1 = self.config[config+'dev_port1']
                            agg_port2 = self.config[config+'dev_port2']

            else:
                modelname = self.config['host_model']
                if txrx_port2 == None and rootport == '---':
                    if self.config['rootport'] == 'agg1':
                        txrx_port2 = 'agg1'
                        if index == 0:
                            agg_port1 = self.config['dev_port1']
                            agg_port2 = self.config['dev_port2']
                        else:
                            agg_port1 = self.config['nbr_port1']
                            agg_port2 = self.config['nbr_port2']
                    else:
                        if self.config['rootport'] in self.config:
                            txrx_port2 = self.config[self.config['rootport']]
                        else:
                            txrx_port2 = 'agg1'
                            agg_port1 = self.config[config+'dev_port1']
                            agg_port2 = self.config[config+'dev_port2']

            if txrx_port2 == None and rootport != '---':
                if rootport == 'agg1':
                    txrx_port2 = 'agg1'
                    if index == 0:
                        agg_port1 = self.config[config+'dev_port1']
                        agg_port2 = self.config[config+'dev_port2']
                    else:
                        agg_port1 = self.config[config+'nbr_port1']
                        agg_port2 = self.config[config+'nbr_port2']
                else:
                    txrx_port2 = rootport

            if txrx_port2 == port1:
                pos   = 'P1'
                state = p1_stat
            elif txrx_port2 == port2:
                pos   = 'P2'
                state = p2_stat
            elif txrx_port2 == port3:
                pos   = 'P3'
                state = p3_stat
            else:
                pos = state = 'unKnown'

            # spanning-tree port-monitoring pkt statistic
            if p1_stat == 'Discarding':
                if port1 == 'agg1':
                    agg_tx =  int(get_search_context(SPLIT_TYPE1, f"{agg_port1} |", log, row=3))
                    agg_tx += int(get_search_context(SPLIT_TYPE1, f"{agg_port2} |", log, row=3))
                    p1_pktdis_tx = agg_tx
                else:
                    p1_pktdis_tx = int(get_search_context(SPLIT_TYPE1, f"{port1} |", log, row=3))
            else:
                p1_pktdis_tx = -1

            if p2_stat == 'Discarding':
                if port2 == 'agg1':
                    agg_tx =  int(get_search_context(SPLIT_TYPE1, f"{agg_port1} |", log, row=3))
                    agg_tx += int(get_search_context(SPLIT_TYPE1, f"{agg_port2} |", log, row=3))
                    p2_pktdis_tx = agg_tx
                else:
                    p2_pktdis_tx = int(get_search_context(SPLIT_TYPE1, f"{port2} |", log, row=3))
            else:
                p2_pktdis_tx = -1

            if p3_stat == 'Discarding':
                if port3 == 'agg1':
                    agg_tx =  int(get_search_context(SPLIT_TYPE1, f"{agg_port1} |", log, row=3))
                    agg_tx += int(get_search_context(SPLIT_TYPE1, f"{agg_port2} |", log, row=3))
                    p3_pktdis_tx = agg_tx
                else:
                    p3_pktdis_tx = int(get_search_context(SPLIT_TYPE1, f"{port3} |", log, row=3))
            else:
                p3_pktdis_tx = -1

            if txrx_port1 == 'agg1':
                in_agg_pkt_rx1 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'nbr_port1']} |", log, row=1))
                in_agg_pkt_tx1 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'nbr_port1']} |", log, row=3))
                in_agg_pkt_rx2 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'nbr_port2']} |", log, row=1))
                in_agg_pkt_tx2 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'nbr_port2']} |", log, row=3))
                in_pkt_rx = in_agg_pkt_rx1 + in_agg_pkt_rx2
                in_pkt_tx = in_agg_pkt_tx1 + in_agg_pkt_tx2
            elif txrx_port1 == 'agg2':
                in_agg_pkt_rx1 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'dev_port1']} |", log, row=1))
                in_agg_pkt_tx1 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'dev_port1']} |", log, row=3))
                in_agg_pkt_rx2 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'dev_port2']} |", log, row=1))
                in_agg_pkt_tx2 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'dev_port2']} |", log, row=3))
                in_agg_pkt_rx3 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'dev_port3']} |", log, row=1))
                in_agg_pkt_tx3 = int(get_search_context(SPLIT_TYPE1, f"{self.config[config+'dev_port3']} |", log, row=3))
                in_pkt_rx = in_agg_pkt_rx1 + in_agg_pkt_rx2 + in_agg_pkt_rx3
                in_pkt_tx = in_agg_pkt_tx1 + in_agg_pkt_tx2 + in_agg_pkt_tx3
            else:
                in_pkt_rx = int(get_search_context(SPLIT_TYPE1, f"{txrx_port1} |", log, row=1))
                in_pkt_tx = int(get_search_context(SPLIT_TYPE1, f"{txrx_port1} |", log, row=3))
    
            if txrx_port2 == 'agg1':
                agg_pkt_rx1 = int(get_search_context(SPLIT_TYPE1, f"{agg_port1} |", log, row=1))
                agg_pkt_tx1 = int(get_search_context(SPLIT_TYPE1, f"{agg_port1} |", log, row=3))
                agg_pkt_rx2 = int(get_search_context(SPLIT_TYPE1, f"{agg_port2} |", log, row=1))
                agg_pkt_tx2 = int(get_search_context(SPLIT_TYPE1, f"{agg_port2} |", log, row=3))
                p_pkt_rx = agg_pkt_rx1 + agg_pkt_rx2
                p_pkt_tx = agg_pkt_tx1 + agg_pkt_tx2
            else:
                p_pkt_rx    = int(get_search_context(SPLIT_TYPE1, f"{txrx_port2} |", log, row=1))
                p_pkt_tx    = int(get_search_context(SPLIT_TYPE1, f"{txrx_port2} |", log, row=3))

            pkt_delay = abs(in_pkt_rx - p_pkt_tx)
            if (in_pkt_rx > 0 and p_pkt_tx > 0
                and pkt_delay < MIN_DELAY_LIMIT
                and p1_pktdis_tx <= AGG_2PORT_PERIOD
                and p2_pktdis_tx <= AGG_2PORT_PERIOD
                and p3_pktdis_tx <= AGG_2PORT_PERIOD):
                stp_stat = True

            if stp_info == stp_stat == True:
                check = STATUS_OK

            status  = "* rpvst+ info"
            status += f"\n  Spanning-tree: model={modelname}, rootport={rootport}, cost={cost}"
            status += f"\n  {port1:<4}: pos=P1, cost={p1_cost:<5}, role={p1_role:<10}, state={p1_stat}"
            status += f"\n  {port2:<4}: pos=P2, cost={p2_cost:<5}, role={p2_role:<10}, state={p2_stat}"
            status += f"\n  {port3:<4}: pos=P3, cost={p3_cost:<5}, role={p3_role:<10}, state={p3_stat}"
            status += "\n* rpvst+ statistics"
            status += f"\n  {txrx_port1:<4}: pos=TC, state=FWD, rxpps={in_pkt_rx:<5}"
            status += f"\n  {txrx_port2:<4}: pos={pos}, state={state}, txpps={p_pkt_tx}"
            if p1_stat == 'Discarding':
                status += f"\n  {port1:<4}: pos=P1, state=DIS, txpps={p1_pktdis_tx}"
                if port1.startswith('agg'): status += f" (≤{AGG_2PORT_PERIOD}pps :agg-period-tx)"
            if p2_stat == 'Discarding':
                status += f"\n  {port2:<4}: pos=P2, state=DIS, txpps={p2_pktdis_tx}"
                if port2.startswith('agg'): status += f" (≤{AGG_2PORT_PERIOD}pps :agg-period-tx)"
            if p3_stat == 'Discarding':
                status += f"\n  {port3:<4}: pos=P3, state=DIS, txpps={p3_pktdis_tx}"
                if port3.startswith('agg'): status += f" (≤{AGG_2PORT_PERIOD}pps :agg-period-tx)"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_mac_table_test_data(self, action=str, log=list, index=0):
        """
        Parse Mac-Table test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "mac-table-set").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "mac-table-set":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']
                curr_cnt = len([mac for mac in get_idx('0010.94', log) if mac != ''])
                if int(self.config['max_addr']) == curr_cnt:
                    check = STATUS_OK

                content = "mac-table에 tc에서 생성한 패킷의 mac주소가 모두 등록이 되었는가?"
                status  = f"Mac-table=[{self.config['max_addr']}/{curr_cnt}]"

            elif self.config_mode == "SHELL":
                target_port = self.config['in_sdk_port']
                curr_cnt = len([mac for mac in get_idx('00:10:94', log) if mac != ''])
                if int(self.config['max_addr']) == curr_cnt:
                    check = STATUS_OK

                content = "mac-table에 tc에서 생성한 패킷의 mac주소가 모두 등록이 되었는가?"
                status  = f"Mac-table=[{self.config['max_addr']}/{curr_cnt}]"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_mac_addr_limit_test_data(self, action=str, log=list, index=0):
        """
        Parse Mac-Address-Limit test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "mac-addr-limit-set").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "mac-addr-limit-set":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']

                mac_list = [get_search_context(SPLIT_TYPE1, f"{target_port}", log[idx], row=3) for idx in get_idx(f"|   {target_port:>4} |", log)]
                if len(mac_list) == int(self.config['limit']):
                    check = STATUS_OK

                content = "mac-table에 tc에서 생성한 패킷의 mac주소가 limit값만큼 등록이 되었는가?"
                status  = f"Mac-table=[{self.config['limit']}/{len(mac_list)}]"

            elif self.config_mode == "SHELL":
                target_port = self.config['in_sdk_port']

                max_mac_cnt = get_search_context(SPLIT_TYPE1, "Max Mac Count",           log, row=1)
                cur_mac_cnt = get_search_context(SPLIT_TYPE1, "Current Mac Count",       log, row=1)
                max_cnt_act = get_search_context(SPLIT_TYPE1, "Exceed Max Count Action", log, row=1)
                mac_list    = [get_search_context(SPLIT_TYPE1, f"{target_port} |", log[idx], row=2) for idx in get_idx(f"00:10:94:", log)]
                if (max_mac_cnt == self.config['limit']
                    and cur_mac_cnt == self.config['limit']
                    and max_cnt_act == "Drop"
                    and len(mac_list) == int(self.config['limit'])):
                    check = STATUS_OK

                content = "l2 table에 limit값이 정상적으로 등록되었는가?"
                status  = f"max-mac-cnt={max_mac_cnt}\ncurr-mac-cnt={cur_mac_cnt}\nmax-cnt-act={max_cnt_act}\nl2-table=[{self.config['limit']}/{len(mac_list)}]"

        elif action == "mac-addr-limit-unset":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']

                mac_list = [get_search_context(SPLIT_TYPE1, f"{target_port}", log[idx], row=3) for idx in get_idx("0010.94", log)]
                if len(mac_list) > int(self.config['limit']):
                    check = STATUS_OK

                content = "unlimit 후 mac-table에 tc에서 생성한 패킷의 mac주소가 모두 등록이 되었는가?"
                status  = f"Mac-table num={len(mac_list)}"

            elif self.config_mode == "SHELL":
                target_port = self.config['in_sdk_port']

                mac_list = [get_search_context(SPLIT_TYPE1, f"{target_port}", log[idx], row=2) for idx in get_idx("00:10:94:", log)]
                if len(mac_list) > int(self.config['limit']):
                    check = STATUS_OK

                content = "l2 table에 tc에서 생성한 패킷의 mac주소가 모두 등록이 되었는가?"
                status  = f"L2-table num={len(mac_list)}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_static_mac_addr_test_data(self, action=str, log=list, index=0):
        """
        Parse Static-Mac-Address test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "forward-set", "discard-set", "static-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "forward-set":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']
                act    = get_search_context(SPLIT_TYPE1, f"| {self.config['cli_static']}", log, row=4)
                static = get_search_context(SPLIT_TYPE1, f"| {self.config['cli_static']}", log, row=5)
                if act == "FORWARD" and static == "STATIC":
                    check = STATUS_OK

                content = f"'{self.config['cli_static']}'주소가 static forward로 Mac-table에 등록되었는가?"
                status  = f"act={act}, mac-table={static}"

            elif self.config_mode == "SHELL":
                target_port = self.config['in_sdk_port']
                static = get_search_context(SPLIT_TYPE1, self.config['sdk_static'], log, row=8)
                sblk   = get_search_context(SPLIT_TYPE1, self.config['sdk_static'], log, row=6)
                if static == '1' and sblk == '0':
                    check = STATUS_OK

                content = f"'{self.config['sdk_static']}'주소가 static forward로 l2테이블에  등록되었는가?"
                status  = f"l2dump={static}, srcblk={sblk}"

        elif action == "discard-set":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']
                act    = get_search_context(SPLIT_TYPE1, f"| {self.config['cli_static']}", log, row=4)
                static = get_search_context(SPLIT_TYPE1, f"| {self.config['cli_static']}", log, row=5)
                if act == "DISCARD" and static == "STATIC":
                    check = STATUS_OK

                content = f"'{self.config['cli_static']}'주소가 static discard로 Mac-table에 등록되었는가?"
                status  = f"act={act}, mac-table={static}"

            elif self.config_mode == "SHELL":
                target_port = self.config['in_sdk_port']
                static = get_search_context(SPLIT_TYPE1, self.config['sdk_static'], log, row=8)
                sblk   = get_search_context(SPLIT_TYPE1, self.config['sdk_static'], log, row=6)
                if static == '1' and sblk == '1':
                    check = STATUS_OK

                content = f"'{self.config['sdk_static']}'주소가 static discard로 l2테이블에  등록되었는가?"
                status  = f"l2dump={static}, srcblk={sblk}"

        elif action == "static-unset":
            if self.config_mode == "CLI":
                target_port = get_search_context(SPLIT_TYPE1, f"| {self.config['cli_static']}", log, row=2)
                act         = get_search_context(SPLIT_TYPE1, f"| {self.config['cli_static']}", log, row=4)
                static      = get_search_context(SPLIT_TYPE1, f"| {self.config['cli_static']}", log, row=5)
                if static == "": static = 'Not setting'
                if act == "FORWARD" and static == 'Not setting':
                    check = STATUS_OK

                content = f"'{self.config['cli_static']}'주소의 static 설정이 Mac테이블에서 해제되었는가?"
                status  = f"act={act}, mac-table={static}"

            elif self.config_mode == "SHELL":
                target_port = self.config['in_sdk_port']
                static = get_search_context(SPLIT_TYPE1, self.config['cli_static'], log, row=5)
                if static == "":
                    static = "Not setting"
                    check = STATUS_OK

                content = f"'{self.config['sdk_static']}'주소의 static 설정이 l2테이블에서 해제되었는가?"
                status  = f"l2dump={static}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_mac_agging_test_data(self, action=str, log=list, index=0):
        """
        Parse Mac-Agging-Time test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "ageing-time-set", "ageing-time-unset").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        if action == "ageing-time-show":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']
                mac_list    = get_idx(f"{self.config['input_port']} | 0010.94", log)
                if len(mac_list) == int(self.config['max_addr']):
                    check = STATUS_OK

                content = "Ageing-time 적용 전 mac-table에 mac이 정상적으로 등록되어 있는가?"
                status  = f"Mac-table=[{self.config['max_addr']}/{len(mac_list)}]"

        elif action == "ageing-time-set":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']
                time     = get_search_context(SPLIT_TYPE2, "show mac-table", log, cols=1, row=1)
                mac_list = get_idx(f"{self.config['input_port']} | 0010.94", log)
                if time == self.config['ageing_time'] and len(mac_list) == 0:
                    check = STATUS_OK

                content = f"Ageing-time 설정 값 {self.config['ageing_time']}이 정상적으로 등록되었는가?\nAgeing-time 이후 Mac-table에 mac이 남아있는가?"
                status  = f"set-time={time}, After {time} delay Mac-table=[{self.config['max_addr']}/{len(mac_list)}]"

            elif self.config_mode == "SHELL":
                target_port = self.config['input_port']
                time = get_search_context(SPLIT_TYPE1, "Aging Time", log, row=1)
                if time == f"{self.config['ageing_time']} seconds.":
                    check = STATUS_OK

                content = f"Aging-time 설정 값 {self.config['ageing_time']}이 정상적으로 등록되었는가?"
                status  = f"set-time={time}"

        elif action == "ageing-time-unset":
            if self.config_mode == "CLI":
                target_port = self.config['input_port']
                time     = get_search_context(SPLIT_TYPE2, "show mac-table", log, cols=1, row=1)
                mac_list = get_idx(f"{self.config['input_port']} | 0010.94", log)
                if time == self.config['default_ageing_time'] and len(mac_list) == int(self.config['max_addr']):
                    check = STATUS_OK

                content = "Aging-time 설정 값이 정상적으로 해제되었는가?\n이후 Mac-table에 mac이 정상적으로 등록되었는가?"
                status  = f"set-time={time}, Mac-table=[{self.config['max_addr']}/{len(mac_list)}]"

            elif self.config_mode == "SHELL":
                target_port = self.config['input_port']
                time = get_search_context(SPLIT_TYPE1, "Aging Time", log, row=1)
                if time == f"{self.config['default_ageing_time']} seconds.":
                    check = STATUS_OK

                content = "Aging-time 설정 값이 정상적으로 해제되었는가?"
                status  = f"set-time={time}"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

    @parsing_func_format
    def get_arp_test_data(self, action=str, log=list, index=0):
        """
        Parse ARP test data based on the specified action.

        Parameters:
        - action: The action to perform (e.g., "arp-set", "arp-set-show", "arp-unset", "arp-unset-show").
        - log: The log data to parse.
        - index: The index to retrieve data from the log.

        Returns:
        None
        """
        check = STATUS_FAIL

        target_port = self.config['input_port']
        if action == "arp-dynamic":
            arp_list = get_idx(f"{self.config['cdynamic_mac']}", log)
            if len(arp_list) == 9:
                check = STATUS_OK

            content = "dynamic arp 등록 후 arp테이블에 등록된 정보가 정상적으로 조회되는가?"
            status  = f"arp-table=[9/{len(arp_list)}]"

        elif action == "arp-dynamic-clear":
            arp_list = get_idx(f"{self.config['cdynamic_mac']}", log)
            if len(arp_list) == 0:
                check = STATUS_OK

            content = "dynamic arp clear 후 arp테이블에 등록된 정보가 정상적으로 삭제되었는가?"
            status  = f"arp-table=[9/{len(arp_list)}]"

        elif action == "arp-static":
            arp_list = get_idx(f"{self.config['cstatic_mac']}", log)
            if len(arp_list) == 1:
                check = STATUS_OK

            content = "static arp 등록 후 arp테이블에 등록된 정보가 정상적으로 조회되는가?"
            status  = f"arp-table=[1/{len(arp_list)}]"

        elif action == "arp-static-clear":
            arp_list = get_idx(f"{self.config['cstatic_mac']}", log)
            if len(arp_list) == 0:
                check = STATUS_OK

            content = "static arp clear 후 arp테이블에 등록된 정보가 정상적으로 삭제되었는가?"
            status  = f"arp-table=[1/{len(arp_list)}]"

        elif action == "pre-arp-timeout":
            arp_list = get_idx(f"{self.config['cdynamic_mac']}", log)
            if len(arp_list) == 9:
                check = STATUS_OK

            content = "arp timeout 60초 설정 전, arp테이블에 등록된 정보가 정상적으로 등록되었는가?"
            status  = f"arp-table=[9/{len(arp_list)}]"

        elif action == "after-arp-timeout":
            arp_list = get_idx(f"{self.config['cdynamic_mac']}", log)
            if len(arp_list) == 0:
                check = STATUS_OK

            content = "arp timeout 60초 경과 후, arp테이블에 등록된 정보가 정상적으로 삭제되었는가?"
            status  = f"arp-table=[9/{len(arp_list)}]"

        self.update_xlsx_log(check, [self.config_mode, target_port, action, content, status])

