#!/bin/bin/env python3
# -*- coding: utf-8 -*-
# Author: huxy1501

from aliyunsdkcore import client
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkrds.request.v20140815 import DescribeResourceUsageRequest, DescribeDBInstancePerformanceRequest
import json
from datetime import datetime, timedelta
import time
import sys
import os
import stat
import getpass

# 请修改以下三个值
API_Key = 'ID'
API_Secret = 'Secret'
RegionId = 'cn-shenzhen'  # 阿里云区域代码

Item_Type = sys.argv[1]  # 类型 Disk or Performance
DBInstanceId = sys.argv[2]  # 实例ID
Item_Key = sys.argv[3]  # 监控项目

StartTime = datetime.strftime(datetime.utcnow() + timedelta(minutes=-1), '%Y-%m-%dT%H:%MZ')
EndTime = datetime.strftime(datetime.utcnow() + timedelta(minutes=1), '%Y-%m-%dT%H:%MZ')


class RdsKey(object):
    def __init__(self, item_key, master_key):
        self.item_key = item_key
        self.master_key = master_key


class FileCache(object):
    """
    讲单次请求产生的多个项目的值保存到临时文件，下次查询时先检查缓存文件中的值是否过期，避免过多的API调用影响性能
    """
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.create_dir()

    def create_dir(self):
        dir_path = os.path.dirname(self.cache_file)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            os.chmod(dir_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 修改目录权限777

    def get_info_from_file(self, seconds=300):
        """
        cache文件的内容，第一行是时间戳，第二行是json数据内容
        :param seconds: 值的有效期，超过这个时间重新请求API获取值
        :return: (value, code)
            code:
                0: 正常获取数据
                1: 异常
                2: 超时
        """
        if not os.path.isfile(self.cache_file):
            return None, 1
        with open(self.cache_file, "r") as fd:
            all_lines = fd.readlines()
        if not all_lines or len(all_lines) < 1:  # 没有数据
            return None, 1
        old_unix_time = int(str(all_lines[0]).strip())
        now_unix_time = int(time.time())
        if (now_unix_time - old_unix_time) > seconds:  # 超过60s
            return None, 2
        try:
            res_obj = str(all_lines[1]).strip()
            return json.loads(res_obj), 0
        except (ValueError, IndexError, json.JSONDecodeError):  # 数据格式错误
            return None, 1

    def save_info_to_file(self, content, timestamp=int(time.time())):
        """
        保存内容到缓存文件
        :param content: 字典或JSON格式的内容
        :param timestamp: 数据的时间戳，默认当前时间
        """
        # 如果是dict，则先转换为json字符串再写入
        if isinstance(content, dict):
            content = json.dumps(content)

        with open(self.cache_file, "w") as fd:
            fd.write(str(timestamp) + "\n")
            fd.write(content)


class Rds(object):
    def __init__(self):
        self.api_key = API_Key
        self.api_secret = API_Secret
        self.region_id = RegionId
        self.user = getpass.getuser()

        self.item_type = Item_Type
        self.db_instance_id = DBInstanceId
        self.item_key = Item_Key
        self.performance_items = dict()

        self.create_item()

        self.master_key = self.performance_items[self.item_key].master_key
        self.cache = FileCache(
            "/tmp/rds/rds_cache_%s_%s_by_%s.json" % (self.db_instance_id, self.master_key, self.user))

        # 创建阿里云API接口实例
        self.ali_client = client.AcsClient(
            self.api_key,
            self.api_secret,
            self.region_id
        )

        self.check_vars()

    def check_vars(self):
        """
        检查参数是否已配置
        """
        try:
            assert self.api_key
            assert self.api_secret
            assert self.region_id
            assert self.item_type
            assert self.db_instance_id
            assert self.item_key
            assert self.ali_client
        except AssertionError:
            exit("Parameters error")

    def create_item(self):
        """
        创建Zabbix监控项与Aliyun监控项的对应关系
        格式：
            performance_items["ZABBIX监控项"] = AliKey("阿里云监控项子项", "阿里云监控项")
        其中阿里云监控项是API请求的最小单位
        """
        self.performance_items["MySQL_NetworkTraffic_In"] = RdsKey("recv_k", "MySQL_NetworkTraffic")  # 平均每秒钟的输入流量
        self.performance_items["MySQL_NetworkTraffic_Out"] = RdsKey("sent_k", "MySQL_NetworkTraffic")  # 平均每秒钟的输出流量

        self.performance_items["MySQL_QPS"] = RdsKey("QPS", "MySQL_QPSTPS")  # 每秒SQL语句执行次数
        self.performance_items["MySQL_TPS"] = RdsKey("TPS", "MySQL_QPSTPS")  # 平均每秒事务数

        self.performance_items["MySQL_Sessions_Active"] = RdsKey("active_session", "MySQL_Sessions")  # 当前活跃连接数
        self.performance_items["MySQL_Sessions_Totle"] = RdsKey("total_session", "MySQL_Sessions")  # 当前总连接数

        self.performance_items["ibuf_read_hit"] = RdsKey("ibuf_read_hit", "MySQL_InnoDBBufferRatio")  # InnoDB缓冲池的读命中率
        self.performance_items["ibuf_use_ratio"] = RdsKey("ibuf_use_ratio", "MySQL_InnoDBBufferRatio")  # InnoDB缓冲池的利用率
        self.performance_items["ibuf_dirty_ratio"] = RdsKey("ibuf_dirty_ratio", "MySQL_InnoDBBufferRatio")  # InnoDB缓冲池脏块的百分率

        self.performance_items["inno_data_read"] = RdsKey("inno_data_read", "MySQL_InnoDBDataReadWriten")  # InnoDB平均每秒钟读取的数据量
        self.performance_items["inno_data_written"] = RdsKey("inno_data_written", "MySQL_InnoDBDataReadWriten")  # InnoDB平均每秒钟写入的数据量

        self.performance_items["ibuf_request_r"] = RdsKey("ibuf_request_r", "MySQL_InnoDBLogRequests")  # 平均每秒向InnoDB缓冲池的读次数
        self.performance_items["ibuf_request_w"] = RdsKey("ibuf_request_w", "MySQL_InnoDBLogRequests")  # 平均每秒向InnoDB缓冲池的写次数

        self.performance_items["Innodb_log_write_requests"] = RdsKey("Innodb_log_write_requests", "MySQL_InnoDBLogWrites")  # 平均每秒日志写请求数
        self.performance_items["Innodb_log_writes"] = RdsKey("Innodb_log_writes", "MySQL_InnoDBLogWrites")  # 平均每秒向日志文件的物理写次数
        self.performance_items["Innodb_os_log_fsyncs"] = RdsKey("Innodb_os_log_fsyncs", "MySQL_InnoDBLogWrites")  # 平均每秒向日志文件完成的fsync()写数量

        self.performance_items["tb_tmp_disk"] = RdsKey("tb_tmp_disk", "MySQL_TempDiskTableCreates")  # MySQL执行语句时在硬盘上自动创建的临时表的数量

        self.performance_items["Key_usage_ratio"] = RdsKey("Key_usage_ratio", "MySQL_MyISAMKeyBufferRatio")  # MyISAM平均每秒Key Buffer利用率
        self.performance_items["Key_read_hit_ratio"] = RdsKey("Key_read_hit_ratio", "MySQL_MyISAMKeyBufferRatio")  # MyISAM平均每秒Key Buffer读命中率
        self.performance_items["Key_write_hit_ratio"] = RdsKey("Key_write_hit_ratio", "MySQL_MyISAMKeyBufferRatio")  # MyISAM平均每秒Key Buffer写命中率

        self.performance_items["myisam_keyr_r"] = RdsKey("myisam_keyr_r", "MySQL_MyISAMKeyReadWrites")  # MyISAM平均每秒钟从缓冲池中的读取次数
        self.performance_items["myisam_keyr_w"] = RdsKey("myisam_keyr_w", "MySQL_MyISAMKeyReadWrites")  # MyISAM平均每秒钟从缓冲池中的写入次数
        self.performance_items["myisam_keyr"] = RdsKey("myisam_keyr", "MySQL_MyISAMKeyReadWrites")  # MyISAM平均每秒钟从硬盘上读取的次数
        self.performance_items["myisam_keyw"] = RdsKey("myisam_keyw", "MySQL_MyISAMKeyReadWrites")  # MyISAM平均每秒钟从硬盘上写入的次数

        self.performance_items["com_delete"] = RdsKey("com_delete", "MySQL_COMDML")  # 平均每秒Delete语句执行次数
        self.performance_items["com_insert"] = RdsKey("com_insert", "MySQL_COMDML")  # 平均每秒Insert语句执行次数
        self.performance_items["com_insert_select"] = RdsKey("com_insert_select", "MySQL_COMDML")  # 平均每秒Insert_Select语句执行次数
        self.performance_items["com_replace"] = RdsKey("com_replace", "MySQL_COMDML")  # 平均每秒Replace语句执行次数
        self.performance_items["com_replace_select"] = RdsKey("com_replace_select", "MySQL_COMDML")  # 平均每秒Replace_Select语句执行次数
        self.performance_items["com_select"] = RdsKey("com_select", "MySQL_COMDML")  # 平均每秒Select语句执行次数
        self.performance_items["com_update"] = RdsKey("com_update", "MySQL_COMDML")  # 平均每秒Update语句执行次数

        self.performance_items["inno_row_readed"] = RdsKey("inno_row_readed", "MySQL_RowDML")  # 平均每秒从InnoDB表读取的行数
        self.performance_items["inno_row_update"] = RdsKey("inno_row_update", "MySQL_RowDML")  # 平均每秒从InnoDB表更新的行数
        self.performance_items["inno_row_delete"] = RdsKey("inno_row_delete", "MySQL_RowDML")  # 平均每秒从InnoDB表删除的行数
        self.performance_items["inno_row_insert"] = RdsKey("inno_row_insert", "MySQL_RowDML")  # 平均每秒从InnoDB表插入的行数
        self.performance_items["Inno_log_writes"] = RdsKey("Inno_log_writes", "MySQL_RowDML")  # 平均每秒向日志文件的物理写次数

        self.performance_items["cpuusage"] = RdsKey("cpuusage", "MySQL_MemCpuUsage")  # MySQL实例CPU使用率(占操作系统总数)
        self.performance_items["memusage"] = RdsKey("memusage", "MySQL_MemCpuUsage")  # MySQL实例内存使用率(占操作系统总数)

        self.performance_items["io"] = RdsKey("io", "MySQL_IOPS")  # MySQL实例的IOPS（每秒IO请求次数）

        self.performance_items["ins_size"] = RdsKey("ins_size", "MySQL_NetworkTraffic_In")  # ins_size实例总空间使用量
        self.performance_items["data_size"] = RdsKey("data_size", "MySQL_NetworkTraffic_In")  # data_size数据空间
        self.performance_items["log_size"] = RdsKey("log_size", "MySQL_NetworkTraffic_In")  # log_size日志空间
        self.performance_items["tmp_size"] = RdsKey("tmp_size", "MySQL_NetworkTraffic_In")  # tmp_size临时空间
        self.performance_items["other_size"] = RdsKey("other_size", "MySQL_NetworkTraffic_In")  # other_size系统空间

        self.performance_items["iothread"] = RdsKey("iothread", "slavestat")  # 只读实例IO线程状态
        self.performance_items["sqlthread"] = RdsKey("sqlthread", "slavestat")  # 只读实例SQL线程状态
        self.performance_items["slave-lag"] = RdsKey("slave", "slavestat")  # 只读实例延迟

        self.performance_items["BackupOssLogSize"] = RdsKey("BackupOssLogSize", "DISK")  # OSS中日志备份大小
        self.performance_items["BackupOssDataSize"] = RdsKey("BackupOssDataSize", "DISK")  # OSS中数据备份大小
        self.performance_items["ColdBackupSize"] = RdsKey("ColdBackupSize", "DISK")  # 冷备份大小
        self.performance_items["SQLSize"] = RdsKey("SQLSize", "DISK")  # SQL大小
        self.performance_items["LogSize"] = RdsKey("LogSize", "DISK")  # 日志大小
        self.performance_items["DataSize"] = RdsKey("DataSize", "DISK")  # 数据大小
        self.performance_items["BackupSize"] = RdsKey("BackupSize", "DISK")  # 备份大小
        self.performance_items["DiskUsed"] = RdsKey("DiskUsed", "DISK")  # 已用磁盘空间

    def get_value(self):
        """
        获取指定监控项的值
        :return: 返回获取到的值
        """
        result = {}
        rds_values, code = self.cache.get_info_from_file()
        if code == 0:  # 从缓存获取值
            result = rds_values
        else:  # 通过API获取值
            if self.item_type == "Disk":
                rds_values = self.get_resource_usage()
                if rds_values != "" and rds_values is not None:
                    result = rds_values
                    self.cache.save_info_to_file(result)
            elif self.item_type == "Performance":
                rds_values, value_time = self.get_performance()
                if rds_values != "" and rds_values is not None:
                    result = rds_values
                    local_time = datetime.strptime(value_time, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                    # timestamp = int(local_time.timestamp())  # timestamp() 方法只支持python3
                    timestamp = int(time.mktime(local_time.timetuple()))
                    self.cache.save_info_to_file(result, timestamp)
        if result:
            return result.get(self.performance_items[self.item_key].item_key)

    def get_resource_usage(self):
        """
        获取磁盘用量相关信息
        """
        request = DescribeResourceUsageRequest.DescribeResourceUsageRequest()
        request.set_accept_format('json')
        request.set_DBInstanceId(self.db_instance_id)
        response = self.ali_client.do_action_with_exception(request)
        info = json.loads(response)
        return info

    def get_performance(self):
        """
        获取各项性能指标
        """
        request = DescribeDBInstancePerformanceRequest.DescribeDBInstancePerformanceRequest()
        request.set_accept_format('json')
        request.set_DBInstanceId(self.db_instance_id)
        request.set_Key(self.master_key)
        request.set_StartTime(StartTime)
        request.set_EndTime(EndTime)
        response = self.ali_client.do_action_with_exception(request)
        info = (json.loads(response))
        value_list = info['PerformanceKeys']['PerformanceKey'][0]['Values']['PerformanceValue'][-1]['Value'].split('&')
        key_list = info['PerformanceKeys']['PerformanceKey'][0]['ValueFormat'].split('&')
        key_value = dict(zip(key_list, value_list))
        value_time = info['PerformanceKeys']['PerformanceKey'][0]['Values']['PerformanceValue'][-1]["Date"]  # UTC时间
        return key_value, value_time


if __name__ == "__main__":
    rds_monitor = Rds()
    try_times = 0
    while try_times < 2:
        try:
            value = rds_monitor.get_value()
            assert (value != "" and value is not None)
            print(value)
            break
        except (IndexError, KeyError, ValueError, AssertionError, ServerException, ClientException):
            # import traceback
            # traceback.print_exc()
            try_times += 1
            time.sleep(1)
