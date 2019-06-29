# zabbix-account-monitor -- mysql
Aliyun account status monitor with zabbix   

zabbix通过阿里云api 自动发现、监控阿里云实例的有效期和账户余额

## 使用方法
### 注意事项
1. 通过添加执行参数-s，脚本支持讲发现的实例保存到MySQL数据库（只支持python3）,如无需保存到数据库，脚本也支持python2
2. 实例发现可能执行时间会较长，请合理设置zabbix的Timeou时间

### 环境要求
python = 2.7+ 或 python3.6+  其他版本未测试

### 安装依赖包
```shell
# python3
/usr/bin/env pip3 -r requirements.txt
```

### 使用方法
1. 从阿里云控制台获取 **AccessKey** ,并修改脚本中的 **API_Key** 与 **API_Secret**
2. 修改区域 **RegionId**
3. 将aliyun-account-monitor.py脚本放置于以下目录
    ```shell
    cp aliyun-account-monitor.py /etc/zabbix/script
    ```
4. 将aliyun-account.conf文件放置到以下目录
    ```shell
    cp aliyun-account.conf /etc/zabbix/zabbix_agentd.d/
    ```

5. 重启zabbix-agent
6. zabbix控制台导入模板zbx_Aliyun_Account_template.xml，并关联主机
