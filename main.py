#!/usr/bin/env python3
"""
arXiv 论文日报 - 主脚本
爬取 arXiv 上 hep-ph 和 hep-ex 分类的最新论文，使用大模型生成中文总结
"""

import os
import sys
import yaml
import arxiv
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from pathlib import Path


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_beijing_date() -> str:
    """获取北京时间日期字符串"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d")


def get_time_threshold_hours() -> int:
    """
    获取时间阈值
    周一返回96小时（覆盖周末+周五），其他返回24小时
    """
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    if now_beijing.weekday() == 0:  # 周一 (0=Monday)
        print("今天是周一，扩大时间范围到96小时（覆盖周末）")
        return 96
    return 24


def get_papers(categories: list, max_results: int = 100) -> list:
    """
    从 arXiv 获取指定分类的论文
    
    使用 arXiv API 搜索，按时间阈值过滤论文。
    周一获取最近72小时，其他日子获取最近24小时。

    Args:
        categories: 论文分类列表
        max_results: 每个分类最大结果数

    Returns:
        论文列表
    """
    papers = []
    seen_ids = set()
    
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    today_beijing = now_beijing.date()
    
    # 获取时间阈值
    time_threshold_hours = get_time_threshold_hours()
    time_threshold = now_beijing - timedelta(hours=time_threshold_hours)
    
    for category in categories:
        print(f"正在获取 {category} 分类的论文...")
        category_count = 0
        
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        # 使用 Client.results() 方法获取结果
        client = arxiv.Client()
        
        try:
            for result in client.results(search):
                # 使用更新时间（updated）而不是提交时间（published）
                # 这样可以捕获那些在周四提交但在北京时间周五凌晨才公开的论文
                updated_beijing = result.updated.astimezone(beijing_tz)
                
                # 只获取时间阈值内的论文
                if updated_beijing >= time_threshold:
                    # 去重：避免同一篇论文被多次添加
                    if result.entry_id not in seen_ids:
                        seen_ids.add(result.entry_id)
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
                        category_count += 1
                else:
                    # 由于按时间降序排列，遇到旧论文即可停止
                    break
        except Exception as e:
            print(f"  获取失败: {e}")
        
        print(f"  {category}: {category_count} 篇")

    print(f"共获取到 {len(papers)} 篇论文（最近{time_threshold_hours}小时，北京时间日期: {today_beijing.strftime('%Y-%m-%d')}）")
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