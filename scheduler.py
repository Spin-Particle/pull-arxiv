#!/usr/bin/env python3
"""
arXiv 论文日报 - 定时任务脚本
在北京时间每天 12:00 自动运行
"""

import schedule
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scheduler.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def get_beijing_time() -> str:
    """获取北京时间字符串"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")


def run_script(script_name: str):
    """运行指定的脚本"""
    script_dir = Path(__file__).parent
    script_path = script_dir / script_name
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_dir),
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.stdout:
            logger.info(f"输出:\n{result.stdout}")
        if result.stderr:
            logger.error(f"错误:\n{result.stderr}")
        
        if result.returncode == 0:
            logger.info(f"{script_name} 执行成功")
        else:
            logger.error(f"{script_name} 执行失败，返回码: {result.returncode}")
            
    except Exception as e:
        logger.error(f"执行 {script_name} 时发生异常: {e}")


def run_main_script():
    """运行论文日报主脚本"""
    logger.info(f"开始执行任务 - 北京时间: {get_beijing_time()}")
    run_script("main.py")


def run_qcdsr_script():
    """运行 QCD Sum Rule 论文收集脚本"""
    logger.info(f"开始执行 QCD Sum Rule 任务 - 北京时间: {get_beijing_time()}")
    run_script("qcdsr.py")


def run_daily_tasks():
    """运行每日任务：先运行 main.py，再运行 qcdsr.py"""
    logger.info("=" * 50)
    logger.info("开始执行每日任务")
    logger.info("=" * 50)
    
    # 先运行论文日报
    run_main_script()
    
    # 等待一下，避免并发
    time.sleep(2)
    
    # 再运行 QCD Sum Rule 收集
    run_qcdsr_script()
    
    logger.info("=" * 50)
    logger.info("每日任务执行完成")
    logger.info("=" * 50)


def main():
    """主函数 - 启动定时任务"""
    logger.info("=" * 50)
    logger.info("arXiv 论文日报 - 定时任务启动")
    logger.info(f"当前北京时间: {get_beijing_time()}")
    logger.info("计划执行时间: 每天 12:00 (北京时间)")
    logger.info("运行任务: main.py (论文日报) + qcdsr.py (QCD Sum Rule)")
    logger.info("=" * 50)
    
    # 设置每天 12:00 执行 (使用系统时间，假设系统时间为北京时间)
    # 如果系统时间不是北京时间，需要调整
    schedule.every().day.at("12:00").do(run_daily_tasks)
    
    logger.info("定时任务已设置，等待执行...")
    logger.info("按 Ctrl+C 停止")
    
    # 立即执行一次（可选，用于测试）
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logger.info("检测到 --now 参数，立即执行一次")
        run_daily_tasks()
    
    # 持续运行
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n定时任务已停止")