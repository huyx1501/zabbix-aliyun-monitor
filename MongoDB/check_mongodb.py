#!/bin/bin/env python3
# -*- coding: utf-8 -*-
# Author: huxy1501

from aliyunsdkcore import client
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkdds.request.v20151201.DescribeDBInstancePerformanceRequest import DescribeDBInstancePerformanceRequest
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

DBInstanceId = sys.argv[1]  # 实例ID
Item_Key = sys.argv[2]  # 监控项目

StartTime = datetime.strftime(datetime.utcnow() + timedelta(minutes=-6), '%Y-%m-%dT%H:%MZ')
EndTime = datetime.strftime(datetime.utcnow() + timedelta(minutes=1), '%Y-%m-%dT%H:%MZ')


class AliKey(object):
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
        if not os.path.exists(dir_path):  # 兼容python2
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


class MongoDB(object):
    def __init__(self):
        self.api_key = API_Key
        self.api_secret = API_Secret
        self.region_id = RegionId
        self.user = getpass.getuser()

        self.db_instance_id = DBInstanceId
        self.item_key = Item_Key
        self.performance_items = dict()

        self.create_item()

        self.master_key = self.performance_items[self.item_key].master_key
        self.cache = FileCache(
            "/tmp/mongodb/mongodb_cache_%s_%s_by_%s.json" % (self.db_instance_id, self.master_key, self.user))

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
        self.performance_items["cpu_usage"] = AliKey("cpu_usage", "CpuUsage")  # CPU使用率

        self.performance_items["mem_usage"] = AliKey("mem_usage", "MemoryUsage")  # 内存使用率

        self.performance_items["data_iops"] = AliKey("data_iops", "MongoDB_IOPS")  # 数据IOPS使用量
        self.performance_items["log_iops"] = AliKey("log_iops", "MongoDB_IOPS")  # 日志IOPS使用量

        self.performance_items["iops_usage"] = AliKey("iops_usage", "IOPSUsage")  # IOPS使用率

        self.performance_items["index_size"] = AliKey("ins_size", "MongoDB_DetailedSpaceUsage")  # 索引使用的存储空间
        self.performance_items["data_size"] = AliKey("data_size", "MongoDB_DetailedSpaceUsage")  # 数据使用的存储空间
        self.performance_items["log_size"] = AliKey("log_size", "MongoDB_DetailedSpaceUsage")  # 日志使用的存储空间

        self.performance_items["disk_usage"] = AliKey("disk_usage", "DiskUsage")  # 磁盘使用率

        self.performance_items["op_insert"] = AliKey("insert", "MongoDB_Opcounters")  # 插入数据
        self.performance_items["op_query"] = AliKey("query", "MongoDB_Opcounters")  # 查询数据
        self.performance_items["op_update"] = AliKey("update", "MongoDB_Opcounters")  # 更新数据
        self.performance_items["op_delete"] = AliKey("delete", "MongoDB_Opcounters")  # 删除出具
        self.performance_items["op_getmore"] = AliKey("getmore", "MongoDB_Opcounters")  # 从游标中获取更多数据
        self.performance_items["op_command"] = AliKey("command", "MongoDB_Opcounters")  # 执行操作指令

        self.performance_items["current_conn"] = AliKey("current_conn", "MongoDB_Connections")  # 当前连接数

        self.performance_items["total_open_cursors"] = AliKey("total_open", "MongoDB_Cursors")  # 总共开启的游标数
        self.performance_items["timed_out_cursors"] = AliKey("timed_out", "MongoDB_Cursors")  # 超时的游标数

        self.performance_items["network_bytes_in"] = AliKey("bytes_in", "MongoDB_Network")  # 网络下行流量
        self.performance_items["network_bytes_out"] = AliKey("bytes_out", "MongoDB_Network")  # 网络上行流量
        self.performance_items["network_requests"] = AliKey("num_requests", "MongoDB_Network")  # 请求数

        self.performance_items["total_locks"] = AliKey("gl_cq_total", "MongoDB_Global_Lock_Current_Queue")  # 全局锁等待次数
        self.performance_items["read_locks"] = AliKey("gl_cq_readers", "MongoDB_Global_Lock_Current_Queue")  # 读锁等待次数
        self.performance_items["write_locks"] = AliKey("gl_cq_writers", "MongoDB_Global_Lock_Current_Queue")  # 写锁等待次数

        self.performance_items["read_into_cache"] = AliKey("bytes_read_into_cache", "MongoDB_Wt_Cache")  # 读入缓存的字节数
        self.performance_items["written_from_cache"] = AliKey("bytes_written_from_cache",
                                                              "MongoDB_Wt_Cache")  # 从缓存取出的字节数
        self.performance_items["maximum_cache"] = AliKey("maximum_bytes_configured", "MongoDB_Wt_Cache")  # 已配置的缓存大小

    def get_value(self):
        """
        获取指定监控项的值
        :return: 返回获取到的值
        """
        result = {}
        mongo_values, code = self.cache.get_info_from_file()
        if code == 0:  # 从缓存获取值
            result = mongo_values
        else:  # 通过API获取值
            mongo_values, value_time = self.get_performance()
            if mongo_values != "" and mongo_values is not None:
                result = mongo_values
                local_time = datetime.strptime(value_time, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                # timestamp = int(local_time.timestamp())  # timestamp() 方法只支持python3
                timestamp = int(time.mktime(local_time.timetuple()))
                self.cache.save_info_to_file(result, timestamp)
        if result:
            return result.get(self.performance_items[self.item_key].item_key)

    def get_performance(self):
        """
        获取各项性能指标
        """
        request = DescribeDBInstancePerformanceRequest()
        request.set_accept_format('json')
        request.set_DBInstanceId(self.db_instance_id)
        request.set_Key(self.master_key)
        request.set_StartTime(StartTime)
        request.set_EndTime(EndTime)
        response = self.ali_client.do_action_with_exception(request)
        info = json.loads(response)
        last_values = info['PerformanceKeys']['PerformanceKey'][0]['PerformanceValues']['PerformanceValue'][-1]  # 取最新值
        value_list = last_values["Value"].split('&')
        value_time = last_values["Date"]  # UTC时间
        key_list = info['PerformanceKeys']['PerformanceKey'][0]['ValueFormat'].split('&')
        key_value = dict(zip(key_list, value_list))
        return key_value, value_time


if __name__ == "__main__":
    mongo = MongoDB()
    try_times = 0
    while try_times < 2:
        try:
            value = mongo.get_value()
            assert (value != "" and value is not None)
            print(value)
            break
        except (IndexError, KeyError, ValueError, AssertionError, ServerException, ClientException):
            # import traceback
            # traceback.print_exc()
            try_times += 1
            time.sleep(1)
