"""
ProteomeXchange 爬虫主程序
使用 Playwright 处理动态页面
"""

import argparse
import logging
import sys
from datetime import datetime

# 导入项目模块
import config
from scraper.px_scraper import scrape_datasets_sync
from utils.excel_writer import ExcelWriter

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='ProteomeXchange 数据集爬虫工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 搜索关键词 "cancer"
  python main.py --keyword "cancer"

  # 搜索并指定输出文件
  python main.py --keyword "mitochondria" --output mitochondria_data.xlsx

  # 搜索多个页面的结果
  python main.py --keyword "proteomics" --pages 5
        """
    )

    parser.add_argument(
        '--keyword', '-k',
        type=str,
        required=True,
        help='搜索关键词（必需）'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=config.DEFAULT_OUTPUT_FILENAME,
        help=f'输出 Excel 文件名（默认: {config.DEFAULT_OUTPUT_FILENAME}）'
    )

    parser.add_argument(
        '--max-datasets', '-m',
        type=int,
        default=None,
        help='最大爬取数据集数量（默认: 全部）'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='无头模式运行（不显示浏览器窗口）'
    )

    parser.add_argument(
        '--show-browser',
        action='store_false',
        dest='headless',
        help='显示浏览器窗口（用于调试）'
    )

    return parser.parse_args()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    logger.info("=" * 60)
    logger.info("ProteomeXchange 爬虫程序启动")
    logger.info("=" * 60)
    logger.info(f"搜索关键词: {args.keyword}")
    logger.info(f"输出文件: {args.output}")
    logger.info(f"最大数据集数量: {args.max_datasets or '全部'}")
    logger.info(f"无头模式: {args.headless}")
    logger.info("-" * 60)

    # 初始化 Excel 写入器
    excel_writer = ExcelWriter(
        output_dir=config.OUTPUT_DIR,
        sheet_name=config.EXCEL_SHEET_NAME
    )

    try:
        # 爬取所有数据集及其详情
        logger.info(f"\n开始爬取关键词 '{args.keyword}' 的所有数据集...")
        all_datasets = scrape_datasets_sync(
            keyword=args.keyword,
            max_datasets=args.max_datasets,
            headless=args.headless
        )

        # 检查是否获取到数据
        if not all_datasets:
            logger.warning("没有获取到任何数据")
            return

        logger.info(f"\n总共获取到 {len(all_datasets)} 个数据集")

        # 写入 Excel（不指定 columns，自动使用所有字段）
        logger.info(f"\n正在写入 Excel 文件...")
        output_path = excel_writer.write_to_excel(
            data=all_datasets,
            filename=args.output
            # 不指定 columns，使用所有提取的字段
        )

        if output_path:
            logger.info(f"\n✓ 数据已成功导出到: {output_path}")
            logger.info(f"✓ 共包含 {len(all_datasets)} 条数据集记录")
        else:
            logger.error("导出失败")

    except KeyboardInterrupt:
        logger.warning("\n用户中断程序")
    except Exception as e:
        logger.error(f"\n程序执行出错: {e}", exc_info=True)
    finally:
        logger.info("\n程序执行完毕")


if __name__ == "__main__":
    main()
