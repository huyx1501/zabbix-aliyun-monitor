#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: huxy1501

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkr_kvstore.request.v20150101.DescribeInstancesRequest import DescribeInstancesRequest
from aliyunsdkr_kvstore.request.v20150101.DescribeLogicInstanceTopologyRequest import \
    DescribeLogicInstanceTopologyRequest
import json
import time

API_Key = 'Key'
API_Secret = 'Secret'
RegionId = 'cn-shenzhen'  # 阿里云区域代码


class RedisDiscovery(object):
    def __init__(self):
        self.client = AcsClient(API_Key, API_Secret, RegionId)
        self.redis_instance_list = []

    def get_instance_list(self):
        request = DescribeInstancesRequest()
        request.set_accept_format("json")
        response = self.client.do_action_with_exception(request)
        instances = json.loads(response)["Instances"]["KVStoreInstance"]
        for redis_instance in instances:
            try:
                redis_instance_info = dict()
                if redis_instance["ArchitectureType"] == "standard":
                    redis_instance_info["{#REDISINSTANCEID}"] = redis_instance["InstanceId"]
                    redis_instance_info["{#REDISINSTANCENAME}"] = redis_instance["InstanceName"]
                    redis_instance_info["{#TYPE}"] = redis_instance["ArchitectureType"]  # 节点类型
                    redis_instance_info["{#CAPACITY}"] = redis_instance["Capacity"]  # 最大可用内存
                    self.redis_instance_list.append(redis_instance_info)
                    continue
                if redis_instance["ArchitectureType"] == "cluster":
                    node_list = self.get_cluster_node(redis_instance['InstanceId'])
                    for node_info in node_list:
                        redis_instance_info = dict()
                        # 节点ID中的"#"符号不能作为参数，需要先将其替换
                        redis_instance_info["{#REDISINSTANCEID}"] = node_info["NodeId"].replace("#", "NUM")
                        node_name = redis_instance_info["{#REDISINSTANCEID}"].lstrip(redis_instance['InstanceId'])
                        redis_instance_info["{#REDISINSTANCENAME}"] = redis_instance['InstanceName'] + "-" + node_name
                        redis_instance_info["{#TYPE}"] = redis_instance["ArchitectureType"]
                        redis_instance_info["{#CAPACITY}"] = node_info["Capacity"]
                        self.redis_instance_list.append(redis_instance_info)
                    continue
            except Exception as e:
                print(Exception, ":", e)
        else:
            return self.redis_instance_list

    def get_cluster_node(self, ins_id):
        """
        根据主实例ID获取集群中的数据节点信息
        :param ins_id: 主实例ID
        :return: 以列表形式返回数据节点信息
        """
        request = DescribeLogicInstanceTopologyRequest()
        request.set_accept_format("json")
        request.set_InstanceId(ins_id)
        response = self.client.do_action_with_exception(request)
        node_list = json.loads(response)["RedisShardList"]["NodeInfo"]
        return node_list


if __name__ == "__main__":
    zabbix_data = dict()
    try_times = 0
    redis = RedisDiscovery()
    while try_times < 2:
        try:
            data = redis.get_instance_list()
            zabbix_data['data'] = data
            print(json.dumps(zabbix_data))
            break
        except (ClientException, ServerException):
            # import traceback
            # traceback.print_exc()
            try_times += 1
            time.sleep(1)
