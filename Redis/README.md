# zabbix-aliyun-monitor -- redis
Aliyun redis status monitor with zabbix   
   
zabbix通过阿里云api 自动发现、监控阿里云redis实例

## 使用方法
### 注意事项
1. 脚本会收集Redis别名作为监控项名称前缀展示；
2. 对于集群版redis只监控实例下的数据节点，因为整体实例的监控存在5分钟延迟；
3. 不要使用默认别名和中文别名（zabbix不识别）；
4、目前支持redis集群版和单机版，其他版本未测试

### 环境要求
python = 2.7+ 或 python3.6+  其他版本未测试

### 安装依赖包
```shell
# python2
/usr/bin/env pip2 -r requirements.txt
```
```shell
# python3
/usr/bin/env pip3 -r requirements.txt
```

### 使用方法
1. 从阿里云控制台获取 **AccessKey** ,并修改脚本中的 **API_Key** 与 **API_Secret**
2. 修改区域 **RegionId**
3. 将check和discovery两个脚本放置于以下目录
```shell
cp check_redis.py discovery_redis.py /etc/zabbix/script
```
4. 将aliyun-redis.conf文件放置到以下目录，并修改其中的python版本信息（默认python3）
```
cp aliyun-redis.conf /etc/zabbix/zabbix_agentd.d/
```

**由于有重试机制，请修改zabbix server和agent配置中的Timeout参数为10秒以上**

5. 重启zabbix-agent
6. zabbix控制台导入模板zbx_Aliyun_Redis_templates.xml，并关联主机
