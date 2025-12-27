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

    async def search_datasets(self, keyword: str) -> List[Dict]:
        """
        搜索数据集

        Args:
            keyword: 搜索关键词

        Returns:
            数据集列表
        """
        if not self.browser:
            await self.start()

        # 构建搜索 URL
        url = f"https://proteomecentral.proteomexchange.org/ui?view=datasets&search={keyword}"

        logger.info(f"搜索关键词: {keyword}")
        logger.info(f"访问 URL: {url}")

        page = await self.browser.new_page()

        try:
            # 访问搜索页面
            await page.goto(url, timeout=self.timeout, wait_until="networkidle")

            # 等待数据加载
            await page.wait_for_timeout(3000)  # 额外等待 3 秒确保数据加载

            # 获取页面内容
            content = await page.content()

            # 查找所有数据集链接
            # 使用 JavaScript 查找包含 pxid 的链接
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

            logger.info(f"找到 {len(datasets)} 个数据集")

            # 去重
            seen = set()
            unique_datasets = []
            for ds in datasets:
                if ds['pxid'] not in seen:
                    seen.add(ds['pxid'])
                    unique_datasets.append(ds)

            logger.info(f"去重后: {len(unique_datasets)} 个数据集")

            await page.close()
            return unique_datasets

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            await page.close()
            return []

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
        爬取搜索关键词对应的所有数据集及其详情

        Args:
            keyword: 搜索关键词
            max_datasets: 最大数据集数量（None 表示全部）

        Returns:
            所有数据集的详细信息列表
        """
        # 搜索数据集
        datasets = await self.search_datasets(keyword)

        if not datasets:
            logger.warning("没有找到数据集")
            return []

        # 限制数量
        if max_datasets:
            datasets = datasets[:max_datasets]

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
