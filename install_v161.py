from pathlib import Path
root=Path(__file__).resolve().parent;project=Path.cwd();index=project/'templates'/'index.html';src=root/'static'/'js'/'v16_addon.js';dst=project/'static'/'js'/'v16_addon.js'
if not index.exists():raise SystemExit('Run this command from the JobAgent project root.')
dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(src.read_text(encoding='utf-8'),encoding='utf-8')
s=index.read_text(encoding='utf-8')
# remove earlier v160/v161 addon tags and insert one current tag
import re
s=re.sub(r'\s*<script src="/static/js/v16_addon\.js\?v=16[01]"></script>\s*','\n',s)
tag='<script src="/static/js/v16_addon.js?v=161"></script>'
pos=s.lower().rfind('</body>');s=(s[:pos]+tag+'\n'+s[pos:]) if pos!=-1 else s+'\n'+tag+'\n';index.write_text(s,encoding='utf-8')
print('v1.6.1 installed. Candidate preferences UI will now be injected automatically.')
