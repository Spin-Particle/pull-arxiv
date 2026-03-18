# arXiv 论文工具集

自动爬取 arXiv 论文，使用大模型生成中文总结，并发送到邮箱。

## 功能特点

### 1. 论文日报 (`main.py`)
- 📥 自动爬取 arXiv 指定分类的每日更新论文
- 🤖 使用大语言模型生成中文论文总结
- 📝 输出格式化的 Markdown 日报
- 📧 自动发送日报到邮箱
- ⏰ 支持定时自动运行（北京时间每天 12:00）
- ⚙️ 支持自定义 LLM API（兼容 OpenAI API 格式）

### 2. QCD Sum Rule 论文收集 (`qcdsr.py`)
- 🔍 搜索 arXiv 上与 "QCD sum rule" 相关的论文
- 📚 增量更新到固定文件 `output/QCDSR.md`
- 🔄 自动去重，新论文追加到文件开头
- 🤖 同样使用大模型生成中文摘要
- 📧 有新论文时自动发送邮件通知

### 3. 邮件发送 (`email_sender.py`)
- 📧 支持 QQ邮箱 SMTP 发送
- 🎨 Markdown 自动转换为格式化的 HTML 邮件
- 📎 美观的邮件样式

## 安装

```bash
# 进入项目目录
cd /Users/zhangsan/Desktop/Academy/program/AI/pull-arxiv

# 安装依赖
pip install -r requirements.txt
```

## 配置

编辑 `config.yaml` 文件，设置你的配置：

```yaml
# 大模型配置
llm:
  # API 地址 (支持 OpenAI API 格式的接口)
  url: "https://api.openai.com/v1"
  # API Key
  api_key: "your-api-key-here"
  # 模型名称
  model: "gpt-4o"

# arXiv 爬取配置
arxiv:
  # 论文分类
  categories:
    - "hep-ph"  # High Energy Physics - Phenomenology
    - "hep-ex"  # High Energy Physics - Experiment
  # 每个分类最大爬取数量
  max_results: 100

# 邮件配置 (QQ邮箱)
email:
  # 是否启用邮件发送
  enabled: true
  # SMTP 服务器
  smtp_server: "smtp.qq.com"
  # SMTP 端口 (SSL: 465)
  smtp_port: 465
  # 发件人邮箱 (您的QQ邮箱)
  sender: "your_qq@qq.com"
  # 授权码 (不是QQ密码)
  password: "your_authorization_code"
  # 收件人邮箱
  receiver: "your_qq@qq.com"
```

### 常见 LLM 服务配置示例

**OpenAI**
```yaml
llm:
  url: "https://api.openai.com/v1"
  api_key: "sk-xxx"
  model: "gpt-4o"
```

**其他兼容服务 (如 DeepSeek, 智谱等)**
```yaml
llm:
  url: "https://api.deepseek.com/v1"
  api_key: "xxx"
  model: "deepseek-chat"
```

### QQ邮箱授权码获取方式

1. 登录 QQ邮箱网页版 (mail.qq.com)
2. 点击 **设置** → **账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 开启 **POP3/SMTP服务**
5. 按提示发送短信验证，获取 **授权码**
6. 将授权码填入 `config.yaml` 的 `password` 字段

## 使用方法

### 论文日报

**手动运行**
```bash
python main.py
```

运行后会在 `output/` 目录下生成当天的日报文件，如 `2026-03-18.md`，并自动发送邮件。

**定时自动运行**

```bash
# 启动定时任务（每天 12:00 执行）
python scheduler.py

# 立即执行一次 + 启动定时任务（用于测试）
python scheduler.py --now
```

### QCD Sum Rule 论文收集

```bash
python qcdsr.py
```

- 搜索 arXiv 上标题或摘要包含 "QCD sum rule" 的论文
- 新论文会追加到 `output/QCDSR.md` 文件开头
- 已有论文会自动去重
- 有新论文时自动发送邮件

### 单独测试邮件发送

```bash
# 测试发送日报
python email_sender.py output/2026-03-18.md

# 测试发送 QCD Sum Rule 合集
python email_sender.py output/QCDSR.md
```

### 使用 crontab 定时运行（推荐）

不占用系统资源，每天自动执行：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天 12:00 执行）
0 12 * * * cd /Users/zhangsan/Desktop/Academy/program/AI/pull-arxiv && /usr/bin/python3 main.py && /usr/bin/python3 qcdsr.py >> cron.log 2>&1

