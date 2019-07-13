# zabbix-aliyun-sms-notice
通过阿里云短信服务发送Zabbix监控告警

## 环境要求
python = 2.7+ 或 python3.6+  其他版本未测试

## 安装依赖包
```shell
# python3
/usr/bin/env pip3 -r requirements.txt
```
```shell
# python2
/usr/bin/env pip2 -r requirements.txt
```

## 使用方法
1. 从阿里云控制台获取 **AccessKey** ,并修改脚本中的 **API_Key** 与 **API_Secret**
2. 创建阿里云短信签名和模板，模板内容需要指定一个变量，参考示例：
```
系统警报：${message}，请及时处理
```
3. 修改脚本中的**SignName**(短信签名)、**TemplateCode**(短信模板ID)、**TemplateVar**(模板中的变量名)
4. 将sms.py放到zabbix server 的AlertScriptsPath配置指定的目录中，默认为
```
/usr/lib/zabbix/alertscripts
```
修改脚本的执行权限
```shell
chmod +x /usr/lib/zabbix/alertscripts/sms.py
```
**注意：如果不希望使用系统默认python版本，请修改sms.py第一行为你选择的版本**
```python
#!/usr/bin/env python
```
5. 在Zabbix控制台创建报警媒介类型-->脚本，添加两个脚本参数
```
-p {ALERT.SENDTO}
-m {ALERT.MESSAGE}
```
6、在“动作”中设置通过新建的报警类型发送警报
