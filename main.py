#!/usr/bin/env python3
"""
arXiv 论文日报 - 主脚本
爬取 arXiv 上 hep-ph 和 hep-ex 分类的最新论文，使用大模型生成中文总结
"""

import os
import re
import sys
import yaml
import arxiv
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_beijing_date() -> str:
    """获取北京时间日期字符串"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d")


def fetch_paper_ids_from_listing(category: str) -> tuple:
    """
    从 arXiv listing 页面获取当天新论文的 ID 列表
    
    通过抓取 https://arxiv.org/list/{category}/new 页面，
    精确获取当天 arXiv 更新批次中的论文，避免基于时间窗口过滤造成的遗漏。
    
    Args:
        category: 论文分类 (如 'hep-ph')
    
    Returns:
        (new_submission_ids, cross_list_ids) 元组，分别为新提交和交叉列表的论文ID列表
    """
    url = f"https://arxiv.org/list/{category}/new"
    
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; arxiv-daily-bot/1.0)'})
        with urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')
    except (URLError, HTTPError) as e:
        print(f"  获取 listing 页面失败: {e}")
        return [], []
    
    new_ids = []
    cross_ids = []
    
    # 按 <h3> 标签分割页面内容为不同区段
    sections = re.split(r'<h3>', html)
    
    for section in sections:
        # 匹配 "New submissions" 区段
        if re.match(r'\s*New submissions', section):
            ids = re.findall(r'arXiv:(\d+\.\d+)', section)
            new_ids.extend(ids)
        # 匹配 "Cross submissions" 区段（交叉列表）
        elif re.match(r'\s*Cross submissions', section):
            ids = re.findall(r'arXiv:(\d+\.\d+)', section)
            cross_ids.extend(ids)
        # "Replacements" 区段不处理（已存在的论文更新版本）
    
    return new_ids, cross_ids


def get_papers(categories: list, max_results: int = 100) -> list:
    """
    从 arXiv 获取指定分类的论文
    
    通过抓取 arXiv listing 页面（/list/{category}/new）获取当天更新批次的论文 ID，
    再通过 arXiv API 获取论文详细信息。
    这种方式精确匹配 arXiv 每日发布的更新批次，不会因时间窗口估算偏差而遗漏论文。

    Args:
        categories: 论文分类列表
        max_results: 每个分类最大结果数（用于 API 回退模式）

    Returns:
        论文列表
    """
    papers = []
    seen_ids = set()
    
    beijing_tz = timezone(timedelta(hours=8))
    
    # 收集所有分类的论文 ID
    all_paper_ids = []
    
    for category in categories:
        print(f"正在获取 {category} 分类的论文...")
        
        # 从 listing 页面获取当天新论文 ID
        new_ids, cross_ids = fetch_paper_ids_from_listing(category)
        
        if not new_ids and not cross_ids:
            print(f"  {category}: listing 页面未找到新论文")
            continue
        
        print(f"  {category}: 新提交 {len(new_ids)} 篇, 交叉列表 {len(cross_ids)} 篇")
        
        # 合并新提交和交叉列表的论文 ID
        category_ids = new_ids + cross_ids
        
        # 去重（同一论文可能出现在多个分类的交叉列表中）
        unique_ids = [pid for pid in category_ids if pid not in seen_ids]
        for pid in unique_ids:
            seen_ids.add(pid)
        
        all_paper_ids.extend([(pid, category) for pid in unique_ids])
    
    if not all_paper_ids:
        print("未获取到任何论文 ID")
        return papers
    
    # 通过 arXiv API 批量获取论文详细信息
    print(f"正在通过 API 获取 {len(all_paper_ids)} 篇论文的详细信息...")
    
    # 提取所有去重后的 ID
    unique_paper_ids = list(dict.fromkeys(pid for pid, _ in all_paper_ids))
    
    client = arxiv.Client()
    
    # 分批获取（arXiv API 可能对单次请求的 ID 数量有限制）
    batch_size = 50
    seen_entry_ids = set()
    
    for i in range(0, len(unique_paper_ids), batch_size):
        batch = unique_paper_ids[i:i + batch_size]
        
        try:
            search = arxiv.Search(
                id_list=batch,
                max_results=len(batch)
            )
            
            for result in client.results(search):
                if result.entry_id not in seen_entry_ids:
                    seen_entry_ids.add(result.entry_id)
                    updated_beijing = result.updated.astimezone(beijing_tz)
                    papers.append({
                        "title": result.title,
                        "authors": [author.name for author in result.authors],
                        "summary": result.summary,
                        "categories": result.categories,
                        "pdf_url": result.pdf_url,
                        "entry_id": result.entry_id,
                        "published": updated_beijing.strftime("%Y-%m-%d %H:%M:%S"),
                        "primary_category": result.primary_category
                    })
        except Exception as e:
            print(f"  批量获取论文详情失败 (批次 {i // batch_size + 1}): {e}")
    
    beijing_date = datetime.now(beijing_tz).strftime("%Y-%m-%d")
    print(f"共获取到 {len(papers)} 篇论文 (日期: {beijing_date})")
    return papers


def summarize_paper(client: OpenAI, model: str, paper: dict) -> str:
    """
    使用大模型总结论文
    
    Args:
        client: OpenAI 客户端
        model: 模型名称
        paper: 论文信息
    
    Returns:
        中文总结
    """
    prompt = f"""请用中文总结以下 arXiv 论文，只输出一段 100-200 字的简短摘要，概括论文的核心内容、方法和结论。

