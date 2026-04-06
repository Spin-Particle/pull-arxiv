#!/usr/bin/env python3
"""
QCD Sum Rule 论文收集脚本
搜集 arXiv 上与 QCD sum rule 相关的论文，增量更新到 QCDSR.md 文件
"""

import os
import re
import yaml
import arxiv
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from pathlib import Path


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_beijing_time() -> str:
    """获取北京时间字符串"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")


def get_existing_paper_ids(output_file: Path) -> set:
    """从已有文件中提取论文ID，用于去重"""
    if not output_file.exists():
        return set()
    
    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 提取 arXiv ID，格式如 http://arxiv.org/abs/2503.xxxxx
    pattern = r'arxiv\.org/abs/(\d+\.\d+)'
    return set(re.findall(pattern, content))


def get_qcdsr_papers(max_results: int = 50) -> list:
    """
    从 arXiv 获取 QCD sum rule 相关的论文（最近24小时）
    
    Args:
        max_results: 最大结果数
    
    Returns:
        论文列表
    """
    papers = []
    beijing_tz = timezone(timedelta(hours=8))
    
    # 获取当前北京时间
    now_beijing = datetime.now(beijing_tz)
    today_beijing = now_beijing.date()
    
    # 获取最近 24 小时的时间阈值（北京时间）
    time_threshold = now_beijing - timedelta(hours=24)
    
    # 搜索关键词：标题或摘要中包含 "QCD sum rule"
    query = 'ti:"QCD sum rule" OR abs:"QCD sum rule"'
    
    print(f"正在搜索 QCD sum rule 相关论文...")
    
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    client = arxiv.Client()
    for result in client.results(search):
        # 论文发布时间转换为北京时间
        published_beijing = result.published.astimezone(beijing_tz)
        
        # 只获取最近 24 小时内发布的论文
        if published_beijing >= time_threshold:
            papers.append({
                "title": result.title,
                "authors": [author.name for author in result.authors],
                "summary": result.summary,
                "categories": result.categories,
                "pdf_url": result.pdf_url,
                "entry_id": result.entry_id,
                "published": published_beijing.strftime("%Y-%m-%d %H:%M:%S"),
                "primary_category": result.primary_category
            })
        else:
            # 由于按时间降序排列，遇到旧论文即可停止
            break
    
    print(f"搜索到 {len(papers)} 篇论文（最近24小时，北京时间日期: {today_beijing.strftime('%Y-%m-%d')}）")
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


def generate_paper_entry(paper: dict, index: int) -> str:
    """生成单篇论文的 Markdown 条目"""
    return f"""# {index}. {paper['title']}

- **作者**: {', '.join(paper['authors'][:5])}{'...' if len(paper['authors']) > 5 else ''}
- **分类**: {', '.join(paper['categories'])}
- **发布时间**: {paper['published']}
- **链接**: [{paper['entry_id']}]({paper['entry_id']})

## 简短摘要

{paper.get('summary_cn', '无总结')}

---

"""


def update_qcdsr_file(output_file: Path, new_papers: list, existing_count: int) -> None:
    """
    增量更新 QCDSR.md 文件
    
    Args:
        output_file: 输出文件路径
        new_papers: 新论文列表
        existing_count: 已有论文数量
    """
    beijing_time = get_beijing_time()
    total_count = existing_count + len(new_papers)
    
    # 读取已有内容（如果存在）
    existing_content = ""
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            # 提取 "---" 分隔符之后的内容（论文列表）
            parts = content.split("---", 2)
            if len(parts) >= 3:
                existing_content = parts[2].strip()
    
    # 生成新论文的条目
    new_entries = ""
    for i, paper in enumerate(new_papers, 1):
        new_entries += generate_paper_entry(paper, i)
    
    # 重新编号已有论文
    if existing_content:
        # 将已有论文的编号向后偏移
        def renumber(match):
            old_num = int(match.group(1))
            return f"# {old_num + len(new_papers)}."
        
        existing_content = re.sub(r'^# (\d+)\.', renumber, existing_content, flags=re.MULTILINE)
    
    # 组合新内容
    header = f"""# QCD Sum Rule 论文合集

> 最后更新：{beijing_time} (北京时间)
> 
> 搜索关键词：QCD sum rule
> 
> 论文总数：{total_count} 篇

---

"""
    
    final_content = header + new_entries + existing_content
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_content)


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
    
    # 输出文件
    output_dir = script_dir / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "QCDSR.md"
    
    # 获取已有论文ID
    existing_ids = get_existing_paper_ids(output_file)
    existing_count = len(existing_ids)
    print(f"已有论文: {existing_count} 篇")
    
    # 搜索新论文
    papers = get_qcdsr_papers(max_results=50)
    
    # 过滤出新论文
    new_papers = []
    for paper in papers:
        # 提取 arXiv ID
        match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', paper['entry_id'])
        if match:
            paper_id = match.group(1)
            if paper_id not in existing_ids:
                new_papers.append(paper)
    
    if not new_papers:
        print("没有新的论文")
        return
    
    print(f"发现 {len(new_papers)} 篇新论文")
    
    # 总结每篇新论文
    print("正在使用大模型总结论文...")
    for i, paper in enumerate(new_papers, 1):
        print(f"  总结第 {i}/{len(new_papers)} 篇论文: {paper['title'][:50]}...")
        paper["summary_cn"] = summarize_paper(client, model, paper)
    
    # 更新文件
    print("更新 QCDSR.md 文件...")
    update_qcdsr_file(output_file, new_papers, existing_count)
    
    print(f"\n✅ 已添加 {len(new_papers)} 篇新论文到: {output_file}")
    
    # 发送邮件
    try:
        from email_sender import send_qcdsr_report
        send_qcdsr_report(str(output_file))
    except Exception as e:
        print(f"邮件发送失败: {e}")


if __name__ == "__main__":
    main()
