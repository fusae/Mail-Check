# 舆情监控系统

自动监控Gmail邮件，提取舆情数据，使用AI判断是否为负面舆情。

## 功能特性

- ✅ 自动监控Gmail邮件
- ✅ 提取舆情链接和数据
- ✅ AI智能判断负面舆情
- ✅ 控制台实时输出
- ✅ 数据库记录处理历史

## 系统架构

```
Mail_Check/
├── config/
│   ├── config.yaml          # 配置文件
│   └── hospitals.txt       # 医院名单（备用）
├── src/
│   ├── email_monitor.py    # 邮件监控模块
│   ├── link_extractor.py   # 链接提取模块
│   ├── content_fetcher.py  # 内容获取模块
│   ├── sentiment_analyzer.py # AI分析模块
│   └── main.py            # 主程序
├── logs/                   # 日志目录
├── data/                   # 数据目录
│   └── processed_emails.db # SQLite数据库
├── requirements.txt         # Python依赖
└── README.md             # 本文件
```

## 安装步骤

### 1. 安装Python依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装Playwright浏览器
playwright install chromium
```

服务器部署及 Playwright 依赖/镜像源配置请参考 `部署指南.md`。

### 2. 配置系统

复制配置模板并修改敏感信息：

```bash
# 复制配置模板
cp config/config.yaml.example config/config.yaml

# 编辑配置文件
vim config/config.yaml  # 或使用其他编辑器
```

**需要修改的关键配置：**

```yaml
# 邮箱配置
email:
  imap_server: "imap.qq.com"  # 或 imap.gmail.com
  email_address: "your_email@qq.com"
  app_password: "your_app_password"  # 应用专用密码

# 通知配置（选择一个）
notification:
  provider: "wechat_work"  # 或 "telegram"
  wechat_work:
    webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_WEBHOOK_KEY"
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"

# AI配置
ai:
  api_key: "YOUR_API_KEY"  # 智谱AI API密钥

# 反馈服务配置
feedback:
  link_base_url: "http://your-server:5002/feedback"
  link_secret: "CHANGE_THIS_TO_RANDOM_SECRET"
```

## 运行方法

### 测试单个模块

```bash
# 测试邮件监控
cd src
python email_monitor.py

# 测试链接提取
python link_extractor.py

# 测试内容获取
python content_fetcher.py

# 测试AI分析
python sentiment_analyzer.py
```

### 运行主程序

```bash
# 在项目根目录
cd src
python main.py
```

程序将：
1. 每5分钟检查一次新邮件
2. 自动处理舆情邮件
3. AI判断负面舆情
4. 控制台输出结果

## 输出示例

发现负面舆情时，控制台会显示：

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
⚠️ 发现负面舆情！
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

医院: XX市第一人民医院
来源: 抖音
标题: 网红疑患性病病历流传
内容摘要: 医院XX市第一人民医院的病历在网络流传...
AI判断: 医疗隐私泄露，对医院声誉造成负面影响
严重程度: high

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

## 数据库

### 处理的邮件
```sql
SELECT * FROM processed_emails;
```

### 负面舆情记录
```sql
SELECT * FROM negative_sentiments ORDER BY processed_at DESC;
```

## 日志

日志文件：`logs/sentiment_monitor.log`

查看日志：
```bash
tail -f logs/sentiment_monitor.log
```

## 故障排查

### 连接Gmail失败
- 检查应用专用密码是否正确
- 确保开启了IMAP服务

### 提取不到舆情ID
- 检查网络连接
- 查看日志中的错误信息

### AI分析失败
- 检查API Key是否有效
- 确认智谱AI账号余额

## 配置说明

### 检查间隔
修改 `config.yaml` 中的 `runtime.check_interval`（单位：秒）

```yaml
runtime:
  check_interval: 300  # 5分钟检查一次
```

### 日志级别
修改 `config.yaml` 中的 `runtime.log_level`

```yaml
runtime:
  log_level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

## 后续开发

- [ ] 添加电话通知功能
- [ ] 支持多医院监控
- [ ] Web界面展示
- [ ] 舆情趋势分析

## 技术支持

如有问题，请查看日志文件或联系开发者。
