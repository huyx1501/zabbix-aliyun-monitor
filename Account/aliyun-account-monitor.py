#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: huxy1501

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkbssopenapi.request.v20171214.QueryAccountBalanceRequest import QueryAccountBalanceRequest
from aliyunsdkbssopenapi.request.v20171214.QueryAvailableInstancesRequest import QueryAvailableInstancesRequest
import json
import sys
from datetime import datetime, timedelta
from optparse import OptionParser
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import traceback

# 请修改以下三个值
API_Key = 'ID'
API_Secret = 'Secret'
RegionId = 'cn-shenzhen'  # 阿里云区域代码

# 请修改mysql连接信息
MySQL_Host = '192.168.1.1'
MySQL_Port = '3306'
MySQL_User = 'root'
MySQL_Pass = '12345678'
MySQL_DB_Name = 'zabbix_data'

engine = create_engine(
    "mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8".format(MySQL_User, MySQL_Pass, MySQL_Host, MySQL_Port, MySQL_DB_Name))
BaseClass = declarative_base()

CreateTimeEnd = datetime.strftime(datetime.utcnow() + timedelta(days=1), "%Y-%m-%dT00:00:00Z")
EndTimeStart = datetime.strftime(datetime.utcnow() + timedelta(days=1), "%Y-%m-%dT00:00:00Z")
EndTimeEnd = datetime.strftime(datetime.utcnow() + timedelta(days=1095), "%Y-%m-%dT00:00:00Z")  # 最多查询3年内过期的实例


class Instances(BaseClass):
    """
    实例详情表
    """
    __tablename__ = "Instances"
    InstanceId = Column(String(64), primary_key=True, comment="实例ID")
    InstanceName = Column(String(255), comment="实例名")
    ZoneId = Column(String(64), comment="实例所在区域ID")
    Engine = Column(String(64), comment="实例类型/系统")
    InstanceClass = Column(String(128), comment="实例规格")
    NetworkType = Column(String(64), comment="实例网络类型")
    ArchitectureType = Column(String(64), comment="实例架构")
    CreateTime = Column(String(128), comment="实例创建时间")
    EndTime = Column(String(64), comment="实例有效期")
    RenewalDays = Column(Integer, comment="剩余天数")

    def __repr__(self):
        return {
            "InstanceId": self.InstanceId,
            "InstanceName": self.InstanceName,
            "ZoneId": self.ZoneId,
            "Engine": self.Engine,
            "InstanceClass": self.InstanceClass,
            "NetworkType": self.NetworkType,
            "ArchitectureType": self.ArchitectureType,
            "CreateTime": self.CreateTime,
            "EndTime": self.EndTime,
            "RenewalDays": self.RenewalDays
        }


