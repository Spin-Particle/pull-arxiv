#!/usr/bin/env python3
"""
邮件发送模块
使用 QQ邮箱 SMTP 发送论文日报
"""

import smtplib
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
from datetime import datetime, timezone, timedelta
from io import BytesIO
import yaml
from pathlib import Path


def load_email_config(config_path: str = "config.yaml") -> dict:
    """加载邮件配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("email", {})


def clean_latex(text: str) -> str:
    """清理 LaTeX 公式，转为可读纯文本"""
    # 处理行间公式 $$...$$
    text = re.sub(r'\$\$(.+?)\$\$', r'[\1]', text, flags=re.DOTALL)
    # 处理行内公式 $...$
    text = re.sub(r'\$(.+?)\$', r'[\1]', text)
    # 处理 \textsc{...} 等命令
    text = re.sub(r'\\textsc\{(.+?)\}', r'\1', text)
    text = re.sub(r'\\mathrm\{(.+?)\}', r'\1', text)
    text = re.sub(r'\\rm\{(.+?)\}', r'\1', text)
    text = re.sub(r'\\overline\{(.+?)\}', r'\1-bar', text)
    text = re.sub(r'\\bar\{(.+?)\}', r'\1-bar', text)
    text = re.sub(r'\\frac\{(.+?)\}\{(.+?)\}', r'\1/\2', text)
    text = re.sub(r'\\sqrt\{(.+?)\}', r'sqrt(\1)', text)
    text = re.sub(r'\\mathcal\{(.+?)\}', r'\1', text)
    text = re.sub(r'\\mathbb\{(.+?)\}', r'\1', text)
    text = re.sub(r'\\left\\?', '', text)
    text = re.sub(r'\\right\\?', '', text)
    # 清理常见 LaTeX 命令
    text = text.replace('\\bar{', '')
    text = text.replace('\\hat{', '')
    text = text.replace('\\tilde{', '')
    text = text.replace('\\vec{', '')
    text = re.sub(r'\\[a-zA-Z]+', '', text)  # 移除剩余 LaTeX 命令
    # 清理残留的花括号
    text = re.sub(r'[{}]', '', text)
    return text


def markdown_to_plain_text(markdown_content: str) -> str:
    """将 Markdown 转为干净的纯文本，用于降级发送"""
    text = markdown_content
    # 清理 LaTeX 公式
    text = clean_latex(text)
    # 移除 Markdown 链接，只保留文本和 URL
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    # 移除粗体标记
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # 移除斜体标记
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # 移除引用标记
    text = re.sub(r'^> ', '  ', text, flags=re.MULTILINE)
    # 保留标题标记和分隔线
    return text


def _build_smtp_message(subject: str, config: dict) -> MIMEMultipart:
    """创建基础邮件消息（不含正文）"""
    message = MIMEMultipart()
    # 注意：From 显示名称不能包含 "arXiv" 等知名机构名，否则会触发 QQ 邮箱反伪装/反钓鱼策略
    message['From'] = formataddr(('论文日报推送', config['sender']))
    message['To'] = formataddr(('收件人', config['receiver']))
    message['Subject'] = Header(subject, 'utf-8')
    return message


def _smtp_send(config: dict, message: MIMEMultipart) -> bool:
    """通过 SMTP 发送邮件"""
    smtp = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
    smtp.login(config['sender'], config['password'])
    smtp.sendmail(config['sender'], [config['receiver']], message.as_string())
    smtp.quit()
    return True


def markdown_to_html(markdown_content: str) -> str:
    """将 Markdown 内容简单转换为 HTML"""
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
            font-size: 1.5em;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            font-size: 1.17em;
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


def _is_content_rejected_error(e: Exception) -> bool:
    """判断是否为内容被拒绝的错误（550 inappropriate content）"""
    error_str = str(e)
    return '550' in error_str and 'inappropriate' in error_str.lower()


def send_email(subject: str, content: str, content_type: str = "html") -> bool:
    """
    发送邮件，带自动降级策略
    
    策略：
    1. 尝试 HTML 格式发送
    2. 若因内容被拒(550)，降级为纯文本重试
    3. 若纯文本也被拒，降级为附件方式发送
    
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
    
    # ========== 第一次尝试：原始方式发送 ==========
    try:
        message = _build_smtp_message(subject, config)
        if content_type == "html":
            msg_content = MIMEText(content, 'html', 'utf-8')
        else:
            msg_content = MIMEText(content, 'plain', 'utf-8')
        message.attach(msg_content)
        _smtp_send(config, message)
        print(f"邮件发送成功: {subject}")
        return True
    except Exception as e:
        if not _is_content_rejected_error(e):
            print(f"邮件发送失败: {e}")
            return False
        print(f"HTML 发送被拒绝(550)，尝试纯文本降级发送...")
    
    # ========== 第二次尝试：纯文本降级 ==========
    time.sleep(2)
    try:
        plain_content = markdown_to_plain_text(content)
        message = _build_smtp_message(subject, config)
        msg_content = MIMEText(plain_content, 'plain', 'utf-8')
        message.attach(msg_content)
        _smtp_send(config, message)
        print(f"邮件发送成功（纯文本降级）: {subject}")
        return True
    except Exception as e:
        if not _is_content_rejected_error(e):
            print(f"邮件发送失败: {e}")
            return False
        print(f"纯文本发送也被拒绝(550)，尝试附件方式发送...")
    
    # ========== 第三次尝试：作为 HTML 附件发送 ==========
    time.sleep(2)
    try:
        message = _build_smtp_message(subject, config)
        # 简短正文
        body_text = subject + "\n\n完整报告见附件。"
        msg_content = MIMEText(body_text, 'plain', 'utf-8')
        message.attach(msg_content)
        
        # HTML 作为附件
        html_bytes = content.encode('utf-8')
        attachment = MIMEBase('text', 'html')
        attachment.set_payload(html_bytes)
        encoders.encode_base64(attachment)
        safe_subject = re.sub(r'[^\w\s-]', '', subject)
        attachment.add_header(
            'Content-Disposition', 'attachment',
            filename=f"{safe_subject}.html"
        )
        message.attach(attachment)
        
        _smtp_send(config, message)
        print(f"邮件发送成功（附件方式）: {subject}")
        return True
    except Exception as e:
        print(f"邮件发送失败（所有方式均失败）: {e}")
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