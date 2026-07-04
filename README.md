# 🤖 智能数据分析助手 (Smart Data Analyst)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![CI](https://github.com/h7720592-svg/smart-data-analyst/actions/workflows/ci.yml/badge.svg)](https://github.com/h7720592-svg/smart-data-analyst/actions)

> 基于 AI 的数据分析与可视化工具——上传数据，用自然语言与 AI 对话，即可获得精美的图表和洞察。

**📊 上传数据 → 💬 自然语言对话 → 📈 自动生成图表 → 📄 导出报告**

---

## ✨ 功能特性

- **📁 多格式支持** — CSV（自动检测编码）、Excel（.xlsx/.xls）、JSON
- **🔍 自动数据画像** — 统计信息、分布、缺失值、异常值、相关性分析
- **💬 自然语言对话** — 用中文或英文向 AI 提问你的数据
- **📈 AI 生成图表** — 柱状图、折线图、散点图、饼图、直方图、箱线图、热力图等 10+ 种图表
- **🔒 安全代码执行** — AST 白名单校验 + 受限沙箱 + 超时保护
- **📄 报告导出** — 下载为交互式 HTML 或可打印的 PDF
- **🌐 多 LLM 提供商** — DeepSeek（推荐）、OpenAI、Groq、Ollama（本地部署）、自定义 API

---

## 🚀 快速开始

### 1. 克隆项目并安装依赖

```bash
git clone https://github.com/h7720592-svg/smart-data-analyst.git
cd smart-data-analyst
pip install -r requirements.txt
```

### 2. 配置 API 密钥

复制环境变量模板并添加你的 API 密钥：

```bash
cp .env.example .env
# 编辑 .env 文件，至少填入一个 API 密钥
```

也可以在启动应用后在侧边栏中配置。

**推荐**：[DeepSeek](https://platform.deepseek.com) — 价格实惠，中文支持好，128K 上下文。

### 3. 启动应用

```bash
streamlit run app.py
```

在浏览器中打开 http://localhost:8501。

### 4. 使用流程

1. **📊 数据上传** — 上传你的数据文件
2. **💬 智能对话** — 与 AI 对话分析数据
3. **📄 导出报告** — 下载分析报告

---

## 📸 截图展示

> 运行 `streamlit run app.py` 启动应用后，可以截取三个主要页面的截图：数据上传、智能对话、导出报告。

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| UI 框架 | [Streamlit](https://streamlit.io) |
| 数据处理 | [Pandas](https://pandas.pydata.org)、[NumPy](https://numpy.org) |
| 自动 EDA | [ydata-profiling](https://github.com/ydataai/ydata-profiling) |
| 可视化 | [Plotly](https://plotly.com/python/) |
| LLM 集成 | [OpenAI SDK](https://github.com/openai/openai-python)（多提供商兼容） |
| 报告导出 | [Jinja2](https://jinja.palletsprojects.com)、[WeasyPrint](https://weasyprint.org) |

---

## 📁 项目结构

```
smart-data-analyst/
├── app.py                    # Streamlit 入口文件
├── pages/
│   ├── 01_📊_数据上传.py      # 文件上传与数据画像
│   ├── 02_💬_智能对话.py      # AI 对话与可视化
│   └── 03_📄_导出报告.py      # 报告生成
├── src/
│   ├── data_loader.py        # CSV/Excel/JSON 文件读取
│   ├── profiler.py           # 自动 EDA 与数据质量检查
│   ├── utils.py              # 会话状态、配置、工具函数
│   ├── llm/
│   │   ├── client.py         # 多提供商 LLM 客户端
│   │   ├── prompts.py        # 系统提示词与少样本示例
│   │   └── code_executor.py  # 安全代码执行沙箱
│   ├── viz/
│   │   ├── chart_registry.py # 支持的图表类型
│   │   └── renderer.py       # Plotly → Streamlit 渲染器
│   └── export/
│       ├── html_report.py    # Jinja2 HTML 报告构建器
│       └── pdf_report.py     # WeasyPrint PDF 转换器
├── assets/
│   ├── style.css             # 自定义 Streamlit 主题
│   └── report_template.html  # Jinja2 报告模板
├── tests/                    # 单元测试
├── requirements.txt
└── README.md
```

---

## 🔒 安全机制

代码执行沙箱采用三层防护：

1. **AST 白名单校验** — 仅允许导入安全模块（pandas、numpy、plotly、scipy）
2. **受限内置函数** — 移除 `open()`、`exec()`、`eval()`、`__import__()` 等危险函数
3. **进程超时** — 代码在子进程中运行，限制 30 秒超时

> ⚠️ 本项目为学生课程设计项目。如需生产环境使用，请在 Docker 或虚拟机中运行。

---

## 🧪 运行测试

```bash
pytest tests/ -v
```

---

## 🤝 参与贡献

欢迎贡献！详情请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的修改 (`git commit -m '添加精彩功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

---

## 📝 开源协议

MIT License — 详见 [LICENSE](LICENSE)。

---

## 🙏 致谢

- [Streamlit](https://streamlit.io) — 最快速构建数据应用的方式
- [Plotly](https://plotly.com) — 交互式 Python 可视化库
- [DeepSeek](https://deepseek.com) — 实惠且强大的 LLM API
- [ydata-profiling](https://github.com/ydataai/ydata-profiling) — 一行代码完成数据画像

---

*❤️ 作为一个开源课程项目编写*
