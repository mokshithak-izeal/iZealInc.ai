from pathlib import Path
import shutil
src=Path(__file__).resolve().parent;dst=Path.cwd()
for rel in ['app/database/automation.py','app/sources/base.py','app/sources/linkedin_alerts.py','app/workers/job_processor.py','app/mock_apply/store.py','app/api/automation.py','app/services/mock_auto_apply.py']:
    s=src/rel;d=dst/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(s,d)
main=dst/'main.py';text=main.read_text(encoding='utf-8')
imp='from app.api.automation import router as automation_router\n'
if imp not in text:text=text.replace('from app.api.preferences import router as preferences_router\n','from app.api.preferences import router as preferences_router\n'+imp)
if 'app.include_router(automation_router)' not in text:
    marker='app.include_router(preferences_router)'
    text=text.replace(marker,marker+';app.include_router(automation_router)')
text=text.replace("version='1.5.0'","version='1.7.0'").replace("'version':'1.5.0'","'version':'1.7.0'")
main.write_text(text,encoding='utf-8')
print('Installed JobAgent v1.7 automation lab.')
