"""
ProteomeXchange 爬虫主程序
支持深度抓取：统计 PRIDE/MassIVE/iProX 等仓库的 RAW 文件数量
"""

import argparse
import logging
import sys
from datetime import datetime
from tqdm import tqdm

# 导入项目模块
import config
from scraper.px_scraper import ProteomeXchangeScraper
from scraper.raw_file_counter import count_raw_files_batch
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


# Excel 输出列配置（按顺序）
OUTPUT_COLUMNS = [
    # 基础信息列（左侧）
    '样品编号',
    'Title',
    'lab head',
    'Description',
    'Instrument List',
    'submitter keyword',
    'Hosting Repository',
    # 新增的文件统计列（右侧）
    'Raw_File_Count',
    # 最后一列：元数据链接
    '元数据网址'
]


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='ProteomeXchange 数据集深度爬虫工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 搜索关键词 "cancer" 并统计 RAW 文件
  python main.py --keyword "cancer"

  # 搜索并指定输出文件
  python main.py --keyword "top-down" --output topdown_data.xlsx

  # 限制爬取数量（用于测试）
  python main.py --keyword "intact protein" --max-datasets 10

  # 指定线程数
  python main.py --keyword "proteomics" --workers 8

  # 跳过 RAW 文件统计（快速模式）
  python main.py --keyword "cancer" --skip-raw-count
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
        '--workers', '-w',
        type=int,
        default=5,
        help='RAW 文件统计的线程数（默认: 5）'
    )

    parser.add_argument(
        '--skip-raw-count',
        action='store_true',
        help='跳过 RAW 文件统计（快速模式，不获取文件数量）'
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


def merge_raw_file_stats(base_datasets: list, raw_stats: dict) -> list:
    """
    将 RAW 文件统计信息合并到基础数据集中

    Args:
        base_datasets: 基础数据集列表
        raw_stats: RAW 文件统计字典

    Returns:
        合并后的数据集列表
    """
    merged_data = []

    for dataset in base_datasets:
        pxid = dataset.get('样品编号', '')

        # 查找对应的 RAW 文件统计
        stat = raw_stats.get(pxid, {})

        # 创建合并后的数据
        merged = dataset.copy()
        merged['Raw_File_Count'] = stat.get('raw_file_count', 0)

        # 如果有 repository 信息但原数据没有，补充进去
        if stat.get('repository') and stat['repository'] != 'Unknown':
            merged.setdefault('Hosting Repository', stat['repository'])

        merged_data.append(merged)

    return merged_data


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    logger.info("=" * 70)
    logger.info("ProteomeXchange 深度爬虫程序启动")
    logger.info("=" * 70)
    logger.info(f"搜索关键词: {args.keyword}")
    logger.info(f"输出文件: {args.output}")
    logger.info(f"最大数据集数量: {args.max_datasets or '全部'}")
    logger.info(f"RAW 文件统计: {'禁用' if args.skip_raw_count else '启用'}")
    logger.info(f"线程数: {args.workers}")
    logger.info(f"无头模式: {args.headless}")
    logger.info("-" * 70)

    # 初始化 Excel 写入器
    excel_writer = ExcelWriter(
        output_dir=config.OUTPUT_DIR,
        sheet_name=config.EXCEL_SHEET_NAME
    )

    try:
        # ========== 第一步：搜索并获取基础数据集信息 ==========
        logger.info(f"\n[第一步] 搜索关键词 '{args.keyword}' 的数据集...")

        scraper = ProteomeXchangeScraper(headless=args.headless)

        import asyncio

        async def scrape_and_get_raw_stats():
            await scraper.start()
            try:
                # 搜索数据集
                datasets = await scraper.search_datasets(
                    keyword=args.keyword,
                    max_datasets=args.max_datasets
                )

                if not datasets:
                    logger.warning("没有找到任何数据集")
                    return []

                # 获取基础详细信息
                logger.info(f"\n获取 {len(datasets)} 个数据集的基础信息...")

                all_details = []
                for i, ds in enumerate(tqdm(datasets, desc="获取基础信息"), 1):
                    pxid = ds['pxid']
                    details = await scraper.get_dataset_details(pxid)
                    if details:
                        all_details.append(details)
                    # 添加延迟避免请求过快
                    import asyncio
                    await asyncio.sleep(0.5)

                return all_details
            finally:
                await scraper.close()

        base_datasets = asyncio.run(scrape_and_get_raw_stats())

        if not base_datasets:
            logger.warning("没有获取到任何数据")
            return

        logger.info(f"基础信息获取完成: {len(base_datasets)} 个数据集")

        # ========== 第二步：统计 RAW 文件（可选）==========
        if args.skip_raw_count:
            logger.info("\n[第二步] 跳过 RAW 文件统计（快速模式）")
            final_datasets = base_datasets
            # 添加空列
            for dataset in final_datasets:
                dataset['Raw_File_Count'] = 0
        else:
            logger.info(f"\n[第二步] 统计 RAW 文件（{args.workers} 线程并行）...")

            # 提取所有 PXD ID
            pxid_list = [ds.get('样品编号', '') for ds in base_datasets if ds.get('样品编号')]

            logger.info(f"需要统计 {len(pxid_list)} 个数据集的文件信息...")

            # 批量统计 RAW 文件
            raw_stats = count_raw_files_batch(pxid_list, max_workers=args.workers)

            # 合并统计结果
            final_datasets = merge_raw_file_stats(base_datasets, raw_stats)

            # 统计汇总
            total_files = sum(ds.get('Raw_File_Count', 0) for ds in final_datasets)
            logger.info(f"RAW 文件统计完成:")
            logger.info(f"  - 总文件数: {total_files}")

        # ========== 第三步：写入 Excel ==========
        logger.info(f"\n[第三步] 写入 Excel 文件...")

        output_path = excel_writer.write_to_excel(
            data=final_datasets,
            filename=args.output,
            columns=OUTPUT_COLUMNS
        )

        if output_path:
            logger.info("\n" + "=" * 70)
            logger.info("✓ 数据导出成功!")
            logger.info(f"✓ 输出文件: {output_path}")
            logger.info(f"✓ 数据集数量: {len(final_datasets)}")

            if not args.skip_raw_count:
                total_files = sum(ds.get('Raw_File_Count', 0) for ds in final_datasets)
                logger.info(f"✓ RAW 文件总数: {total_files}")

            logger.info("=" * 70)
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
