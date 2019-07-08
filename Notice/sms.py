#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: huxy1501

from optparse import OptionParser
import sys
import json
import traceback
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException

API_Key = 'ID'
API_Secret = 'Secret'
RegionId = "cn-hangzhou"  # 短信服务固定值，请勿修改
SignName = "XXX"  # 短信签名
TemplateCode = "SMS_XXX"  # 短信模板ID
TemplateVar = "message"  # 模板中的变量名


class AliSms(object):
    def __init__(self):
        self.client = AcsClient(
            API_Key,
            API_Secret,
            RegionId
        )

    def send_sms(self, phone, message):
        """
        发送短信
        :param str phone: 目标手机号
        :param str message: 消息内容
        :return: 发送成功返回"OK",否则返回False
        """
        request = CommonRequest()
        request.set_accept_format("json")
        request.set_domain("dysmsapi.aliyuncs.com")
        request.set_method("POST")
        request.set_protocol_type("https")  # 协议http或https
        request.set_version("2017-05-25")  # 短信接口版本
        request.set_action_name("SendSms")  # 接口名

        request.add_query_param("RegionId", RegionId)
        request.add_query_param("SignName", SignName)
        request.add_query_param("PhoneNumbers", phone)
        request.add_query_param("TemplateCode", TemplateCode)
        request.add_query_param("TemplateParam", self._get_params(message))

        response = self.client.do_action_with_exception(request)
        return json.loads(response)["Message"]

    @staticmethod
    def _get_params(message):
        message_dic = dict()
        message_dic[TemplateVar] = message
        return json.dumps(message_dic)


def main():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage)
    parser.add_option("-p", "--phone", action="store", dest="PhoneNumber", type="string", help="Target phone number")

    parser.add_option("-m", "--message", action="store", dest="Message", type="string", help="Sms message to send")

    (options, args) = parser.parse_args()
    if len(sys.argv) <= 1:
        parser.print_help()
        return
    try:
        phone = options.PhoneNumber
        message = options.Message
        assert phone and message
        sender = AliSms()
        print("Result: %s" % sender.send_sms(phone, message))
    except (ClientException, ServerException, json.JSONDecodeError, KeyError, ValueError):
        traceback.print_exc()
    except AssertionError:
        parser.print_help()
        return


if __name__ == "__main__":
    main()
