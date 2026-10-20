from pathlib import Path
root=Path(__file__).resolve().parent
project=Path.cwd()
index=project/'templates'/'index.html'
addon_src=root/'static'/'js'/'v16_addon.js'
addon_dst=project/'static'/'js'/'v16_addon.js'
if not index.exists(): raise SystemExit('Run this from the JobAgent project root. templates/index.html was not found.')
addon_dst.write_text(addon_src.read_text(encoding='utf-8'),encoding='utf-8')
s=index.read_text(encoding='utf-8')
tag='<script src="/static/js/v16_addon.js?v=160"></script>'
if tag not in s:
    pos=s.lower().rfind('</body>')
    s=(s[:pos]+tag+'\n'+s[pos:]) if pos!=-1 else s+'\n'+tag+'\n'
    index.write_text(s,encoding='utf-8')
print('v1.6 UI add-on installed successfully.')
