import os
import sys
import re
import pdb
import time
import traceback
import shutil
import subprocess
import pandas as pd
from time import strftime, localtime
from autotest.Print import *

# path
RESOURCE_DIR = "autotest/resources"
IMAGE_DIR    = RESOURCE_DIR + "/images"
CONFIG_DIR   = RESOURCE_DIR + "/config"
PROFILE_DIR  = CONFIG_DIR + "/profile"
BACKUP_DIR   = "backup"
TEST_LOGS    = BACKUP_DIR + "/test-logs"
STAT_LOGS    = BACKUP_DIR + "/stat-logs"
REPORT_FILE  = "Report.txt"
ARCHIVE_FILE = "Report.tar"
CURR_LOG     = BACKUP_DIR + "/current_log"
CHK_LIST     = BACKUP_DIR + "/chklist"

class _Backup(object):
    def __init__(self):
        self.curr_time     = strftime("%Y%m%d", localtime())
        self.testlogs_path = ""
        self.statlogs_path = ""
        self.chklist_path  = ""
        self.start_test    = 1
        self.data          = dict()
        self.df_dict       = dict()
        self.tm_dict       = dict()
        self.st_time       = 0

    def backup_time_dir_check(self, host_key, dev_name):
        ret = 0

        try:
            if self.start_test:
                self.testlogs_path = get_available_name(f"{TEST_LOGS}/{self.curr_time}")
                if not os.path.exists(self.testlogs_path):
                    os.makedirs(self.testlogs_path)
                self.statlogs_path = get_available_name(f"{STAT_LOGS}/{self.curr_time}")
                if not os.path.exists(self.statlogs_path):
                    os.makedirs(self.statlogs_path)
                self.chklist_path = get_available_name(f"{CHK_LIST}/{self.curr_time}")
                if not os.path.exists(self.chklist_path):
                    os.makedirs(self.chklist_path)
                self.start_test = 0
        except Exception as e:
            print("backup dir generate error:  \n", e)
            traceback.print_exc()
            ret = -1

        return ret

    def backup_log_save(self, host_key, dev_name, log, testtype=None, sec=0.5):
        filename = ''
        opt = ''

        if testtype != None:
            testlogs_path = self.testlogs_path+f"/{host_key}-{dev_name}"
            if not os.path.exists(testlogs_path):
                os.makedirs(testlogs_path)
            filename = f"{testlogs_path}/{testtype}"
            opt = 'a+'
        else:
            filename = f"{self.statlogs_path}/{host_key}-{dev_name}"
            opt = 'a+'

        f = open(filename, opt)
        if type(log) is str:
            f.write(log)
        elif type(log) is list:
            f.write("\n".join(log))
        f.close()

    def backup_statlog_save(self, host_key, dev_name, testtype):
        reason = 'ok'

        filename = f"{self.statlogs_path}/{host_key}-{dev_name}"

        failcnt = len([result for result in self.data['Result'] if result == 'Abnormal'])
        if failcnt > 0: reason = 'fail'

        with open(filename, 'a+') as f:
            f.write("\n".join(print_stat_name(testtype, host_key, dev_name, reason)))
            if reason == 'fail':
                curr_df = self.df_dict[testtype]
                if testtype == 'Port-Mapping' or testtype == 'Shutdown' or testtype == 'Speed':
                    fail_log = curr_df[curr_df['Result'] == 'Abnormal'].drop(labels=['Content'], axis=1)
                else:
                    fail_log = curr_df[curr_df['Result'] == 'Abnormal'].drop(labels=['Content', 'Status'], axis=1)
                f.write(fail_log.to_string(index=False, justify='left')+'\n\n')

    def backup_testlog_save(self, host_key, dev_name, log, testtype):

        testlogs_path = self.testlogs_path+f"/{host_key}-{dev_name}"
        if not os.path.exists(testlogs_path):
            os.makedirs(testlogs_path)

        filename = f"{testlogs_path}/{testtype}"

        with open(filename, 'a+') as f:
            if type(log) is str:
                f.write(log)
            elif type(log) is list:
                f.write("\n".join(log))

    def create_dataframe(self):
        self.data = {
            'Mode'   :[],
            'Port'   :[],
            'Action' :[],
            'Content':[],
            'Status' :[],
            'Result' :[],
        }
        self.st_time = time.time()

    def add_dataframe(self, data=list):
        if not isinstance(data, list):
            data = [data]

        if len(data) != len(self.data):
            data = ["" for idx in range(len(self.data))]

        for idx, element in enumerate(data):
            if type(element) is not str:
                data[idx] = "-"
            else:
                if len(element) == 0:
                    data[idx] = "-"

        for idx, key in enumerate(self.data.keys()):
            self.data[key].append(data[idx])

    def save_dataframe(self, testtype):
        self.df_dict[testtype] = pd.DataFrame(self.data)
        self.tm_dict[testtype] = int(time.time() - self.st_time)

    def save_aggregation_dataframe(self):
        total_failcnt = 0
        total_elapsed = 0
        data = {'Item List': [], 'Elapsed Time': [], 'Fail Cnt': [], 'Result': []}

        for testtype, df in self.df_dict.items():
            failcnt = len([result for result in df['Result'].values if result == 'Abnormal'])

            data['Item List'].append(testtype)
            if self.tm_dict[testtype] > 60:
                elapsed_min = int(self.tm_dict[testtype]//60)
                elapsed_sec = int(self.tm_dict[testtype]%60)
                data['Elapsed Time'].append(f"{elapsed_min}(m){elapsed_sec}(s)")
            else:
                data['Elapsed Time'].append(f"{self.tm_dict[testtype]}(s)")
            data['Fail Cnt'].append(failcnt)

            total_elapsed += self.tm_dict[testtype]
            if failcnt > 0:
                total_failcnt += failcnt
                data['Result'].append('Abnormal')
            else:
                data['Result'].append('Normal')

        data['Item List'].append('Total test')
        if total_elapsed > 60:
            elapsed_min = int(total_elapsed//60)
            elapsed_sec = int(total_elapsed%60)
            data['Elapsed Time'].append(f"{elapsed_min}(m){elapsed_sec}(s)")
        else:
            data['Elapsed Time'].append(f"{total_elapsed}(s)")
        data['Fail Cnt'].append(total_failcnt)
        if total_failcnt > 0:
            data['Result'].append('Abnormal')
        else:
            data['Result'].append('Normal')

        return data

    def set_total_worksheet_format(self, df, writer, sheetname):
        startrow = 1
        startcol = 1

        df.to_excel(writer, index=False, engine='xlsxwriter', sheet_name=sheetname, startrow=startrow, startcol=startcol)

        workbook  = writer.book
        worksheet = writer.sheets[sheetname]

        worksheet.insert_image('G2', IMAGE_DIR+"/NetworkConfChart.png", {'x_scale': 0.8, 'y_scale': 0.8})

        header_format = workbook.add_format({
                'bold'     : True,
                'text_wrap': True,
                'valign'   : 'center',
                'border'   : 2,
                'align'    : 'center',
                'bg_color' : '#F2F2F2',
            })

        # apply header format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(startrow, startcol+col_num, value, header_format)

        # apply body format
        for row_num, (index, values) in enumerate(df.iterrows(), start=(startrow+1)):
            for col_num, value in enumerate(values):
                bottom_format = {
                        'bold'     : True,
                        'text_wrap': True,
                        'valign'   : 'top',
                        'border'   : 2,
                        'align'    : 'right',
                        'font_size': 10,
                    }
                body_format = {
                        'text_wrap': True,
                        'valign'   : 'top',
                        'align'    : 'right',
                        'border'   : 2,
                        'font_size': 10,
                    }

                if value in self.df_dict.keys():
                    locate  = f"{chr(ord('A')+(startcol+col_num))}{row_num + 1}"
                    hyperlink_url = f"internal:'{value}'!{locate}"
                    worksheet.write_url(locate, hyperlink_url)
                    body_format['color']     = 'blue'
                    body_format['underline'] = 1
                    body_format['align'] = 'left'

                if value == 'Normal':
                    body_format['bg_color']   = '#00FF00'
                    body_format['align']      = 'center'
                    bottom_format['bg_color'] = '#00FF00'
                    bottom_format['align']    = 'center'
                elif  value == 'Abnormal':
                    body_format['bg_color']   = '#FF0000'
                    body_format['align']      = 'center'
                    bottom_format['bg_color'] = '#FF0000'
                    bottom_format['align']    = 'center'

                form = workbook.add_format(body_format)

                if df['Item List'][(row_num-startrow)-1] == 'Total test':
                    form = workbook.add_format(bottom_format)

                worksheet.write(row_num, startcol+col_num, value, form)

        # apply cell auto width
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).apply(len).max()+2, len(col)+2)
            worksheet.set_column(startrow+i, startcol+i, max_len)

    def set_test_worksheet_format(self, df, writer, sheetname):
        startrow = 1
        startcol = 1

        if sheetname == 'STP':
            startrow = 18
            image_path = IMAGE_DIR+"/StpNetChart.png"
        elif sheetname == 'STP&LACP':
            startrow = 18
            image_path = IMAGE_DIR+"/StpLacpNetChart.png"
        elif sheetname == 'L2-Smoke':
            startrow = 18
            image_path = IMAGE_DIR+"/L2Smoke.png"

        df.to_excel(writer, index=False, engine='xlsxwriter', sheet_name=sheetname, startrow=startrow, startcol=startcol)

        workbook  = writer.book
        worksheet = writer.sheets[sheetname]

        worksheet.set_zoom(85)

        if startrow > 1: worksheet.insert_image('E2', image_path, {'x_scale': 1.2, 'y_scale': 1.2})

        header_format = workbook.add_format({
                'bold'     : True,
                'text_wrap': True,
                'valign'   : 'center',
                'border'   : 2,
                'align'    : 'center',
                'bg_color' : '#F2F2F2',
            })

        # back to Main sheet
        worksheet.write(0, 0, 'back to main', {'bold': True, 'align': 'center', 'color': 'blue', 'underline': 1})
        worksheet.write_url(0, 0, "internal:'Main'!A1", string=f">> back to main")

        # apply header format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(startrow, startcol+col_num, value, header_format)

        # apply body format
        for row_num, (index, values) in enumerate(df.iterrows(), start=(startrow+1)):
            for col_num, value in enumerate(values):
                body_format = {
                    'text_wrap': True,
                    'valign'   : 'top',
                    'align'    : 'left',
                    'border'   : 1,
                    'font_size': 10,
                }
                if value == 'Normal':
                    body_format['bg_color'] = '#00FF00'
                elif value == 'Abnormal':
                    body_format['bg_color'] = '#FF0000'

                form = workbook.add_format(body_format)
                worksheet.write(row_num, startcol+col_num, value, form)

        # apply cell auto width
        for i, col in enumerate(df.columns):
            max_len = (len(col)+2)
            for line in df[col].astype(str):
                if '\n' in line:
                    max_len = max(max_len, max(len(sub_line) for sub_line in line.split('\n'))+10)
                else:
                    max_len = max(max_len, len(line)+2)

            if col == 'Content': max_len*=1.20 # kor language length issue

            worksheet.set_column(startrow+i, startcol+i, max_len)

    def save_xlsx(self, host_key, dev_name):
        ret = 0

        try:
            with pd.ExcelWriter(self.chklist_path+f"/{host_key}-{dev_name}.xlsx") as writer:

                df = pd.DataFrame(self.save_aggregation_dataframe())
                self.set_total_worksheet_format(df, writer, 'Main')

                for testtype, df in self.df_dict.items():
                    self.set_test_worksheet_format(df, writer, testtype)

        except Exception as e:
            print("excel save error:  \n", e)
            traceback.print_exc()
            ret = -1

        return ret

def get_available_name(path):
    base, ext = os.path.splitext(path)

    counter = 0
    new_path = path
    while os.path.exists(new_path):
        counter += 1
        new_path = f"{base}.{counter}{ext}"

    return new_path

def backup_dir_check():
    ret = 0
    try:
        if not(os.path.isdir(BACKUP_DIR)):
            os.mkdir(BACKUP_DIR)
        if os.path.isdir(CURR_LOG):
            shutil.rmtree(CURR_LOG)

        os.mkdir(CURR_LOG)

    except Exception as e:
        print("Error: No search directoty:  \n", e)
        traceback.print_exc()
        ret = None

    return ret

def current_log(path, log=list, sec=0.1):

    f = open(f"{CURR_LOG}/{path}", 'a+')
    if type(log) is list:
        for line in log:
            f.write(f"{line}\n")

    f.close()
#    time.sleep(sec)

