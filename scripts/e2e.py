from playwright.sync_api import sync_playwright
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True, args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1280,'height':1000}, device_scale_factor=1)
 errors=[]
 page.on('pageerror', lambda e: errors.append(str(e)))
 page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
 page.route('https://fonts.gstatic.com/**', lambda route: route.abort())
 page.goto('http://127.0.0.1:5173', wait_until='domcontentloaded'); page.get_by_text('Knowledge index ready').wait_for()
 page.screenshot(path=str(root/'data'/'groundwork-entry.png'),full_page=True)
 page.get_by_label('Resume file').set_input_files(str(root/'examples/resume.txt'))
 page.get_by_label('Target role').select_option('ai-ml')
 page.get_by_role('button',name='Build my interview').click()
 page.get_by_label('Your answer').wait_for(timeout=360000)
 page.get_by_text('View retrieval trace & textbook evidence').click()
 page.screenshot(path=str(root/'data'/'groundwork-evidence.png'),full_page=True)
 page.get_by_text('View retrieval trace & textbook evidence').click()
 for i in range(3):
  page.get_by_label('Your answer').fill('I would split training and test data before fitting preprocessing. For the RAG project, I would measure relevance on held-out queries and inspect failure cases, rather than assume similar vectors are always correct. I would compare lexical and vector retrieval with a fixed evaluation set.')
  page.get_by_role('button',name='Save & review session' if i==2 else 'Save answer & continue').click()
  if i<2: page.get_by_text(f'QUESTION {i+2:02d} / 03').wait_for()
 page.get_by_role('heading',name='Interview complete',exact=True).wait_for()
 page.screenshot(path=str(root/'data'/'groundwork-summary.png'),full_page=True)
 sid=page.evaluate("localStorage.getItem('groundwork-session')")
 page.reload(); page.get_by_role('heading',name='Interview complete',exact=True).wait_for()
 page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(root/'data'/'groundwork-mobile.png'),full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
 assert not errors, errors
 print(json.dumps({'session':sid,'page_errors':errors,'mobile_overflow':False}))
 b.close()
