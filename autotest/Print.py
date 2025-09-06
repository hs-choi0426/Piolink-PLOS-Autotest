import os
import sys
from time import strftime, localtime

class _Loadbar(object):
    def __init__(self, host_key, testtype, cycle):
        self.testtype   = testtype
        self.host_key   = host_key
        self.cycle      = cycle
        self.cycle_list = ["... \\", "... |", "... /", "... -"]

    def print_loadbar(self, complete=False):
        curr_time = strftime("[%Y%m%d_%H:%M:%S]", localtime())
        bar_fill  = f"\r{curr_time}[{self.host_key}] {self.testtype} Test"

        if complete == True:
            sys.stdout.write(f'{bar_fill} ... Done\n')
        else:
            sys.stdout.write(f'{bar_fill} {self.cycle_list[self.cycle % len(self.cycle_list)]}')
            self.cycle += 1
        sys.stdout.flush()

def print_time_log(host_key, dev_name):
    curr_time  = strftime("[%Y%m%d_%H:%M:%S]", localtime())
    return f"{curr_time} {host_key}: {dev_name}"

def print_stat_name(testtype, host_key=None, dev_name=None, reason="", length=47):
    prompt = []

    prompt.append("="*length)
    prompt.append(f"={testtype.center(length-2)}=")
    prompt.append("="*length)
    if (host_key != None) and (dev_name != None):
        prompt.append(print_time_log(host_key, dev_name))
    prompt.append("-"*length)
    prompt.append(f"{testtype} Test Complete")
    if reason == 'fail':
        prompt.append("-"*length)
        prompt.append("Fail:")
    prompt.append("\n")

    return prompt

def print_testtype_display(log={}, length=47):
    prompt = []
    num = 0

    if log == []: return prompt

    prompt.append("-"*length)
    prompt.append("Item List")
    prompt.append("-"*length)
    for key, val in log:
        prompt.append(f"{'*' if val == 1 else ' '}[{num:<2}] {key}")
        num += 1

    return prompt

