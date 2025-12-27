# ProteomeXchange 数据集爬虫

一个用于从 [ProteomeXchange](https://www.proteomexchange.org/) 网站爬取蛋白质组学数据集信息的 Python 爬虫工具。

## 功能特性

- 🔍 根据关键词搜索 ProteomeXchange 数据集
- 📊 自动提取 8 个核心字段信息
- 🔗 生成包含可点击元数据链接的 Excel 文件
- ⚡ 使用 Playwright 处理动态页面
- 🎯 支持批量爬取，自动去重

## 提取的字段

每个数据集提取以下 8 个字段（按顺序）：

1. **样品编号** (PXD****) - 数据集唯一标识符
2. **Title** - 数据集标题
3. **lab head** - 实验室负责人信息
4. **Description** - 研究描述
5. **Instrument List** - 使用仪器列表
6. **submitter keyword** - 提交者关键词
7. **Hosting Repository** - 托管仓库（如 PRIDE）
8. **元数据网址** - 可直接点击跳转到元数据页面

## 安装

### 前置要求

- Python 3.7 或更高版本
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
python main.py --keyword "你的关键词" --output "输出文件名.xlsx"
```

### 示例

```bash
# 搜索关键词 "proteoform"
python main.py --keyword "proteoform" --output "proteoform.xlsx"

# 搜索多个关键词
python main.py --keyword "top down" --output "top_down.xlsx"

# 限制爬取数量（用于测试）
python main.py --keyword "cancer" --max-datasets 10 --output "cancer_10.xlsx"
```

### 参数说明

| 参数 | 简写 | 说明 | 必需 | 默认值 |
|------|------|------|------|--------|
| `--keyword` | `-k` | 搜索关键词 | ✅ | - |
| `--output` | `-o` | 输出 Excel 文件名 | ❌ | `proteomexchange_data.xlsx` |
| `--max-datasets` | `-m` | 最大爬取数据集数量 | ❌ | 全部 |
| `--headless` | - | 无头模式运行（不显示浏览器） | ❌ | True |
| `--show-browser` | - | 显示浏览器窗口（用于调试） | ❌ | False |

## 输出文件

爬取完成后，Excel 文件会保存在 `data/` 目录下，包含：
- 8 列数据，按指定顺序排列
- 自动格式化的表格（列宽自适应、标题行加粗）
- 最后一列的元数据网址可直接点击跳转

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
│   └── px_scraper.py     # ProteomeXchange 爬虫
├── utils/                # 工具模块
│   ├── __init__.py
│   └── excel_writer.py   # Excel 写入工具
└── data/                 # 输出目录
    └── .gitkeep
```

## 技术栈

- **Playwright** - 用于处理动态加载的网页
- **pandas** - 数据处理
- **openpyxl** - Excel 文件生成和格式化
- **BeautifulSoup4** - HTML 解析（备用）

## 注意事项

1. **爬取速度**：每个数据集约需 6-7 秒（包含页面加载和数据提取）
2. **网络要求**：需要能够访问 ProteomeXchange 网站
3. **资源占用**：Playwright 会启动 Chromium 浏览器，占用一定内存
4. **合理使用**：建议控制爬取频率，遵守网站使用条款

## 常见问题

### Q: 提示 "Permission denied" 错误？
A: Excel 文件可能已被打开，请关闭文件后重试。

### Q: 如何只爬取少量数据测试？
A: 使用 `--max-datasets` 参数限制数量，如：`--max-datasets 5`

### Q: 爬取过程中可以中断吗？
A: 可以，按 `Ctrl+C` 即可安全中断程序。

### Q: 元数据链接打不开？
A: 确保网络可以访问 ProteomeXchange 网站，某些地区可能需要科学上网。

## 开发者

本项目基于 Python 开发，使用 Playwright 处理动态网页内容。

## 许可证

本项目仅供学习和研究使用，请遵守 ProteomeXchange 网站的使用条款和数据使用政策。

## 相关链接

- [ProteomeXchange 官网](https://www.proteomexchange.org/)
- [ProteomeCentral](https://proteomecentral.proteomexchange.org/)
- [Playwright 文档](https://playwright.dev/python/)

---

**祝使用愉快！如有问题欢迎提 Issue。**
