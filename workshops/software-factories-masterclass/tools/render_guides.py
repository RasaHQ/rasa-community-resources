"""Build browser-readable teaching pages (markdown-it-py 4.2.0)."""
from pathlib import Path
from markdown_it import MarkdownIt
import html
import re
ROOT = Path(__file__).resolve().parents[1]
MD = MarkdownIt('commonmark', {'html': True}).enable('table')
CSS = 'body{max-width:1000px;margin:60px auto;padding:0 28px;background:#FAF6F0;color:#181210;font:18px/1.65 system-ui}h1,h2,h3{font-family:Georgia;font-weight:400;line-height:1.2}h1{font-size:48px}h2{margin-top:48px;font-size:32px}a{color:#AA1E54}pre{padding:22px;background:#181210;color:#FAF6F0;overflow:auto;font-size:14px;border-radius:6px}code{font-size:.9em}table{border-collapse:collapse;width:100%;font-size:16px}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #C8C0B6}th{background:#EDE8E0}blockquote{border-left:4px solid #E85A91;margin:24px 0;padding:4px 24px;background:#FFFBF5}nav{padding-bottom:20px;border-bottom:1px solid #C8C0B6;font-size:15px}@media print{body{margin:0;font-size:11pt}pre{white-space:pre-wrap}h2,h3{break-after:avoid}tr{break-inside:avoid}}'
names = ['BEGINNER-PRIMER', 'README', 'PARTICIPANT-GUIDE', 'TECHNICAL-AUDIT', 'RUN-SHEET', 'BUILD-CONTRACT', 'LEARNING-CHECKPOINTS', 'ACCEPTANCE-HANDOFF']
files = [ROOT / (name + '.md') for name in names] + sorted((ROOT / 'book').glob('*.md'))
outputs = {f.with_suffix('.html').resolve() for f in files}
for source in files:
    body = MD.render(source.read_text())
    def local_link(match):
        target = (source.parent / (match[1] + '.html')).resolve()
        return 'href="' + match[1] + '.html' + (match[2] or '') + '"' if target in outputs else match[0]
    body = re.sub(r'href="([^"#]+)\.md(#[^"]*)?"', local_link, body)
    prefix = '../' if source.parent.name == 'book' else ''
    nav = f'<nav><a href="{prefix}README.html">Start</a> · <a href="{prefix}PARTICIPANT-GUIDE.html">Short route</a> · <a href="{prefix}book/README.html">Book</a> · <a href="{prefix}slides/index.html">Slides</a></nav>'
    source.with_suffix('.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(source.stem.replace('-', ' ')) + '</title><style>' + CSS + '</style>' + nav + '<main>' + body + '</main></html>')
print(f'Built {len(files)} teaching pages')
