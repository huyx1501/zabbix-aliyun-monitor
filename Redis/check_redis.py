#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: huxy1501

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkr_kvstore.request.v20150101.DescribeHistoryMonitorValuesRequest import DescribeHistoryMonitorValuesRequest
import json
from datetime import datetime, timedelta
import time
import sys

# 请修改以下三个值
API_Key = 'Key'
API_Secret = 'Secret'
RegionId = 'cn-shenzhen'  # 阿里云区域代码

InstanceId = sys.argv[1]  # 实例ID
InstanceType = sys.argv[2]  # 实例类型，cluster 或 standard
ItemKey = sys.argv[3]  # 监控项目

StartTime = datetime.strftime(datetime.utcnow() + timedelta(minutes=-5), '%Y-%m-%dT%H:%M:%SZ')
EndTime = datetime.strftime(datetime.utcnow(), '%Y-%m-%dT%H:%M:%SZ')


class RedisMonitor(object):
    def __init__(self):
        self.api_key = API_Key
        self.api_secret = API_Secret
        self.region_id = RegionId

        self.instance_type = InstanceType
        self.item_key = ItemKey
        self.instance_id = ""
        self.node_id = ""

        # 创建阿里云API接口实例
        self.client = AcsClient(
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
            assert self.item_key
            assert self.client
        except AssertionError:
            exit(1)

    def get_value(self):
        """
        获取各项性能指标
        """
        request = DescribeHistoryMonitorValuesRequest()
        request.set_accept_format('json')

        request.set_IntervalForHistory("01m")
        if self.instance_type == "cluster":
            self.node_id = InstanceId.replace("NUM", "#")  # 还原节点ID（发现节点时节点名中的"#"号被替换成了"NUM"）
            request.set_NodeId(self.node_id)  # 集群需要设置NodeId
            self.instance_id = InstanceId.split("-db")[0]  # 还原主实例ID
        else:
            self.instance_id = InstanceId
        request.set_InstanceId(self.instance_id)

        request.set_MonitorKeys(self.item_key)
        request.set_StartTime(StartTime)
        request.set_EndTime(EndTime)

        response = self.client.do_action_with_exception(request)
        # print(response)
        info = json.loads(json.loads(response)["MonitorHistory"])  # 需要两次json.loads
        values = sorted(info.items(), key=lambda item: item[0], reverse=True)  # 对字典排序
        try:
            info = values[0][1][self.item_key]
            return info
        except KeyError:
            return 0


if __name__ == "__main__":
    monitor = RedisMonitor()
    try_times = 0
    while try_times < 2:
        try:
            value = monitor.get_value()
            if value == "" or value is None:
                print(0)
            else:
                print(value)
            break
        except (IndexError, KeyError, ValueError, ServerException, ClientException):
            # import traceback
            # traceback.print_exc()
            try_times += 1
            time.sleep(1)
