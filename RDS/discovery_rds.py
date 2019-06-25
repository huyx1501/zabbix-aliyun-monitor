#!/bin/bin/env python3
# -*- coding: utf-8 -*-
# Author: huxy1501

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkrds.request.v20140815.DescribeDBInstancesRequest import DescribeDBInstancesRequest
import json
import time

API_Key = 'ID'
API_Secret = 'Secret'
RegionId = 'cn-shenzhen'  # 阿里云区域代码


class RdsDiscovery(object):
    def __init__(self):
        self.client = AcsClient(API_Key, API_Secret, RegionId)
        self.rds_instance_list = []

    def get_instance_list(self):
        request = DescribeDBInstancesRequest()
        request.set_accept_format('json')
        response = self.client.do_action_with_exception(request)
        instances = json.loads(response)['Items']['DBInstance']
        for rds_instance in instances:
            try:
                rds_instance_info = dict()
                rds_instance_info["{#DBINSTANCEID}"] = rds_instance['DBInstanceId']
                rds_instance_info["{#DBINSTANCEDESCRIPTION}"] = rds_instance['DBInstanceDescription']
                self.rds_instance_list.append(rds_instance_info)
            except Exception as e:
                print(Exception, ":", e)
        else:
            return self.rds_instance_list


if __name__ == "__main__":
    zabbix_data = dict()
    try_times = 0
    rds = RdsDiscovery()
    while try_times < 2:
        try:
            data = rds.get_instance_list()
            zabbix_data['data'] = data
            print(json.dumps(zabbix_data))
            break
        except (ClientException, ServerException):
            # import traceback
            # traceback.print_exc()
            try_times += 1
            time.sleep(1)
