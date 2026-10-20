from pathlib import Path
import shutil,re
src=Path(__file__).resolve().parent;dst=Path.cwd()
for rel in ['app/sources/linkedin_email.py','app/api/email_ingestion.py']:
    s=src/rel;d=dst/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(s,d)
main=dst/'main.py';text=main.read_text(encoding='utf-8')
imp='from app.api.email_ingestion import router as email_ingestion_router\n'
if imp not in text:
    # robustly insert before BASE/app declaration
    m=re.search(r'^(BASE\s*=|app\s*=)',text,re.M)
    text=text[:m.start()]+imp+text[m.start():] if m else imp+text
if 'app.include_router(email_ingestion_router)' not in text:
    # append after last include_router line
    matches=list(re.finditer(r'^.*app\.include_router\([^\n]+$',text,re.M))
    if matches:
        pos=matches[-1].end();text=text[:pos]+'\napp.include_router(email_ingestion_router)'+text[pos:]
    else:text+='\napp.include_router(email_ingestion_router)\n'
text=text.replace("version='1.7.0'","version='1.7.1'").replace("'version':'1.7.0'","'version':'1.7.1'")
main.write_text(text,encoding='utf-8')
print('Installed v1.7.1 LinkedIn alert email importer.')
