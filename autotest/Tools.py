
import subprocess
import os
import sys
import re
from functools import reduce

SPLIT_TYPE0=0 # context once split
SPLIT_TYPE1=1 # context once split
SPLIT_TYPE2=2 # context multiple split

def shell_exe(cmd) :
    fd = subprocess.Popen(cmd, shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    return fd.stdout, fd.stderr


def log_file_list_up(DIR):
    testnames = os.listdir(DIR)
    print(testnames)
    log_list = []
    for testname in testnames:
        filenames = os.listdir(DIR + "/" + testname)
        for filename in filenames:
            log_list.append(testname + "/" + filename)  

    return log_list

def apply_prefix(ipaddr, prefix):
    ip_sections     = list(map(int, ipaddr.split('.')))
    mask_sections   = create_mask(prefix)
    new_ip_sections = [ip & mask for ip, mask in zip(ip_sections, mask_sections)]

    result_ip = '.'.join(map(str, new_ip_sections))
    return result_ip

def create_mask(prefix):
    mask = (1 << prefix) - 1
    mask <<= (32 - prefix)

    return [(mask >> shift) & 0xFF for shift in (24, 16, 8, 0)]

def mac_addr_formatter(mode, mac):
    if mode == "colon":
        new_mac = ':'.join([mac[i:i+2] for i in range(0, 12, 2)])
    elif mode == "dot":
        new_mac = '.'.join([mac[i:i+4] for i in range(0, 12, 4)])

    return new_mac

def get_search_context(mode, context, log, cols=0, row=0):
    DELIMITERS_TYPE0 = [':', '|', '=']
    DELIMITERS_TYPE1 = [':', '|', '=', ',']
    REPLACEMENTS_TYPE2 = [('|', ''), (':', ''), (',', ''), ('!', '')]
    
    try:
        if not context or not log:
            return ""
        
        if not isinstance(log, list):
            log = [log]
        
        idx_list = get_idx(context, log)
        if not idx_list:
            return ""
        
        target_idx = idx_list[0] + cols
        if target_idx < 0 or target_idx >= len(log):
            return ""
        
        text = log[target_idx]
        if not text:
            return ""
        
        parsed_text = ""
        
        if mode == SPLIT_TYPE0:
            parsed_text = _parse_with_delimiters(text, DELIMITERS_TYPE0, row)
        elif mode == SPLIT_TYPE1:
            parsed_text = _parse_with_delimiters(text, DELIMITERS_TYPE1, row)
        elif mode == SPLIT_TYPE2:
            parsed_text = _parse_with_replacements(text, REPLACEMENTS_TYPE2, row)
        else:
            return ""
        
        return parsed_text
        
    except (IndexError, TypeError, AttributeError) as e:
        print(f"Error in get_search_context_improved: {e}")
        return ""

def _parse_with_delimiters(text, delimiters, row):
    for delimiter in delimiters:
        if delimiter in text:
            parsed_list = [segment.strip() for segment in text.split(delimiter)]
            if 0 <= row < len(parsed_list):
                return parsed_list[row]
    return ""

def _parse_with_replacements(text, replacements, row):
    try:
        modified_text = reduce(lambda s, replacement: s.replace(*replacement), replacements, text)
        parsed_list = [segment.strip() for segment in modified_text.split()]
        if 0 <= row < len(parsed_list):
            return parsed_list[row]
    except Exception:
        pass
    return ""

def get_idx(context, log):
    ret = []
    if not isinstance(log, list): log = [log]

    idx_list = [idx for idx, element in enumerate(log) if context in element]
    if len(idx_list) != 0: ret = idx_list

    return ret

def get_integer_val(val_str):
    try:
        return int(val_str)
    except ValueError:
        return 0

def rtk_sdk_parse_match(sdk_func, context, match):
    ret = False

    if sdk_func == 'ports':
        if all(value in _rtk_sdk_parse_ports(context) for value in match):
            ret = True

    return ret

def _rtk_sdk_parse_ports(ports_str):
    numbers = []

    match = re.search(r'\s*([0-9,-]+)', ports_str)
    if match:
        range_str = match.group(1)

        for part in range_str.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                numbers.extend(range(start, end + 1))
            else:
                numbers.append(int(part))

        return numbers

    return numbers

