#!/usr/bin/env python3
"""
邮件发送模块
使用 QQ邮箱 SMTP 发送论文日报
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from datetime import datetime, timezone, timedelta
import yaml
from pathlib import Path


def load_email_config(config_path: str = "config.yaml") -> dict:
    """加载邮件配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("email", {})


def markdown_to_html(markdown_content: str) -> str:
    """将 Markdown 内容简单转换为 HTML"""
    import re
    
    html = markdown_content
    
    # 转换标题
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    
    # 转换粗体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # 转换链接
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
    
    # 转换引用块
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    
    # 转换列表项
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    
    # 转换水平线
    html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
    
    # 转换段落（连续的非标签行）
    lines = html.split('\n')
    result = []
    in_paragraph = False
    paragraph_content = []
    
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<'):
            if not in_paragraph:
                in_paragraph = True
                paragraph_content = [stripped]
            else:
                paragraph_content.append(stripped)
        else:
            if in_paragraph:
                result.append('<p>' + ' '.join(paragraph_content) + '</p>')
                in_paragraph = False
                paragraph_content = []
            result.append(line)
    
    if in_paragraph:
        result.append('<p>' + ' '.join(paragraph_content) + '</p>')
    
    html = '\n'.join(result)
    
    # 包装成完整 HTML
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        h3 {{
            color: #7f8c8d;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        blockquote {{
            background-color: #f9f9f9;
            border-left: 4px solid #3498db;
            margin: 10px 0;
            padding: 10px 15px;
            color: #666;
        }}
        li {{
            margin: 5px 0;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 20px 0;
        }}
        strong {{
            color: #2c3e50;
        }}
    </style>
</head>
<body>
{html}
</body>
</html>"""
    
    return html_template


def send_email(subject: str, content: str, content_type: str = "html") -> bool:
    """
    发送邮件
    
    Args:
        subject: 邮件主题
        content: 邮件内容
        content_type: 内容类型 ("html" 或 "plain")
    
    Returns:
        是否发送成功
    """
    config = load_email_config()
    
    if not config.get("enabled", False):
        print("邮件发送未启用")
        return False
    
    try:
        # 创建邮件
        message = MIMEMultipart()
        # 使用 formataddr 设置标准格式的邮件头
        message['From'] = formataddr(('arXiv论文日报', config['sender']))
        message['To'] = formataddr(('收件人', config['receiver']))
        message['Subject'] = Header(subject, 'utf-8')
        
        # 添加内容
        if content_type == "html":
            msg_content = MIMEText(content, 'html', 'utf-8')
        else:
            msg_content = MIMEText(content, 'plain', 'utf-8')
        message.attach(msg_content)
        
        # 发送邮件
        smtp = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        smtp.login(config['sender'], config['password'])
        smtp.sendmail(config['sender'], [config['receiver']], message.as_string())
        smtp.quit()
        
        print(f"邮件发送成功: {subject}")
        return True
        
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


def send_daily_report(md_file_path: str) -> bool:
    """
    发送论文日报邮件
    
    Args:
        md_file_path: Markdown 文件路径
    
    Returns:
        是否发送成功
    """
    md_path = Path(md_file_path)
    
    if not md_path.exists():
        print(f"文件不存在: {md_file_path}")
        return False
    
    # 读取 Markdown 内容
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # 获取日期
    date_str = md_path.stem  # 文件名即日期，如 2026-03-18
    
    # 生成邮件主题
    subject = f"arXiv 论文日报 - {date_str}"
    
    # 转换为 HTML
    html_content = markdown_to_html(md_content)
    
    # 发送邮件
    return send_email(subject, html_content, "html")


def send_qcdsr_report(md_file_path: str) -> bool:
    """
    发送 QCD Sum Rule 论文合集邮件
    
    Args:
        md_file_path: Markdown 文件路径
    
    Returns:
        是否发送成功
    """
    md_path = Path(md_file_path)
    
    if not md_path.exists():
        print(f"文件不存在: {md_file_path}")
        return False
    
    # 读取 Markdown 内容
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # 获取当前时间
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    # 生成邮件主题
    subject = f"QCD Sum Rule 论文合集更新 - {now}"
    
    # 转换为 HTML
    html_content = markdown_to_html(md_content)
    
    # 发送邮件
    return send_email(subject, html_content, "html")


if __name__ == "__main__":
    # 测试发送
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if "QCDSR" in file_path:
            send_qcdsr_report(file_path)
        else:
            send_daily_report(file_path)
    else:
        print("用法: python email_sender.py <md_file_path>")