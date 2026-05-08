import re
import markdown
from pathlib import Path
from integrations.anki_connect import AnkiConnector

def convert_math_and_markdown(md_text):
    block_exprs = []
    def replace_block(m):
        block_exprs.append(m.group(1).strip())
        return f"BLOCKMATH{len(block_exprs)-1}BLOCKMATH"
    text = re.sub(r'\$\$(.*?)\$\$', replace_block, md_text, flags=re.DOTALL)
    inline_exprs = []
    def replace_inline(m):
        inline_exprs.append(m.group(1).strip())
        return f"INLINEMATH{len(inline_exprs)-1}INLINEMATH"
    text = re.sub(r'\$(.*?)\$', replace_inline, text)
    html = markdown.markdown(text, extensions=['extra', 'nl2br', 'sane_lists'])
    for i, expr in enumerate(block_exprs):
        expr_fixed = expr.replace('&', '&').replace('<', '<').replace('>', '>')
        html = html.replace(f"BLOCKMATH{i}BLOCKMATH", f'<anki-mathjax block="true">{expr_fixed}</anki-mathjax>')
    for i, expr in enumerate(inline_exprs):
        expr_fixed = expr.replace('&', '&').replace('<', '<').replace('>', '>')
        html = html.replace(f"INLINEMATH{i}INLINEMATH", f'<anki-mathjax>{expr_fixed}</anki-mathjax>')
    return html

class ObsidianSync:
    @staticmethod
    def sync_file(file_path, deck_name, model_name="Blank"):
        file_path = Path(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
        if not content.startswith('## '): content = '\n## (Intro)\n' + content
        sections = re.split(r'\n## ', content)
        for sec in sections:
            if not sec.strip(): continue
            lines = sec.strip().split('\n', 1)
            title = lines[0].lstrip('#').strip()
            body = lines[1] if len(lines) > 1 else ""
            html = convert_math_and_markdown(body)
            AnkiConnector.add_note(deck_name, model_name, {"대주제": file_path.stem, "소주제": title, "내용": html}, tags=["obsidian_sync"])
