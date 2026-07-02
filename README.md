# 🤖 智能数据分析助手 (Smart Data Analyst)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](https://github.com)

> AI-powered data analysis and visualization — upload your data, chat with AI, get beautiful charts and insights.

**📊 上传数据 → 💬 自然语言对话 → 📈 自动生成图表 → 📄 导出报告**

---

## ✨ Features

- **📁 Multi-format Support** — CSV (auto encoding detection), Excel (.xlsx/.xls), JSON
- **🔍 Auto Data Profiling** — Statistics, distributions, missing values, outliers, correlations
- **💬 Natural Language Chat** — Ask questions about your data in plain Chinese or English
- **📈 AI-Generated Charts** — Bar, line, scatter, pie, histogram, box plot, heatmap, and 10+ more
- **🔒 Safe Code Execution** — AST validation + restricted sandbox + timeout protection
- **📄 Report Export** — Download as interactive HTML or printable PDF
- **🌐 Multi-Provider LLM** — DeepSeek (recommended), OpenAI, Groq, Ollama (local), custom API

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/smart-data-analyst.git
cd smart-data-analyst
pip install -r requirements.txt
```

### 2. Configure API Key

Copy the environment template and add your API key:

```bash
cp .env.example .env
# Edit .env — add at least one API key
```

Or configure in the app sidebar after launching.

**Recommended**: [DeepSeek](https://platform.deepseek.com) — affordable, great Chinese support, 128K context.

### 3. Run

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

### 4. Use

1. **📊 数据上传** — Upload your data file
2. **💬 智能对话** — Chat with AI about your data
3. **📄 导出报告** — Download the analysis report

---

## 📸 Screenshots

*(Add screenshots here after running the app)*

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | [Streamlit](https://streamlit.io) |
| Data Processing | [Pandas](https://pandas.pydata.org), [NumPy](https://numpy.org) |
| Auto EDA | [ydata-profiling](https://github.com/ydataai/ydata-profiling) |
| Visualization | [Plotly](https://plotly.com/python/) |
| LLM Integration | [OpenAI SDK](https://github.com/openai/openai-python) (multi-provider) |
| Report Export | [Jinja2](https://jinja.palletsprojects.com), [WeasyPrint](https://weasyprint.org) |

---

## 📁 Project Structure

```
smart-data-analyst/
├── app.py                    # Streamlit entry point
├── pages/
│   ├── 01_📊_数据上传.py      # File upload & profiling
│   ├── 02_💬_智能对话.py      # AI chat & visualization
│   └── 03_📄_导出报告.py      # Report generation
├── src/
│   ├── data_loader.py        # CSV/Excel/JSON file reader
│   ├── profiler.py           # Auto-EDA & data quality checks
│   ├── utils.py              # Session state, config, helpers
│   ├── llm/
│   │   ├── client.py         # Multi-provider LLM client
│   │   ├── prompts.py        # System prompts & few-shot examples
│   │   └── code_executor.py  # Safe code execution sandbox
│   ├── viz/
│   │   ├── chart_registry.py # Supported chart types
│   │   └── renderer.py       # Plotly → Streamlit renderer
│   └── export/
│       ├── html_report.py    # Jinja2 HTML report builder
│       └── pdf_report.py     # WeasyPrint PDF converter
├── assets/
│   ├── style.css             # Custom Streamlit theme
│   └── report_template.html  # Jinja2 report template
├── tests/                    # Unit tests
├── requirements.txt
└── README.md
```

---

## 🔒 Security

The code execution sandbox uses three layers of defense:

1. **AST Whitelist Validation** — Only safe modules (pandas, numpy, plotly, scipy) can be imported
2. **Restricted Builtins** — `open()`, `exec()`, `eval()`, `__import__()`, etc. are removed
3. **Process Timeout** — Code runs in a subprocess with a 30-second timeout

> ⚠️ This is a student project. For production use, run inside Docker or a VM.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Streamlit](https://streamlit.io) — The fastest way to build data apps
- [Plotly](https://plotly.com) — Interactive Python visualization
- [DeepSeek](https://deepseek.com) — Affordable and powerful LLM API
- [ydata-profiling](https://github.com/ydataai/ydata-profiling) — One-line data profiling

---

*Made with ❤️ as an open-source course project*
