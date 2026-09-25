"""붙임2 증빙용 화면 캡처. 공개 주소에서 헤드리스 크롬으로 찍어 data/reports/evidence/에 저장한다.

    uv run --with playwright python scripts/capture_evidence.py
"""

import asyncio
import datetime
import json
from pathlib import Path

from playwright.async_api import async_playwright

BASE = 'https://sportsbridge.o-r.kr'
OUT = 'data/reports/evidence'
Path(OUT).mkdir(parents=True, exist_ok=True)
sc = json.loads(Path('data/reports/scenario_demo/scenario.json').read_text(encoding='utf-8'))
best_ids = [a['id'] for a in sc['actions']]
now = datetime.datetime.now(datetime.UTC).astimezone().strftime('%Y-%m-%d %H:%M')
async def shot(pg,name,clip_h=None,full=False):
    if clip_h: await pg.screenshot(path=f'{OUT}/{name}.png', full_page=True, clip={'x':0,'y':0,'width':1366,'height':clip_h})
    else: await pg.screenshot(path=f'{OUT}/{name}.png', full_page=full)
async def goto(pg,path,wait=1200):
    for _ in range(3):
        r=await pg.goto(BASE+path)
        if r and r.status==200: break
        await pg.wait_for_timeout(1500)
    await pg.wait_for_load_state('networkidle'); await pg.wait_for_timeout(wait)
    assert '502' not in (await pg.title()), path
async def card_of(pg,sel,name):
    h=await pg.evaluate_handle(f"document.querySelector('{sel}').closest('.card')"); await h.as_element().screenshot(path=f'{OUT}/{name}.png')
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(viewport={'width':1366,'height':900},device_scale_factor=1.5,locale='ko-KR')
        pg=await ctx.new_page()
        pg.on('console', lambda m: print('console:', m.type, m.text[:200]) if m.type in ('error','warning') else None)
        pg.on('pageerror', lambda e: print('pageerror:', str(e)[:200]))
        pg.on('response', lambda r: print('resp', r.status, r.url[-70:]) if r.status>=400 else None)
        await goto(pg,'/'); await shot(pg,'e31_home')
        await pg.evaluate("(t)=>{const d=document.createElement('div');d.textContent=t;d.style.cssText='position:fixed;top:0;left:0;right:0;z-index:99999;background:#111;color:#fff;font:14px/1.6 sans-serif;padding:6px 14px;border-bottom:2px solid #4f8cff';document.body.prepend(d);}", f'접속 주소 {BASE}/ · 캡처 {now}')
        await shot(pg,'e12_home_url')
        await goto(pg,'/gap'); await shot(pg,'e33_gap',clip_h=1000)
        await goto(pg,'/gap/11110',1800); await pg.wait_for_selector('#region-sub:not(:has-text("불러오는"))', timeout=20000); await shot(pg,'e43_jongno',clip_h=1400)
        await goto(pg,'/gap/11110/candidates',1800); await pg.wait_for_timeout(3000); print('cand text:', (await pg.inner_text('#cand-summary'))[:200]); await shot(pg,'e53_candidates',clip_h=1250)
        await goto(pg,'/data',1800)
        try: await pg.wait_for_selector('tr.ver-detail', state='attached', timeout=20000)
        except Exception: print('VER-BODY:', (await pg.inner_text('#ver-body'))[:200], '| JOB:', (await pg.inner_text('#job-meta'))[:100]); raise
        await pg.wait_for_selector('#src-body tr', state='attached', timeout=20000); print('detail visible?', await pg.is_visible('tr.ver-detail details')); await pg.wait_for_timeout(500); await shot(pg,'e41_data_top',clip_h=1150)
        await card_of(pg,'#ver-body','e11_versions')
        det=await pg.query_selector('tr.ver-detail details[open]'); assert det, 'no step detail'
        await det.screenshot(path=f'{OUT}/e42_steps.png')
        await card_of(pg,'#src-body','e51_sources')
        await goto(pg,'/scenario')
        await pg.evaluate("(s)=>{localStorage.setItem('vgp_scenario',JSON.stringify(s));localStorage.setItem('vgp_selected_bundle',JSON.stringify(" + json.dumps(best_ids) + "));}", sc)
        await goto(pg,'/scenario/compare',2000)
        for el2 in await pg.query_selector_all('[data-pick]'):
            v=await el2.get_attribute('data-pick')
            if v and ',' in v: await el2.click(); break
        await pg.wait_for_timeout(1500); await shot(pg,'e44_compare',full=True)
        await goto(pg,'/scenario/plan',2500); await shot(pg,'e45_plan',clip_h=1500)
        await goto(pg,'/user'); await shot(pg,'e32_user_find',clip_h=1100)
        await goto(pg,'/user/voice?region=11110',1500); await shot(pg,'e46a_voice',clip_h=1100)
        await goto(pg,'/user/facilities?region=11110',1500)
        btn=await pg.query_selector('.facility-item, [data-fac], .fac-card, .list-item')
        if btn: await btn.click(); await pg.wait_for_timeout(1200)
        await shot(pg,'e54_facilities',clip_h=1100)
        m=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True,locale='ko-KR',user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        mp=await m.new_page(); await mp.goto(BASE+'/user'); await mp.wait_for_load_state('networkidle'); await mp.wait_for_timeout(1200)
        await mp.screenshot(path=f'{OUT}/e34_mobile.png')
        await b.close(); print('done')
asyncio.run(main())
