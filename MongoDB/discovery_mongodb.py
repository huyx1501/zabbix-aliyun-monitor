#!/bin/bin/env python3
# -*- coding: utf-8 -*-
# Author: huxy1501

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkdds.request.v20151201.DescribeDBInstancesRequest import DescribeDBInstancesRequest
import json
import time

# 请修改以下三个值
API_Key = 'ID'
API_Secret = 'Secret'
RegionId = 'cn-shenzhen'  # 阿里云区域代码


class MongoDiscovery(object):
    def __init__(self):
        self.client = AcsClient(API_Key, API_Secret, RegionId)
        self.mongo_instance_list = []

    def get_instance_list(self):
        request = DescribeDBInstancesRequest()
        request.set_accept_format('json')
        response = self.client.do_action_with_exception(request)
        instances = json.loads(response)["DBInstances"]["DBInstance"]
        for mongo_instance in instances:
            try:
                mongo_instance_info = dict()
                mongo_instance_info["{#DBINSTANCEID}"] = mongo_instance["DBInstanceId"]
                mongo_instance_info["{#DBINSTANCEDESCRIPTION}"] = mongo_instance["DBInstanceDescription"]
                self.mongo_instance_list.append(mongo_instance_info)
            except Exception as e:
                print(Exception, ":", e)
        else:
            return self.mongo_instance_list


if __name__ == "__main__":
    zabbix_data = dict()
    try_times = 0
    Mongo = MongoDiscovery()
    while try_times < 2:
        try:
            data = Mongo.get_instance_list()
            zabbix_data['data'] = data
            print(json.dumps(zabbix_data))
            break
        except (ClientException, ServerException):
            # import traceback
            # traceback.print_exc()
            try_times += 1
            time.sleep(1)