论文信息：
标题：{paper['title']}
作者：{', '.join(paper['authors'][:5])}{'...' if len(paper['authors']) > 5 else ''}
摘要：{paper['summary']}
"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位专业的物理学研究者，擅长总结和解读高能物理领域的学术论文。请用清晰、准确的中文进行总结。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_completion_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"**总结生成失败**: {str(e)}"


def generate_markdown(papers: list, date: str) -> str:
    """
    生成 Markdown 格式的日报
    
    Args:
        papers: 论文列表（包含总结）
        date: 日期字符串
    
    Returns:
        Markdown 内容
    """
    md_content = f"""# arXiv 论文日报 - {date}

> 本报告自动生成于北京时间 {datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")}
> 
> 分类：hep-ph (高能物理-唯象学), hep-ex (高能物理-实验)
> 
> 论文数量：{len(papers)} 篇

---

"""
    
    for i, paper in enumerate(papers, 1):
        md_content += f"""# {i}. {paper['title']}

- **作者**: {', '.join(paper['authors'][:5])}{'...' if len(paper['authors']) > 5 else ''}
- **分类**: {', '.join(paper['categories'])}
- **发布时间**: {paper['published']}
- **链接**: [{paper['entry_id']}]({paper['entry_id']})

## 简短摘要

{paper.get('summary_cn', '无总结')}

---

"""
    
    return md_content


def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # 加载配置
    print("加载配置文件...")
    config = load_config()
    
    # 初始化 OpenAI 客户端
    client = OpenAI(
        api_key=config["llm"]["api_key"],
        base_url=config["llm"]["url"]
    )
    model = config["llm"]["model"]
    
    # 获取今天日期
    date = get_beijing_date()
    print(f"日期: {date} (北京时间)")
    
    # 获取论文
    papers = get_papers(
        categories=config["arxiv"]["categories"],
        max_results=config["arxiv"]["max_results"]
    )
    
    if not papers:
        print("没有新的论文更新")
        # 生成空报告
        md_content = f"""# arXiv 论文日报 - {date}

> 本报告自动生成于北京时间 {datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")}
> 
> 分类：hep-ph (高能物理-唯象学), hep-ex (高能物理-实验)
> 
> **今天没有新的论文更新**

"""
    else:
        # 总结每篇论文
        print("正在使用大模型总结论文...")
        for i, paper in enumerate(papers, 1):
            print(f"  总结第 {i}/{len(papers)} 篇论文: {paper['title'][:50]}...")
            paper["summary_cn"] = summarize_paper(client, model, paper)
        
        # 生成 Markdown
        print("生成 Markdown 报告...")
        md_content = generate_markdown(papers, date)
    
    # 保存文件
    output_dir = script_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"{date}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print(f"\n✅ 日报已生成: {output_file}")
    
    # 发送邮件
    try:
        from email_sender import send_daily_report
        send_daily_report(str(output_file))
    except Exception as e:
        print(f"邮件发送失败: {e}")
    
    return str(output_file)


if __name__ == "__main__":
    main()