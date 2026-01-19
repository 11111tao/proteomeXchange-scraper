"""
原始文件统计模块
支持从 ProteomeXchange XML 和各仓库 API 统计 RAW 文件数量

支持的原始文件格式：
- .raw - Thermo 仪器
- .d / .d.zip - TOF/Brucker 仪器
- .wiff / .wiff2 - AB Sciex 仪器
"""

import logging
import xml.etree.ElementTree as ET
import json
import re
from typing import Dict, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# 支持的原始文件扩展名（按长度排序，长的优先匹配）
RAW_EXTENSIONS = [
    '.raw.zip',      # 压缩的 Thermo RAW 文件
    '.raw.gz',       # 压缩的 Thermo RAW 文件
    '.raw',          # Thermo RAW 文件
    '.d.zip',        # 压缩的 TOF/Brucker 文件
    '.d.gz',         # 压缩的 TOF/Brucker 文件
    '.d',            # TOF/Brucker 文件
    '.wiff',         # AB Sciex WIFF
    '.wiff2',        # AB Sciex WIFF2
]


def is_raw_file(filename: str) -> bool:
    """判断文件是否是原始文件"""
    filename_lower = filename.lower()
    for ext in RAW_EXTENSIONS:
        if filename_lower.endswith(ext):
            return True
    return False


