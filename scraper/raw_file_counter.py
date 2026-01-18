"""
原始文件统计模块
支持从 PRIDE, MassIVE, iProX 等仓库统计 RAW 文件数量和大小
"""

import logging
import xml.etree.ElementTree as ET
import re
from typing import Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# 支持的原始文件扩展名
RAW_EXTENSIONS = [
    '.raw', '.d', '.zip', '.wiff', '.wiff2', '.d.zip',
    '.tar', '.gz', '.bz2', '.rar', '.7z',
    '.mzml', '.mzxml', '.ms2', '.mgf', '.fid', '.yep', '.tdf'
]


class RawFileCounter:
    """原始文件统计器 - 支持多仓库"""

    # 仓库对应的配置
    REPOSITORY_CONFIGS = {
        'PRIDE': {
            'api_base': 'https://www.ebi.ac.uk/pride/ws/archive/v2',
            'files_endpoint': '/files'
        },
        'MassIVE': {
            'api_base': 'https://massive.ucsd.edu/ProteoSAFe',
            'dataset_json': '/datasets_json.jsp'
        },
        'iProX': {
            'api_base': 'https://www.iprox.cn',
            'api_endpoint': '/api/project/{accession}/files'
        },
        'ProteomeXchange': {
            'api_base': 'https://proteomecentral.proteomexchange.org',
            'xml_endpoint': '/cgi/GetDataset'
        }
    }

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        初始化统计器

        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建带重试机制的 Session"""
        session = requests.Session()

        # 配置重试策略
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

    def get_repository_from_xml(self, pxid: str) -> Optional[str]:
        """
        从 ProteomeXchange XML 获取 Hosting Repository

        Args:
            pxid: 数据集 ID (如 PXD000001)

        Returns:
            仓库名称 (PRIDE, MassIVE, iProX 等) 或 None
        """
        url = f"https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={pxid}&outputMode=XML"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            # 查找 Repository 名称
            # ProteomeXchange XML 格式: <Repository name="PRIDE" />
            for repo in root.findall('.//Repository'):
                repo_name = repo.get('name')
                if repo_name:
                    logger.debug(f"{pxid} -> Repository: {repo_name}")
                    return repo_name

            # 备选：从 Announcement 中提取
            for announcement in root.findall('.//Announcement'):
                repo_text = announcement.text or ''
                for repo in ['PRIDE', 'MassIVE', 'iProX', 'JPOST', 'PeptideAtlas']:
                    if repo.lower() in repo_text.lower():
                        logger.debug(f"{pxid} -> Repository (from announcement): {repo}")
                        return repo

            logger.warning(f"{pxid} 无法从 XML 中识别 Repository")
            return None

        except Exception as e:
            logger.error(f"获取 {pxid} Repository 信息失败: {e}")
            return None

    def count_pride_raw_files(self, pxid: str) -> Tuple[int, float]:
        """
        统计 PRIDE 仓库的 RAW 文件

        Args:
            pxid: 数据集 ID

        Returns:
            (文件数量, 总大小(字节))
        """
        api_url = f"{self.REPOSITORY_CONFIGS['PRIDE']['api_base']}/files"

        try:
            # PRIDE API: 按 accession 查询文件
            params = {
                'accession': pxid,
                'fileCategory': 'RAW'  # 只获取 RAW 文件
            }

            response = self.session.get(api_url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            if not data or '_embedded' not in data:
                return 0, 0.0

            files = data['_embedded'].get('files', [])

            total_size = sum(f.get('fileSizeBytes', 0) for f in files)

            logger.debug(f"{pxid} (PRIDE): {len(files)} RAW 文件, {self._bytes_to_gb(total_size):.2f} GB")
            return len(files), total_size

        except Exception as e:
            logger.warning(f"{pxid} PRIDE API 请求失败: {e}")
            return 0, 0.0

    def count_massive_raw_files(self, pxid: str) -> Tuple[int, float]:
        """
        统计 MassIVE 仓库的 RAW 文件

        Args:
            pxid: 数据集 ID

        Returns:
            (文件数量, 总大小(字节))
        """
        # MassIVE 使用 MSV ID，但从 PXD 可以获取
        url = f"{self.REPOSITORY_CONFIGS['MassIVE']['api_base']}{self.REPOSITORY_CONFIGS['MassIVE']['dataset_json']}"

        try:
            # 获取数据集信息
            params = {'accession': pxid}

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            # 解析文件列表
            files = data.get('files', [])

            raw_count = 0
            total_size = 0

            for file_info in files:
                file_name = file_info.get('fileName', '').lower()
                file_size = file_info.get('fileSizeBytes', 0)

                # 检查是否是原始文件
                if any(file_name.endswith(ext.lower()) for ext in RAW_EXTENSIONS):
                    raw_count += 1
                    total_size += file_size

            logger.debug(f"{pxid} (MassIVE): {raw_count} RAW 文件, {self._bytes_to_gb(total_size):.2f} GB")
            return raw_count, total_size

        except Exception as e:
            logger.warning(f"{pxid} MassIVE API 请求失败: {e}")
            return 0, 0.0

    def count_iprox_raw_files(self, pxid: str) -> Tuple[int, float]:
        """
        统计 iProX 仓库的 RAW 文件

        Args:
            pxid: 数据集 ID

        Returns:
            (文件数量, 总大小(字节))
        """
        # iProX API 相对复杂，这里实现基础版本
        url = f"https://www.iprox.cn/api/project/{pxid}/files"

        try:
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 404:
                # iProX 可能使用不同格式
                return 0, 0.0

            response.raise_for_status()
            data = response.json()

            files = data.get('data', data.get('files', []))

            raw_count = 0
            total_size = 0

            for file_info in files:
                file_name = file_info.get('name', file_info.get('fileName', '')).lower()
                file_size = file_info.get('size', file_info.get('fileSize', 0))

                if any(file_name.endswith(ext.lower()) for ext in RAW_EXTENSIONS):
                    raw_count += 1
                    total_size += file_size

            logger.debug(f"{pxid} (iProX): {raw_count} RAW 文件, {self._bytes_to_gb(total_size):.2f} GB")
            return raw_count, total_size

        except Exception as e:
            logger.warning(f"{pxid} iProX API 请求失败: {e}")
            return 0, 0.0

    def count_from_xml_fallback(self, pxid: str) -> Tuple[int, float]:
        """
        备用方案：从 ProteomeXchange XML 中提取 FTP 链接信息

        Args:
            pxid: 数据集 ID

        Returns:
            (文件数量, 估算大小)
        """
        url = f"https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={pxid}&outputMode=XML"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            # 查找 FTP 链接
            ftp_links = []
            for link in root.findall('.//ftpLink'):
                if link.text:
                    ftp_links.append(link.text)

            # 从 fullDatasetLink 中提取
            for link in root.findall('.//fullDatasetLink'):
                if link.text and 'ftp' in link.text.lower():
                    ftp_links.append(link.text)

            if ftp_links:
                # 无法从 FTP 获取实际大小，返回链接数量作为估算
                logger.debug(f"{pxid} (XML fallback): 找到 {len(ftp_links)} 个 FTP 链接")
                return len(ftp_links), 0.0

            return 0, 0.0

        except Exception as e:
            logger.warning(f"{pxid} XML fallback 失败: {e}")
            return 0, 0.0

    def count_raw_files(self, pxid: str, repository: str = None) -> Tuple[int, float]:
        """
        统计指定数据集的 RAW 文件数量和大小

        Args:
            pxid: 数据集 ID (如 PXD000001)
            repository: 仓库名称 (如 PRIDE, MassIVE)。如果为 None，会自动检测

        Returns:
            (文件数量, 总大小(GB))
        """
        # 如果没有指定仓库，尝试从 XML 获取
        if repository is None:
            repository = self.get_repository_from_xml(pxid)

        if not repository:
            logger.warning(f"{pxid} 无法识别仓库，尝试备用方案")
            count, size_bytes = self.count_from_xml_fallback(pxid)
            return count, self._bytes_to_gb(size_bytes)

        # 根据仓库类型调用相应的方法
        repository_lower = repository.lower()

        if 'pride' in repository_lower:
            count, size_bytes = self.count_pride_raw_files(pxid)

        elif 'massive' in repository_lower or 'msv' in repository_lower:
            count, size_bytes = self.count_massive_raw_files(pxid)

        elif 'iprox' in repository_lower or 'pxd' in repository_lower:
            count, size_bytes = self.count_iprox_raw_files(pxid)

        else:
            logger.info(f"{pxid} 仓库 '{repository}' 暂不支持 API，使用 XML fallback")
            count, size_bytes = self.count_from_xml_fallback(pxid)

        # 如果 API 方法失败，尝试备用方案
        if count == 0:
            logger.debug(f"{pxid} API 未获取到文件，尝试 XML fallback")
            count, size_bytes = self.count_from_xml_fallback(pxid)

        return count, self._bytes_to_gb(size_bytes)

    @staticmethod
    def _bytes_to_gb(bytes_size: float) -> float:
        """将字节转换为 GB"""
        return bytes_size / (1024 ** 3)


def count_raw_files_for_dataset(pxid: str) -> Dict[str, any]:
    """
    为单个数据集统计 RAW 文件（用于多线程）

    Args:
        pxid: 数据集 ID

    Returns:
        包含统计信息的字典
    """
    counter = RawFileCounter()

    try:
        # 获取仓库信息
        repository = counter.get_repository_from_xml(pxid)

        # 统计文件
        count, size_gb = counter.count_raw_files(pxid, repository)

        return {
            'pxid': pxid,
            'repository': repository or 'Unknown',
            'raw_file_count': count,
            'total_raw_size_gb': round(size_gb, 2),
            'success': True
        }

    except Exception as e:
        logger.error(f"统计 {pxid} 文件失败: {e}")
        return {
            'pxid': pxid,
            'repository': 'Error',
            'raw_file_count': 0,
            'total_raw_size_gb': 0.0,
            'success': False,
            'error': str(e)
        }


def count_raw_files_batch(pxid_list: list, max_workers: int = 5) -> Dict[str, Dict]:
    """
    批量统计多个数据集的 RAW 文件（多线程）

    Args:
        pxid_list: 数据集 ID 列表
        max_workers: 最大线程数

    Returns:
        字典，键为 pxid，值为统计信息
    """
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
                logger.info(f"  {pxid}: {result['raw_file_count']} 文件, {result['total_raw_size_gb']} GB")
            except Exception as e:
                logger.error(f"{pxid} 处理失败: {e}")
                results[pxid] = {
                    'pxid': pxid,
                    'raw_file_count': 0,
                    'total_raw_size_gb': 0.0,
                    'error': str(e)
                }

    logger.info(f"批量统计完成: {len(results)} 个数据集")
    return results
