"""Browser automation for the LOCAL /mock-apply test portal only."""
from pathlib import Path

def build_playwright_script(base_url,candidate,resume_path):
    resume=str(Path(resume_path).resolve())
    # Generates a runnable Playwright script; it targets only this project's mock portal.
    return f'''from playwright.sync_api import sync_playwright\nwith sync_playwright() as p:\n    browser=p.chromium.launch(headless=False)\n    page=browser.new_page()\n    page.goto({base_url!r} + "/mock-apply")\n    page.fill("input[name=full_name]", {candidate.get("full_name","")!r})\n    page.fill("input[name=email]", {candidate.get("email","")!r})\n    page.fill("input[name=phone]", {candidate.get("phone","")!r})\n    page.fill("input[name=years_experience]", str({candidate.get("years_experience",0)!r}))\n    page.select_option("select[name=work_authorization]", label={candidate.get("work_authorization","Yes")!r})\n    page.fill("textarea[name=interest]", {candidate.get("interest","Interested in this role based on the skills match.")!r})\n    page.set_input_files("input[name=resume]", {resume!r})\n    page.click("button[type=submit]")\n    page.wait_for_selector("#submission-status")\n    print(page.locator("#submission-status").inner_text())\n    browser.close()\n'''