class AliQuery(object):
    def __init__(self, sql_session=None):
        self.sql_session = sql_session
        self.instance_details = list()
        self.AcsClient = AcsClient(API_Key, API_Secret, RegionId)

    def get_balance(self):
        """
        获取账户可用余额
        :return: 返回余额的浮点数形式
        """
        request = QueryAccountBalanceRequest()
        request.set_accept_format("json")
        response = self.AcsClient.do_action_with_exception(request)
        amount = json.loads(response)["Data"]["AvailableAmount"]
        return float(amount.replace(",", ""))

    def get_instances(self, ins_id="", ins_type="", page_num=1, page_size=50):
        """
        获取所有有效实例或指定类型的实例
        :param str ins_id: 实例id，不指定ID默认查询所有有效实例
        :param str ins_type: 实例类型，不指定类型时获取所有实例信息
        :param int page_num: 翻页指针
        :param int page_size: 结果页大小
        :return list: 以列表嵌套字典的形式返回获取到的实例信息
        """
        request = QueryAvailableInstancesRequest()
        request.set_accept_format("json")
        request.set_EndTimeStart(EndTimeStart)  # 设置查询的实例结束时间，不查询已过期的实例
        request.set_EndTimeEnd(EndTimeEnd)
        request.set_CreateTimeEnd(CreateTimeEnd)
        request.set_SubscriptionType("Subscription")
        request.set_PageSize(page_size)
        if ins_id:
            request.set_InstanceIDs(ins_id)
        received_item = 0
        while True:
            # print("正在处理第[%d]页" % page_num)
            request.set_PageNum(page_num)
            response = self.AcsClient.do_action_with_exception(request)
            response_dic = json.loads(response)
            total_count = response_dic["Data"]["TotalCount"]
            instance_list = response_dic["Data"]["InstanceList"]
            for instance in instance_list:
                if not ins_type:  # 未指定实例类型
                    instance_detail = self.get_instance_info(instance)
                else:  # 指定了实例类型时，查询到实例类型和要求的相匹配
                    if ins_type == instance["ProductCode"]:
                        instance_detail = self.get_instance_info(instance)
                    else:
                        continue
                if self.sql_session:
                    self.update_or_insert(instance_detail)
                self.instance_details.append(self.get_upper(instance_detail))
            else:
                received_item += page_size
            if total_count > received_item:  # 翻页
                page_num += 1
            else:
                if self.sql_session:
                    self.sql_session.commit()  # 提交数据库
                    self.sql_session.close()
                return self.instance_details

    def get_instance_info(self, instance):
        """
        根据实例基本信息查询详细信息
        :param dict instance: 实例基本信息
        :return dict: 返回实例详细信息
        """
        ins_type = instance["ProductCode"]
        if hasattr(self, ins_type):
            instance_detail = getattr(self, ins_type)(instance)
        else:  # 无法获取更多详细信息时取部分QueryAvailableInstancesRequest得到的值
            instance_detail = {
                "InstanceId": instance["InstanceID"],
                "InstanceName": instance["InstanceID"],
                "ZoneId": "",
                "Engine": instance["ProductCode"],
                "InstanceClass": "",
                "NetworkType": "",
                "ArchitectureType": "",
                "CreateTime": self.get_cst_from_utc(instance["CreateTime"]),
                "EndTime": self.get_cst_from_utc(instance["EndTime"]),
                "RenewalDays": self.get_days(instance["EndTime"])
            }
        return instance_detail

    def ecs(self, instance):
        """
        获取ecs实例的详细信息并进行过滤后返回
        :param instance: 实例基本信息，必须包含实例ID和创建和到期时间
        :return dict: 返回实例详细信息
        """
        from aliyunsdkecs.request.v20140526.DescribeInstanceAttributeRequest import DescribeInstanceAttributeRequest
        ins_id = instance["InstanceID"]
        request = DescribeInstanceAttributeRequest()
        request.set_accept_format("json")
        request.set_InstanceId(ins_id)
        response = self.AcsClient.do_action_with_exception(request)
        instance_attrib = json.loads(response)
        try:
            instance_name = instance_attrib["InstanceName"]
        except KeyError:  # 未设置实例别名时会导致KeyError
            instance_name = ""
        instance_info = {
            "InstanceId": ins_id,
            "InstanceName": instance_name if instance_name else ins_id,
            "ZoneId": instance_attrib["ZoneId"],
            "Engine": instance_attrib["ImageId"],  # centos_6_xx
            "InstanceClass": instance_attrib["InstanceType"],  # ecs.sn2ne.xx
            "NetworkType": instance_attrib["InstanceNetworkType"],  # vpc
            "ArchitectureType": "",  # ECS 无此属性
            "CreateTime": self.get_cst_from_utc(instance["CreateTime"]),
            "EndTime": self.get_cst_from_utc(instance["EndTime"]),
            "RenewalDays": self.get_days(instance["EndTime"])
        }
        return instance_info

    def redisa(self, instance):
        """
        获取redis实例的详细信息并进行过滤后返回
        :param instance: 实例基本信息，必须包含实例ID和创建和到期时间
        :return dict: 返回实例详细信息
        """
        from aliyunsdkr_kvstore.request.v20150101.DescribeInstanceAttributeRequest import \
            DescribeInstanceAttributeRequest
        ins_id = instance["InstanceID"]
        request = DescribeInstanceAttributeRequest()
        request.set_accept_format("json")
        request.set_InstanceId(ins_id)
        response = self.AcsClient.do_action_with_exception(request)
        instance_attrib = json.loads(response)["Instances"]["DBInstanceAttribute"][0]
        try:
            instance_name = instance_attrib["InstanceName"]
        except KeyError:  # 未设置实例别名时会导致KeyError
            instance_name = ""
        instance_info = {
            "InstanceId": ins_id,
            "InstanceName": instance_name if instance_name else ins_id,
            "ZoneId": instance_attrib["ZoneId"],  # cn-shenzhen-a
            "Engine": instance_attrib["Engine"],  # Redis
            "InstanceClass": instance_attrib["InstanceClass"],  # redis.logic.sharding.2g.2db.xx
            "NetworkType": instance_attrib["NetworkType"],  # Classic
            "ArchitectureType": instance_attrib["ArchitectureType"],  # cluster
            "CreateTime": self.get_cst_from_utc(instance["CreateTime"]),
            "EndTime": self.get_cst_from_utc(instance["EndTime"]),
            "RenewalDays": self.get_days(instance["EndTime"])
        }
        return instance_info

    def rds(self, instance):
        """
        获取rds实例的详细信息并进行过滤后返回
        :param instance: 实例基本信息，必须包含实例ID和创建和到期时间
        :return dict: 返回实例详细信息
        """
        from aliyunsdkrds.request.v20140815.DescribeDBInstanceAttributeRequest import DescribeDBInstanceAttributeRequest
        ins_id = instance["InstanceID"]
        request = DescribeDBInstanceAttributeRequest()
        request.set_accept_format("json")
        request.set_DBInstanceId(ins_id)
        response = self.AcsClient.do_action_with_exception(request)
        instance_attrib = json.loads(response)["Items"]["DBInstanceAttribute"][0]
        try:
            instance_name = instance_attrib["DBInstanceDescription"]
        except KeyError:  # 未设置实例别名时会导致KeyError
            instance_name = ""
        instance_info = {
            "InstanceId": ins_id,
            "InstanceName": instance_name if instance_name else ins_id,
            "ZoneId": instance_attrib["ZoneId"],
            "Engine": instance_attrib["Engine"],
            "InstanceClass": instance_attrib["DBInstanceClass"],
            "NetworkType": instance_attrib["InstanceNetworkType"],
            "ArchitectureType": instance_attrib["Category"],
            "CreateTime": self.get_cst_from_utc(instance["CreateTime"]),
            "EndTime": self.get_cst_from_utc(instance["EndTime"]),
            "RenewalDays": self.get_days(instance["EndTime"])
        }
        return instance_info

    def dds(self, instance):
        """
        获取mongodb实例的详细信息并进行过滤后返回
        :param instance: 实例基本信息，必须包含实例ID和创建和到期时间
        :return dict: 返回实例详细信息
        """
        from aliyunsdkdds.request.v20151201.DescribeDBInstanceAttributeRequest import DescribeDBInstanceAttributeRequest
        ins_id = instance["InstanceID"]
        request = DescribeDBInstanceAttributeRequest()
        request.set_accept_format("json")
        request.set_DBInstanceId(ins_id)
        response = self.AcsClient.do_action_with_exception(request)
        instance_attrib = json.loads(response)["DBInstances"]["DBInstance"][0]
        try:
            instance_name = instance_attrib["DBInstanceDescription"]
        except KeyError:  # 未设置实例别名时会导致KeyError
            instance_name = ""
        instance_info = {
            "InstanceId": ins_id,
            "InstanceName": instance_name if instance_name else ins_id,
            "ZoneId": instance_attrib["ZoneId"],
            "Engine": instance_attrib["Engine"],
            "InstanceClass": instance_attrib["DBInstanceClass"],
            "NetworkType": instance_attrib["NetworkType"],
            "ArchitectureType": instance_attrib["DBInstanceType"],
            "CreateTime": self.get_cst_from_utc(instance["CreateTime"]),
            "EndTime": self.get_cst_from_utc(instance["EndTime"]),
            "RenewalDays": self.get_days(instance["EndTime"])
        }
        return instance_info

    def update_or_insert(self, instance):
        """
        插入或更新信息到数据库
        :param dict instance: 要更新或插入的数据
        :return: None
        """
        sql_data = self.sql_session.query(Instances).filter_by(InstanceId=instance["InstanceId"]).first()
        if sql_data:  # 存在记录则更新
            sql_data.InstanceName = instance["InstanceName"]
            sql_data.ZoneId = instance["ZoneId"]
            sql_data.Engine = instance["Engine"]
            sql_data.InstanceClass = instance["InstanceClass"]
            sql_data.NetworkType = instance["NetworkType"]
            sql_data.ArchitectureType = instance["ArchitectureType"]
            sql_data.CreateTime = instance["CreateTime"]
            sql_data.EndTime = instance["EndTime"]
            sql_data.RenewalDays = instance["RenewalDays"]
        else:  # 不存在则插入新记录
            sql_data = Instances(**instance)
            self.sql_session.add(sql_data)  # 添加到数据库

    @staticmethod
    def get_cst_from_utc(utc_time_str):
        """
        将字符串的UTC时间转换成CST时间
        :param str utc_time_str: 字符串格式的UTC时间
        :return str: 字符串格式的CST时间
        """
        cst_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
        return cst_time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def get_days(end_date):
        """
        获取当前时间距离指定日期的天数
        :param str end_date: 结束日志
        :return int: 返回天数
        """
        end_date = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")
        today = datetime.utcnow()
        days = (end_date - today).days  # 不足一天算0天
        return days

    @staticmethod
    def get_upper(ins_info):
        """
        将zabbix自动发现所需字段进行特殊处理
        :param dict ins_info:
        :return dict :
        """
        new_dict = dict()
        for k, v in ins_info.items():
            if k in ["InstanceId", "InstanceName", "Engine"]:
                new_dict["{#" + k.upper() + "}"] = v  # 格式化为zabbix宏格式
            else:
                new_dict[k] = v
        return new_dict


