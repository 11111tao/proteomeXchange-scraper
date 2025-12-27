"""
配置文件
包含所有可配置的参数
"""

# ProteomeXchange API 配置
PX_API_BASE_URL = "https://www.proteomexchange.org"  # 基础 URL
PX_DATASET_URL = "https://proteomecentral.proteomexchange.org/cgi/GetDataset"  # 数据集查询接口

# 请求配置
REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
REQUEST_DELAY = 1  # 请求之间的延迟（秒）- 避免请求过快
MAX_RETRIES = 3  # 最大重试次数

# 输出配置
OUTPUT_DIR = "data"  # 输出目录
DEFAULT_OUTPUT_FILENAME = "proteomexchange_data.xlsx"  # 默认输出文件名

# Excel 配置
EXCEL_SHEET_NAME = "ProteomeXchange Datasets"  # 工作表名称

# 日志配置
LOG_LEVEL = "INFO"  # 日志级别: DEBUG, INFO, WARNING, ERROR
LOG_FILE = "scraper.log"  # 日志文件

# 数据字段配置
# 我们要提取的数据集字段
DATASET_FIELDS = [
    "Accession",      # 数据集ID（如 PXD000001）
    "Title",          # 标题
    "Summary",        # 摘要/描述
    "Publication",    # 发表信息
    "Keywords",       # 关键词
    "Instrument",     # 仪器
    "Organism",       # 物种
    "Modified",       # 修改日期
    "Published",      # 发布日期
    "Repository",     # 仓库（PRIDE, MassIVE等）
    "Dataset Link",   # 数据集链接
]