class RawFileCounter:
    """原始文件统计器"""

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建带重试机制的 Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_repository_and_links(self, pxid: str) -> Tuple[Optional[str], Dict[str, str]]:
        """
        从 XML 获取仓库类型和外部链接

        Returns:
            (仓库名称, 链接字典)
        """
        url = f"https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={pxid}&outputMode=XML"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            # 获取仓库
            dataset_summary = root.find('.//DatasetSummary')
            repository = None
            if dataset_summary is not None:
                repository = dataset_summary.get('hostingRepository')

            # 获取外部链接
            links = {}
            for full_link in root.findall('.//FullDatasetLink'):
                for cv_param in full_link.findall('.//cvParam'):
                    name = cv_param.get('name', '')
                    value = cv_param.get('value', '')
                    if value:
                        links[name] = value

            return repository, links

        except Exception as e:
            logger.error(f"获取 {pxid} XML 失败: {e}")
            return None, {}

    def _count_from_jpost(self, jpost_id: str) -> int:
        """从 JPOST API 获取文件数量"""
        # JPOST ID 格式: JPST004334
        url = f"https://repository.jpostdb.org/api/proteome/v1/jpost_files?dataset_id={jpost_id}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                files = data.get('data', data.get('files', []))

                count = 0
                for file_info in files:
                    file_name = file_info.get('path', file_info.get('name', ''))
                    if is_raw_file(file_name):
                        count += 1

                logger.debug(f"JPOST {jpost_id}: {count} RAW files")
                return count
        except Exception as e:
            logger.debug(f"JPOST API 失败: {e}")

        return 0

    def _count_from_massive(self, massive_id: str) -> int:
        """从 MassIVE API 获取文件数量"""
        # MassIVE ID 格式: MSV000097430
        url = "https://massive.ucsd.edu/ProteoSAFe/QueryDatasets"

        try:
            params = {'query': massive_id}
            response = self.session.post(url, data=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                # 尝试从 datasets_json.jsp 获取详细文件列表
                task_id = data.get('row_data', [{}])[0].get('task', '')
                if task_id:
                    json_url = f"https://massive.ucsd.edu/ProteoSAFe/datasets_json.jsp?task={task_id}"
                    json_response = self.session.get(json_url, timeout=self.timeout)

                    if json_response.status_code == 200:
                        json_data = json_response.json()
                        files = json_data.get('files', json_data.get('dataset_files', []))

                        count = 0
                        for file_info in files:
                            file_name = file_info.get('fileName', file_info.get('name', ''))
                            if is_raw_file(file_name):
                                count += 1

                        logger.debug(f"MassIVE {massive_id}: {count} RAW files")
                        return count
        except Exception as e:
            logger.debug(f"MassIVE API 失败: {e}")

        return 0

    def _count_from_pride_api(self, pxid: str) -> int:
        """从 PRIDE API 获取 RAW 文件数量"""
        url = "https://www.ebi.ac.uk/pride/ws/archive/v2/files"

        try:
            params = {'accession': pxid, 'fileCategory': 'RAW'}
            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data and '_embedded' in data:
                    files = data['_embedded'].get('files', [])
                    logger.debug(f"PRIDE {pxid}: {len(files)} RAW files")
                    return len(files)
        except Exception as e:
            logger.debug(f"PRIDE API 失败: {e}")

        return 0

    def count_raw_files(self, pxid: str) -> Tuple[int, str]:
        """
        统计指定数据集的 RAW 文件数量

        Args:
            pxid: 数据集 ID (如 PXD000001)

        Returns:
            (文件数量, 仓库名称)
        """
        # 首先从 XML 获取仓库信息和链接
        repository, links = self._get_repository_and_links(pxid)

        if not repository:
            return 0, 'Unknown'

        # 首先尝试从 XML 的 DatasetFileList 获取（如果有）
        xml_count = self._count_from_xml_datasetfilelist(pxid)
        if xml_count > 0:
            return xml_count, repository

        # 根据仓库类型调用相应的 API
        repository_lower = repository.lower()
        count = 0

        if 'pride' in repository_lower:
            count = self._count_from_pride_api(pxid)

        elif 'jpost' in repository_lower:
            # 从链接中提取 JPOST ID (如 JPST004334)
            jpost_id = None
            for name, value in links.items():
                if 'jPOST dataset URI' in name or 'jPOST dataset identifier' in name:
                    match = re.search(r'(JPST\d+)', value)
                    if match:
                        jpost_id = match.group(1)
                        break

            if jpost_id:
                count = self._count_from_jpost(jpost_id)

        elif 'massive' in repository_lower:
            # 从链接中提取 MassIVE ID (如 MSV000097430)
            massive_id = None
            for name, value in links.items():
                if 'MassIVE dataset identifier' in name:
                    match = re.search(r'(MSV\d+)', value)
                    if match:
                        massive_id = match.group(1)
                        break
                # 也尝试从 FTP 链接提取
                if 'FTP location' in name:
                    match = re.search(r'(MSV\d+)', value)
                    if match:
                        massive_id = match.group(1)
                        break

            if massive_id:
                count = self._count_from_massive(massive_id)

        elif 'iprox' in repository_lower:
            # iProX 可能可以从 XML 读取，返回 0 表示暂不支持
            count = 0

        logger.info(f"{pxid} ({repository}): {count} 个原始文件")
        return count, repository

    def _count_from_xml_datasetfilelist(self, pxid: str) -> int:
        """从 XML 的 DatasetFileList 统计文件"""
        url = f"https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={pxid}&outputMode=XML"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            file_count = 0
            for dataset_file in root.findall('.//DatasetFile'):
                file_name = dataset_file.get('name', '')
                if is_raw_file(file_name):
                    file_count += 1

            if file_count > 0:
                logger.debug(f"{pxid} XML: {file_count} RAW files")

            return file_count

        except Exception as e:
            logger.debug(f"XML 解析失败: {e}")
            return 0


def count_raw_files_for_dataset(pxid: str) -> Dict[str, any]:
    """为单个数据集统计 RAW 文件（用于多线程）"""
    counter = RawFileCounter()

    try:
        count, repository = counter.count_raw_files(pxid)

        return {
            'pxid': pxid,
            'repository': repository,
            'raw_file_count': count,
            'success': True
        }

    except Exception as e:
        logger.error(f"统计 {pxid} 文件失败: {e}")
        return {
            'pxid': pxid,
            'repository': 'Error',
            'raw_file_count': 0,
            'success': False
        }


def count_raw_files_batch(pxid_list: list, max_workers: int = 5) -> Dict[str, Dict]:
    """批量统计多个数据集的 RAW 文件（多线程）"""
    results = {}

    logger.info(f"开始批量统计 {len(pxid_list)} 个数据集的 RAW 文件...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pxid = {
            executor.submit(count_raw_files_for_dataset, pxid): pxid
            for pxid in pxid_list
        }

        for future in as_completed(future_to_pxid):
            pxid = future_to_pxid[future]
            try:
                result = future.result()
                results[pxid] = result
                logger.info(f"  {pxid}: {result['raw_file_count']} 个原始文件")
            except Exception as e:
                logger.error(f"{pxid} 处理失败: {e}")
                results[pxid] = {
                    'pxid': pxid,
                    'raw_file_count': 0
                }

    logger.info(f"批量统计完成: {len(results)} 个数据集")
    return results
