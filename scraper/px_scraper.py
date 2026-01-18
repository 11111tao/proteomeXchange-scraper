"""
ProteomeXchange 动态爬虫模块
使用 Playwright 处理动态加载的页面
"""

import asyncio
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger(__name__)


class ProteomeXchangeScraper:
    """ProteomeXchange 动态爬虫"""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        初始化爬虫

        Args:
            headless: 是否无头模式（不显示浏览器）
            timeout: 页面加载超时时间（毫秒）
        """
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.playwright = None

        logger.info(f"初始化 ProteomeXchange 动态爬虫（headless={headless}）")

    async def start(self):
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        logger.info("浏览器已启动")

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("浏览器已关闭")

    async def search_datasets(self, keyword: str, max_datasets: int = None) -> List[Dict]:
        """
        搜索数据集（支持多页）

        Args:
            keyword: 搜索关键词
            max_datasets: 最大数据集数量（None 表示全部）

        Returns:
            数据集列表
        """
        if not self.browser:
            await self.start()

        logger.info(f"搜索关键词: {keyword}")

        all_datasets = []
        page_num = 1

        while True:
            # 构建搜索 URL（带分页）
            if page_num == 1:
                url = f"https://proteomecentral.proteomexchange.org/ui?view=datasets&search={keyword}"
            else:
                url = f"https://proteomecentral.proteomexchange.org/ui?view=datasets&pageNumber={page_num}&search={keyword}"

            logger.info(f"访问第 {page_num} 页: {url}")

            page = await self.browser.new_page()

            try:
                # 访问搜索页面
                await page.goto(url, timeout=self.timeout, wait_until="networkidle")

                # 等待数据加载
                await page.wait_for_timeout(3000)  # 额外等待 3 秒确保数据加载

                # 查找当前页的所有数据集链接
                datasets = await page.evaluate('''() => {
                    const results = [];
                    const links = document.querySelectorAll('a');

                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        if (href && href.includes('?pxid=')) {
                            // 提取 pxid
                            const match = href.match(/[?&]pxid=([^&]+)/);
                            if (match) {
                                const pxid = match[1];

                                // 查找链接文本或其他信息
                                const text = link.textContent.trim();

                                results.push({
                                    'pxid': pxid,
                                    'link_text': text,
                                    'href': href
                                });
                            }
                        }
                    });

                    return results;
                }''')

                logger.info(f"第 {page_num} 页找到 {len(datasets)} 个数据集")

                # 如果当前页没有数据，说明已经到最后一页
                if not datasets:
                    logger.info(f"第 {page_num} 页没有数据，停止翻页")
                    await page.close()
                    break

                # 去重后添加到总列表
                for ds in datasets:
                    if ds['pxid'] not in {d['pxid'] for d in all_datasets}:
                        all_datasets.append(ds)

                logger.info(f"累计找到 {len(all_datasets)} 个数据集")

                await page.close()

                # 检查是否达到最大数量限制
                if max_datasets and len(all_datasets) >= max_datasets:
                    logger.info(f"已达到最大数量限制 {max_datasets}")
                    all_datasets = all_datasets[:max_datasets]
                    break

                # 如果当前页数据少于 100 个，说明已是最后一页
                if len(datasets) < 100:
                    logger.info(f"第 {page_num} 页数据量 < 100，已是最后一页")
                    break

                page_num += 1

            except Exception as e:
                logger.error(f"搜索第 {page_num} 页失败: {e}")
                await page.close()
                break

        logger.info(f"翻页完成，共找到 {len(all_datasets)} 个数据集")
        return all_datasets

    async def get_dataset_details(self, pxid: str) -> Optional[Dict]:
        """
        获取数据集详细信息

        Args:
            pxid: 数据集 ID（如 PXD055745）

        Returns:
            数据集详细信息字典
        """
        if not self.browser:
            await self.start()

        url = f"https://proteomecentral.proteomexchange.org/ui?pxid={pxid}"

        logger.info(f"获取数据集详情: {pxid}")
        logger.debug(f"URL: {url}")

        page = await self.browser.new_page()

        try:
            await page.goto(url, timeout=self.timeout, wait_until="networkidle")
            await page.wait_for_timeout(2000)  # 等待动态内容加载

            # 使用 JavaScript 提取指定的7个字段
            result = await page.evaluate('''() => {
                const result = {};

                // 查找所有表格中的数据
                const tables = document.querySelectorAll('table');
                tables.forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    rows.forEach(row => {
                        const headerCell = row.querySelector('th, td:first-child');
                        const dataCell = row.querySelector('td:not(:first-child), td:last-child');

                        if (headerCell && dataCell) {
                            const label = headerCell.textContent.trim();
                            const value = dataCell.textContent.trim();

                            // 只保存我们需要的字段
                            if (label === 'Title' ||
                                label === 'Description' ||
                                label === 'lab head' ||
                                label === 'Instrument List' ||
                                label === 'submitter keyword' ||
                                label === 'Hosting Repository') {
                                result[label] = value;
                            }
                        }
                    });
                });

                return result;
            }''')

            # 构建元数据网址
            metadata_url = f"https://proteomecentral.proteomexchange.org/ui?pxid={pxid}"

            # 按照指定顺序重新组织字段（最后一列添加元数据网址）
            ordered_details = {
                '样品编号': pxid,
                'Title': result.get('Title', ''),
                'lab head': result.get('lab head', ''),
                'Description': result.get('Description', ''),
                'Instrument List': result.get('Instrument List', ''),
                'submitter keyword': result.get('submitter keyword', ''),
                'Hosting Repository': result.get('Hosting Repository', ''),
                '元数据网址': metadata_url
            }

            logger.info(f"成功提取 {len([v for v in ordered_details.values() if v])} 个非空字段")

            return ordered_details

        except Exception as e:
            logger.error(f"获取详情失败 {pxid}: {e}")
            await page.close()
            return None

    async def scrape_all(self, keyword: str, max_datasets: int = None) -> List[Dict]:
        """
        爬取搜索关键词对应的所有数据集及其详情（支持多页）

        Args:
            keyword: 搜索关键词
            max_datasets: 最大数据集数量（None 表示全部）

        Returns:
            所有数据集的详细信息列表
        """
        # 搜索数据集（带分页支持）
        datasets = await self.search_datasets(keyword, max_datasets=max_datasets)

        if not datasets:
            logger.warning("没有找到数据集")
            return []

        logger.info(f"开始爬取 {len(datasets)} 个数据集的详细信息")

        all_details = []

        for i, ds in enumerate(datasets, 1):
            pxid = ds['pxid']
            logger.info(f"[{i}/{len(datasets)}] 爬取 {pxid}...")

            details = await self.get_dataset_details(pxid)

            if details:
                all_details.append(details)
            else:
                logger.warning(f"跳过 {pxid}")

            # 添加延迟避免请求过快
            await asyncio.sleep(1)

        logger.info(f"完成！共获取 {len(all_details)} 个数据集的详细信息")

        return all_details


# 便捷函数：同步运行异步代码
def scrape_datasets_sync(keyword: str, max_datasets: int = None,
                        headless: bool = True) -> List[Dict]:
    """
    同步方式爬取数据集

    Args:
        keyword: 搜索关键词
        max_datasets: 最大数据集数量
        headless: 是否无头模式

    Returns:
        数据集详细信息列表
    """
    async def _scrape():
        scraper = ProteomeXchangeScraper(headless=headless)
        await scraper.start()
        try:
            result = await scraper.scrape_all(keyword, max_datasets)
            return result
        finally:
            await scraper.close()

    return asyncio.run(_scrape())