# 保存退出后验证
crontab -l
```

## 输出示例

### 日报格式 (`output/2026-03-18.md`)

```markdown
# arXiv 论文日报 - 2026-03-18

> 本报告自动生成于北京时间 2026-03-18 12:00:00
> 
> 分类：hep-ph (高能物理-唯象学), hep-ex (高能物理-实验)
> 
> 论文数量：5 篇

---

# 1. Paper Title Here

- **作者**: Author A, Author B, ...
- **分类**: hep-ph
- **发布时间**: 2026-03-18 08:30:00
- **链接**: https://arxiv.org/abs/2503.xxxxx

## 简短摘要
本文提出一种...

---
```

### QCD Sum Rule 合集格式 (`output/QCDSR.md`)

```markdown
# QCD Sum Rule 论文合集

> 最后更新：2026-03-18 12:00:00 (北京时间)
> 
> 搜索关键词：QCD sum rule
> 
> 论文总数：10 篇

---

# 1. 最新论文标题

- **作者**: Author A, Author B, ...
- **分类**: hep-ph
- **发布时间**: 2026-03-18 08:30:00
- **链接**: https://arxiv.org/abs/2503.xxxxx

## 简短摘要
本文提出一种...

---

# 2. 较早论文标题
...
```

## 文件结构

```
pull-arxiv/
├── config.yaml          # 配置文件
├── main.py              # 论文日报主脚本
├── qcdsr.py             # QCD sum rule 论文收集脚本
├── email_sender.py      # 邮件发送模块
├── scheduler.py         # 定时任务脚本
├── requirements.txt     # Python 依赖
├── README.md            # 说明文档
├── scheduler.log        # 定时任务日志（运行后生成）
└── output/              # 输出目录
    ├── 2026-03-18.md    # 按日期生成的日报
    └── QCDSR.md         # QCD sum rule 论文合集（增量更新）
```

## 注意事项

1. **arXiv 更新时间**：arXiv 通常在 UTC 时间下午更新，对应北京时间晚上。脚本使用最近 24 小时作为时间窗口来捕获最新论文。

2. **API 费用**：每篇论文会调用一次 LLM API，请注意 API 调用费用。

3. **网络访问**：确保能正常访问 arXiv 和 LLM API 服务。

4. **增量更新**：`qcdsr.py` 会自动去重，多次运行不会重复添加相同论文。

5. **邮件发送**：如果邮件发送失败，请检查：
   - QQ邮箱授权码是否正确
   - 发件人和收件人邮箱是否配置正确
   - 网络是否能访问 smtp.qq.com

## License

MIT


### QCD Sum Rule 合集格式 (`output/QCDSR.md`)

```markdown
# QCD Sum Rule 论文合集

> 最后更新：2026-03-18 12:00:00 (北京时间)
> 
> 搜索关键词：QCD sum rule
> 
> 论文总数：10 篇

---

# 1. 最新论文标题

- **作者**: Author A, Author B, ...
- **分类**: hep-ph
- **发布时间**: 2026-03-18 08:30:00
- **链接**: https://arxiv.org/abs/2503.xxxxx

## 简短摘要
本文提出一种...

---

# 2. 较早论文标题
...
```

## 文件结构

```
pull-arxiv/
├── config.yaml          # 配置文件
├── main.py              # 论文日报主脚本
├── qcdsr.py             # QCD sum rule 论文收集脚本
├── email_sender.py      # 邮件发送模块
├── scheduler.py         # 定时任务脚本
├── requirements.txt     # Python 依赖
├── README.md            # 说明文档
├── scheduler.log        # 定时任务日志（运行后生成）
└── output/              # 输出目录
    ├── 2026-03-18.md    # 按日期生成的日报
    └── QCDSR.md         # QCD sum rule 论文合集（增量更新）
```

## 注意事项

1. **arXiv 更新时间**：arXiv 通常在 UTC 时间下午更新，对应北京时间晚上。脚本使用最近 24 小时作为时间窗口来捕获最新论文。

2. **API 费用**：每篇论文会调用一次 LLM API，请注意 API 调用费用。

3. **网络访问**：确保能正常访问 arXiv 和 LLM API 服务。

4. **增量更新**：`qcdsr.py` 会自动去重，多次运行不会重复添加相同论文。

5. **邮件发送**：如果邮件发送失败，请检查：
   - QQ邮箱授权码是否正确
   - 发件人和收件人邮箱是否配置正确
   - 网络是否能访问 smtp.qq.com


## 邮箱接收效果：

![alt text](image.png)
![alt text](image-1.png)



