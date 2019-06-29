# zabbix-aliyun-monitor
Aliyun service status monitor with zabbix   

zabbix通过阿里云api 自动发现、监控阿里云产品性能指标，目前支持Redis和RDS for MySQL

**由于有重试机制，请修改zabbix server和agent配置中的Timeout参数为10秒以上**

## 环境要求
python = 2.7+ 或 python3.6+  其他版本未测试

## 安装依赖包
进入到项目目录中，如Redis目录，执行
```shell
# python2
/usr/bin/env pip2 -r requirements.txt
```
```shell
# python3
/usr/bin/env pip3 -r requirements.txt
```

## 使用方法
1. 从阿里云控制台获取 **AccessKey** ,并修改脚本中的 **API_Key** 与 **API_Secret**
2. 修改区域 **RegionId**
3. 将check和discovery两个脚本放置于以下目录
    ```shell
    cp check_XX.py discovery_XX.py /etc/zabbix/script
    ```
4. 将zabbix客户端文件放置到/etc/zabbix/zabbix_agentd.d/，并修改其中的python版本信息（默认python3）
5. 重启zabbix-agent
6. zabbix控制台导入模板，并关联主机
