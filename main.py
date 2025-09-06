#!/usr/bin/env python3
import os
import sys
import time
import argparse
import telnetlib
import re
import threading
import datetime
import shutil
import traceback
import concurrent.futures

from collections import defaultdict
from autotest.resources.Data import *
from autotest.resources.Data import _Data
from autotest.Tools import *
from autotest.Log import *
from autotest.Print import *
from autotest.Host import _Host
from autotest.Run_test import _Run

def reboot_sequence_thread(session, host_key, host_info):
    session.reset_connection()
    print(f"============ {host_key} ============")
    print(f"reboot dev_name   : {host_info['dev_name']}")
    print(f"reboot ip         : {host_info['dev_con_ip']}")
    print(f"reboot console    : {host_info['dev_console']}")
    session.reboot()
    session.telnet.close()

def initial_sequence_thread(session, host_key, Run, reboot_flag):
    session.reset_connection(reboot=reboot_flag)
    Run.initial_set(host_key, session)
    print(f"[{host_key}]...plos init complete!")

def initialize_all_device(data=None, reboot_flag=True, init_flag=True):
    threads = []

    if data == None:
        data = _Data()

    print("test all device initialize")

    if (data.host_info is None) or (backup_dir_check() == None):
        return None

    if reboot_flag == True:
        try:
            for host_key, session in data.full_session_list.items():
                if os.path.exists(CURR_LOG + "/" + host_key):
                    f = open(CURR_LOG + "/" + host_key, 'w')
                    f.close()

                t = threading.Thread(target=reboot_sequence_thread, args=(session, host_key, data.host_info[host_key]))
                threads.append(t)
                t.start()
                time.sleep(1)

            if len(threads) > 0:
                for t in threads:
                    t.join()
            print("reboot cmd sent to all device. start timer (120s)\n")
            time.sleep(120)
        except Exception as e:
            print("Error: Unable to start reboot thread:  \n", e)
            traceback.print_exc()
            return None

    else: 
        print("device will initialize without reboot\n")

    threads = []
    Run = _Run(data)
    if init_flag == True:
        print("#initial sequence#")
        try:
            for host_key, session in data.full_session_list.items():
                if os.path.exists(CURR_LOG + "/" + host_key):
                    f = open(CURR_LOG + "/" + host_key, 'w')
                    f.close()

                t = threading.Thread(target=initial_sequence_thread, args=(session, host_key, Run, reboot_flag))
                threads.append(t)
                t.start()
                time.sleep(1)

            if len(threads) > 0:
                for t in threads:
                    t.join()
        except Exception as e:
            print("Error: Unable to start initial thread:  \n", e)
            traceback.print_exc()
            return None

    return 0

def update_sequence_thread(session, host_key, host_info, Run, log):
    session.reset_connection()
    print(f"[{host_key}]...update Version={host_info['osname']}")
    if (Run.plos_update(host_key, session) < 0):
        print(f"[{host_key}]...plos update fail!")
        log.append('fail')
    else:
        print(f"[{host_key}]...plos update complete!")
        log.append('ok')

def update_all_device(data=None):
    threads = []
    log = []

    if data == None:
        data = _Data()

    if (data.host_info is None) or (backup_dir_check() == None):
        return None

    if initialize_all_device(data=data, reboot_flag=False) == None:
        return None

    time.sleep(1)

    Run = _Run(data)

    print("#plos update sequence#")
    try:
        for host_key, session in data.full_session_list.items():
            if data.host_info[host_key]['osupdate'] == "y":
                t = threading.Thread(target=update_sequence_thread, args=(session, host_key, data.host_info[host_key], Run, log))
                threads.append(t)
                t.start()
                time.sleep(1)

        if len(threads) > 0:
            for t in threads:
                t.join()

    except Exception as e:
        print("Error: Unable to start update thread:  \n", e)
        traceback.print_exc()
        return None

    for match in log:
        if match == 'fail':
            return None

    if initialize_all_device(data=data, init_flag=False) == None:
        return None

    return 0

def print_help():
    help_text = [
        "Usage: ./main.py",
        "\nCommands:",
        "    list             Display a list of items.",
        "    list <0-25>      Select and display items based on the specified range (0-25).",
        "    list <range1,range2,...>  Select and display items based on the specified ranges.",
        "    list all         Select and Display all items.",
        "    config           Display Tifront configuration information.",
        "    init [reboot]    Initialize the program. Optional 'reboot' flag for a reboot after initialization.",
        "    update           Update the plos-image.",
        "    run [reboot]     Run the program. Optional 'reboot' flag for a reboot after running.",
        "\n",
        "Examples:",
        "    ./main.py list",
        "    ./main.py list 8",
        "    ./main.py list 0-1,4,20-24",
        "    ./main.py list all",
        "    ./main.py config",
        "    ./main.py init",
        "    ./main.py init reboot",
        "    ./main.py update",
        "    ./main.py run",
        "    ./main.py run reboot"
        "\n",
    ]
    [print(line) for line in help_text]

def main():
    """
    Main function to handle command line arguments and execute corresponding actions.
    """
    reboot_flag = False

    if len(sys.argv) == 1:
        print_help()
        sys.exit()

    elif len(sys.argv) > 2 and sys.argv[2] == "reboot":
        reboot_flag = True

    data = _Data()

    if sys.argv[1] == "init":
        execute_action(initialize_all_device, data, reboot_flag)

    elif sys.argv[1] == "update":
        execute_action(update_all_device, data)

    elif sys.argv[1] == "run":
        execute_action(initialize_all_device, data, reboot_flag)
        time.sleep(1)
        Run = _Run(data)
        execute_action(Run.run_script)

    elif sys.argv[1] == "list":
        if len(sys.argv) > 2:
            execute_action(data.set_testtype_info, sys.argv[2])
        else:
            execute_action(data.get_testtype_info, show="y")

    elif sys.argv[1] == "config":
        execute_action(data.get_config_info)

    else:
        print_help()
        sys.exit()

def execute_action(action_function, *args, **kwargs):
    if action_function(*args, **kwargs) == None:
        sys.exit()

if __name__ == "__main__":
    main()

    
