"""
Markdown 和 LaTeX 渲染模块。
将 Markdown 文本（可能包含 LaTeX 公式）转换为 HTML，用于在 QTextBrowser 中显示。
"""
import re
import base64
import io
import sys
from typing import Optional

try:
    import markdown
except ImportError:
    markdown = None

try:
    import matplotlib.mathtext as mathtext
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    rcParams['mathtext.fontset'] = 'cm'  # 使用 Computer Modern 字体
    rcParams['mathtext.rm'] = 'serif'
    rcParams['mathtext.it'] = 'serif:italic'
    rcParams['mathtext.bf'] = 'serif:bold'
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class MarkdownRenderer:
    """
    将 Markdown 文本渲染为 HTML，支持内联 LaTeX 公式（$...$）和块级公式（$$...$$）。
    """

    def __init__(self, css_style: Optional[str] = None):
        """
        :param css_style: 自定义 CSS 样式字符串，用于美化 HTML 输出。
        """
        self.css_style = css_style or self.default_css()

    @staticmethod
    def default_css() -> str:
        """
        返回默认的 CSS 样式，用于美化渲染后的 HTML。
        """
        return """
        <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #fff;
            padding: 10px;
        }
        h1, h2, h3, h4 {
            color: #2c3e50;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
        }
        code {
            background-color: #f5f5f5;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }
        pre {
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }
        blockquote {
            border-left: 4px solid #ddd;
            padding-left: 15px;
            color: #666;
            margin-left: 0;
        }
        img {
            max-width: 100%;
            height: auto;
        }
        .math-inline {
            vertical-align: middle;
        }
        .math-block {
            display: block;
            text-align: center;
            margin: 1em 0;
        }
        </style>
        """

    def latex_to_data_url(self, latex: str, is_inline: bool = True) -> str:
        """
        将 LaTeX 公式渲染为 PNG 图像，并返回 data URL。
        如果 matplotlib 不可用，则回退到纯文本占位符。
        """
        if not HAS_MATPLOTLIB:
            return f'<span class="math-placeholder">{latex}</span>'

        try:
            # 设置 mathtext 属性
            dpi = 100
            if is_inline:
                fontsize = 10
            else:
                fontsize = 12

            # 使用 mathtext 将 LaTeX 渲染为图像
            fig = plt.figure(figsize=(0.1, 0.1), dpi=dpi)
            fig.patch.set_alpha(0.0)  # 透明背景
            text = fig.text(0, 0, latex, fontsize=fontsize, usetex=False,
                            ha='left', va='bottom', color='black')

            # 调整图像大小以适应内容
            fig.canvas.draw()
            bbox = text.get_window_extent()
            width_inch = bbox.width / dpi
            height_inch = bbox.height / dpi
            fig.set_size_inches(width_inch, height_inch)
            text.set_position((0, 0))

            # 保存到字节流
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0.05, transparent=True)
            plt.close(fig)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('ascii')
            return f'data:image/png;base64,{img_data}'
        except Exception as e:
            print(f"LaTeX 渲染失败 {latex}: {e}")
            return f'<span class="math-error">{latex}</span>'

    def render(self, markdown_text: str) -> str:
        """
        将 Markdown 文本转换为 HTML，并将 LaTeX 公式替换为图像。
        """
        if markdown is None:
            # 如果没有 markdown 库，则原样返回
            html = markdown_text.replace('\n', '<br>')
        else:
            # 首先提取 LaTeX 公式，用占位符替换
            latex_pattern = r'\$\$(.*?)\$\$|\$(.*?)\$'
            matches = list(re.finditer(latex_pattern, markdown_text, re.DOTALL))
            placeholders = []
            processed_text = markdown_text
            for i, match in enumerate(matches):
                latex = match.group(1) or match.group(2)  # 块级或内联
                is_inline = match.group(2) is not None  # 如果第二个组匹配，则是内联
                placeholder = f'<!-- LATEX_PLACEHOLDER_{i} -->'
                placeholders.append((placeholder, latex, is_inline))
                processed_text = processed_text.replace(match.group(0), placeholder, 1)

            # 将 Markdown 转换为 HTML
            html = markdown.markdown(processed_text, extensions=['extra', 'codehilite', 'tables'])

            # 将占位符替换为图像标签
            for placeholder, latex, is_inline in placeholders:
                data_url = self.latex_to_data_url(latex, is_inline)
                if is_inline:
                    img_tag = f'<img class="math-inline" src="{data_url}" alt="{latex}" />'
                else:
                    img_tag = f'<div class="math-block"><img src="{data_url}" alt="{latex}" /></div>'
                html = html.replace(placeholder, img_tag)

        # 包装在完整的 HTML 文档中
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            {self.css_style}
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        return full_html


# 全局渲染器实例
_default_renderer = None

def get_renderer() -> MarkdownRenderer:
    """获取全局渲染器实例（懒加载）。"""
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = MarkdownRenderer()
    return _default_renderer

def render_markdown(text: str) -> str:
    """便捷函数：渲染 Markdown 文本为 HTML。"""
    return get_renderer().render(text)


if __name__ == "__main__":
    # 测试代码
    test_md = """
# 测试标题

这是一个段落，包含内联公式 $E = mc^2$ 和块级公式：

$$
\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}
$$

- 列表项
- **粗体** 和 *斜体*

> 引用块

`行内代码`
"""
    print("测试 Markdown 渲染...")
    result = render_markdown(test_md)
    print(result[:500])