def main():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage)
    parser.add_option("-k", "--key", action="store", dest="KEY", type="string", default="balance",
                      help="Which key to fetch")

    parser.add_option("-t", "--type", action="store", dest="TYPE", type="string", default="",
                      help="Instance type, e.g. ecs/rds/dds/redisa etc...")

    parser.add_option("-i", "--id", action="store", dest="ID", type="string", default="",
                      help="Which key to fetch")

    parser.add_option("-s", "--store", action="store_true", dest="STORE", default=False,
                      help="Store instance data in mysql")

    (options, args) = parser.parse_args()
    if len(sys.argv) <= 1:
        parser.print_help()
        return
    try:
        key = options.KEY
        version = sys.version
        if options.STORE and version.startswith("3"):
            if options.KEY == "discovery" and not options.TYPE:
                BaseClass.metadata.drop_all(engine)  # 删除表
            BaseClass.metadata.create_all(engine)  # 创建数据表
            session_class = sessionmaker(bind=engine)
            session = session_class()  # 创建会话
            query = AliQuery(session)  # 创建带SQL会话的类实例
        else:
            query = AliQuery()

        if key == "balance":
            balance = query.get_balance()
            print(balance)
            return

        if key == "discovery":
            instances = query.get_instances(ins_type=options.TYPE)
            if instances:
                # print("处理成功，累计处理实例[%d]个" % len(instance_details))
                data = {"data": instances}
                print(json.dumps(data))
                return

        if key == "check":
            if not options.ID:
                return
            instance_info = query.get_instances(options.ID)
            print(instance_info[0]["RenewalDays"])

    except (ValueError, IndexError, KeyError, ClientException, ServerException):
        traceback.print_exc()


if __name__ == "__main__":
    main()
