# ProteomeXchange 深度爬虫

一个用于从 [ProteomeXchange](https://www.proteomexchange.org/) 深度爬取蛋白质组学数据集信息的 Python 工具，支持统计 PRIDE、MassIVE、iProX 等仓库的 RAW 原始文件数量和大小。

## 功能特性

- 🔍 **关键词搜索** - 根据关键词搜索 ProteomeXchange 数据集，支持多页自动翻页
- 📊 **深度抓取** - 统计 RAW 原始文件（.raw, .d, .zip 等）的数量和总大小
- 🗂️ **多仓库支持** - 支持 PRIDE、MassIVE、iProX、JPOST 等主流仓库
- ⚡ **多线程加速** - 可配置并发线程数，大幅提升统计速度
- 📈 **进度显示** - 实时进度条，清晰展示爬取进度
- 🔗 **Excel 导出** - 自动生成格式化的 Excel 表格，包含可点击的元数据链接
- 🔄 **自动重试** - 内置请求重试机制，提高稳定性

## 提取的字段

每个数据集提取以下字段（按顺序）：

| 基础信息 | 文件统计 | 链接 |
|---------|---------|-----|
| 样品编号 (PXD***) | Raw_File_Count | 元数据网址 |
| Title | Total_Raw_Size_GB | |
| lab head | | |
| Description | | |
| Instrument List | | |
| submitter keyword | | |
| Hosting Repository | | |

## 安装

### 前置要求

- Python 3.8 或更高版本
- pip 包管理器

### 安装依赖

```bash
pip install -r requirements.txt
```

安装 Playwright 浏览器：

```bash
python -m playwright install chromium
```

## 使用方法

### 基本用法

```bash
# 搜索关键词并统计 RAW 文件
python main.py --keyword "top-down"

# 指定输出文件名
python main.py --keyword "cancer" --output "cancer_data.xlsx"

# 限制爬取数量（用于测试）
python main.py --keyword "intact protein" --max-datasets 10
```

### 高级参数

```bash
# 快速模式（跳过 RAW 文件统计）
python main.py --keyword "proteomics" --skip-raw-count

# 指定线程数（默认 5，范围 1-20）
python main.py --keyword "phosphorylation" --workers 10

# 显示浏览器窗口（调试用）
python main.py --keyword "glycoproteomics" --show-browser
```

### 参数说明

| 参数 | 简写 | 说明 | 必需 | 默认值 |
|------|------|------|------|--------|
| `--keyword` | `-k` | 搜索关键词 | ✅ | - |
| `--output` | `-o` | 输出 Excel 文件名 | ❌ | `proteomexchange_data.xlsx` |
| `--max-datasets` | `-m` | 最大爬取数据集数量 | ❌ | 全部 |
| `--workers` | `-w` | RAW 文件统计线程数 | ❌ | 5 |
| `--skip-raw-count` | - | 跳过 RAW 文件统计（快速模式） | ❌ | False |
| `--show-browser` | - | 显示浏览器窗口（调试用） | ❌ | False |

## 线程数建议

| 线程数 | 适用场景 |
|-------|---------|
| 1 | 最稳定，最慢 |
| 3-5 | 默认推荐，平衡速度和稳定性 |
| 5-10 | 国内网络，较快 |
| 10-20 | 海外服务器/良好网络 |

> 注意：线程过多可能触发网站限流，建议不超过 20

## 输出示例

Excel 文件保存在 `data/` 目录下：

| 样品编号 | Title | lab head | Hosting Repository | Raw_File_Count | Total_Raw_Size_GB | 元数据网址 |
|---------|-------|----------|-------------------|----------------|------------------|-----------|
| PXD000001 | Sample title | Dr. Name | PRIDE | 150 | 25.68 | [点击] |
| PXD000002 | Another study | Dr. Smith | MassIVE | 80 | 12.34 | [点击] |

## 项目结构

```
scrap_tdp/
├── config.py              # 配置文件
├── main.py                # 主程序入口
├── requirements.txt       # Python 依赖
├── README.md             # 项目说明
├── .gitignore            # Git 忽略文件
├── scraper/              # 爬虫模块
│   ├── __init__.py
│   ├── px_scraper.py     # ProteomeXchange 搜索爬虫
│   └── raw_file_counter.py  # RAW 文件统计模块
├── utils/                # 工具模块
│   ├── __init__.py
│   └── excel_writer.py   # Excel 写入工具
└── data/                 # 输出目录
    └── .gitkeep
```

## 技术栈

- **Playwright** - 处理动态加载的网页
- **requests + urllib3** - HTTP 请求和重试机制
- **pandas** - 数据处理
- **openpyxl** - Excel 文件生成和格式化
- **tqdm** - 进度条显示
- **concurrent.futures** - 多线程并发

## 支持的仓库

| 仓库 | API 支持 | 统计方式 |
|------|---------|---------|
| PRIDE | ✅ | `fileCategory=RAW` 过滤 |
| MassIVE | ✅ | 文件后缀过滤 |
| iProX | ✅ | 文件列表 API |
| JPOST | ⚠️ | XML Fallback |
| 其他 | ⚠️ | XML Fallback |

## 常见问题

### Q: 爬取需要多长时间？
A: 取决于数据集数量和线程数。假设每个数据集 API 响应时间 0.5 秒：
- 100 个数据集，5 线程：约 10 秒
- 100 个数据集，单线程：约 50 秒

### Q: Raw_File_Count 为 0 是什么意思？
A: 可能原因：
1. 该数据集没有上传原始文件
2. 仓库 API 暂不支持该数据集
3. 网络请求失败（查看日志）

### Q: 如何只爬取不统计文件？
A: 使用 `--skip-raw-count` 参数，只获取基础信息。

### Q: 元数据链接打不开？
A: 确保网络可以访问 ProteomeXchange 网站。

### Q: 如何查看详细日志？
A: 日志保存在 `scraper.log` 文件中。

## 许可证

本项目仅供学习和研究使用，请遵守 ProteomeXchange 网站的使用条款和数据使用政策。

## 相关链接

- [ProteomeXchange 官网](https://www.proteomexchange.org/)
- [ProteomeCentral](https://proteomecentral.proteomexchange.org/)
- [PRIDE API 文档](https://www.ebi.ac.uk/pride/ws/archive/v2/)
- [MassIVE API](https://massive.ucsd.edu/ProteoSAFe/static/proteosafe.jsp)

---

**祝使用愉快！如有问题欢迎提 Issue。**
