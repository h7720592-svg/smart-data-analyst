"""PDF export using WeasyPrint."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def html_to_pdf(
    html_content: str,
    output_path: str,
    use_cjk_fonts: bool = True,
) -> str:
    """Convert HTML content to PDF using WeasyPrint.

    Args:
        html_content: Complete HTML string.
        output_path: Path to save the PDF file.
        use_cjk_fonts: If True, configure CJK font fallbacks for Chinese text.

    Returns:
        Path to the generated PDF file.

    Raises:
        ImportError: If weasyprint is not installed.
        RuntimeError: If PDF generation fails.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "需要安装 weasyprint 才能导出 PDF。请运行: pip install weasyprint"
        )

    # Ensure output directory exists
    output_path = str(Path(output_path).resolve())
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        html = HTML(string=html_content)

        # Try with CJK font configuration
        if use_cjk_fonts:
            # Common CJK fonts on different platforms
            cjk_fonts = [
                # Windows
                '"Microsoft YaHei"',
                '"SimHei"',
                '"SimSun"',
                # macOS
                '"PingFang SC"',
                '"Heiti SC"',
                # Linux
                '"Noto Sans CJK SC"',
                '"WenQuanYi Micro Hei"',
                '"WenQuanYi Zen Hei"',
                # Generic fallback
                "sans-serif",
            ]
            font_family = ", ".join(cjk_fonts)
            css = f"""
            @page {{
                size: A4;
                margin: 2cm;
                @top-center {{
                    content: "Smart Data Analyst - 数据分析报告";
                    font-size: 10px;
                    color: #999;
                    font-family: {font_family};
                }}
                @bottom-center {{
                    content: "第 " counter(page) " 页";
                    font-size: 10px;
                    color: #999;
                    font-family: {font_family};
                }}
            }}
            body {{
                font-family: {font_family};
                line-height: 1.6;
            }}
            """
            html.write_pdf(output_path, stylesheets=[], presentational_hints=True)
        else:
            html.write_pdf(output_path)

        return output_path

    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        raise RuntimeError(f"PDF 生成失败: {e}") from e
