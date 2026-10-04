#!/usr/bin/env python3
"""Test the supplied preview player in Chromium. Requires Playwright and a browser."""
from pathlib import Path
import argparse,json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--chromium');args=a.parse_args()
report={'scope':'Chromium SVG/DOM preview tests only; no Pyodide or pygame integration.', 'errors':[]}
with sync_playwright() as p:
    launch={'headless':True,'args':['--no-sandbox']}
    if args.chromium:launch['executable_path']=args.chromium
    browser=p.chromium.launch(**launch)
    page=browser.new_page(viewport={'width':1400,'height':1000},device_scale_factor=1)
    page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.set_content((ROOT/'gallery.html').read_text(),wait_until='load')
    report['browser_version']=browser.version
    report['loading']='Self-contained document loaded with set_content; no network or asset server.'
    report['asset_cards']=page.locator('.card').count()
    report['master_image_elements']=page.locator('svg image').count()
    report['samples']=page.evaluate('''() => {
      const s=window.demoStage,errors=[];let tested=0;
      for(const c of TlfRobotArt.clips)for(const direction of ['north','east','south','west'])for(const p of [0,.25,.5,.75,1]) {
        const o={direction,heading:'west',count:2,bag:1,painted:true};
        s.render(c.key,p,o);const expected=s.svg.outerHTML;
        s.render('crystal.transfer',.5,{transfer:'put',count:9,bag:'infinite'});
        s.render('input.waiting',.73,{input:'time'});
        s.render('error.wall',.63,{direction:'south'});
        s.render('sense.edge',.64,{direction:'east',result:false});
        s.render(c.key,p,o);tested++;
        if(s.svg.outerHTML!==expected)errors.push(c.key+' '+direction+' '+p);
      }
      return {tested,historyDependentFrames:errors};
    }''')
    report['invariants']=page.evaluate('''() => {
      const s=window.demoStage,errors=[];let checks=0;
      for(const transfer of ['take','put'])for(const p of [0,.249,.25,.5,.799,.8,1]){
        const v=s.render('crystal.transfer',p,{transfer,count:2,bag:1});checks++;
        if(v.cellCount+v.bagCount+v.carried!==3)errors.push('finite conservation '+transfer+' '+p);
      }
      for(const bag of [0,1,'infinite']){
        const v=s.render('sense.bag',1,{bag});checks++;
        if(v.result!==(bag===0))errors.push('bag_empty '+bag);
      }
      const v=s.render('sense.bag',1,{bag:'infinite',subject:'count'});checks++;
      if(v.result!==null)errors.push('infinite bag_count');
      for(const direction of ['north','east','south','west']){
        s.render('sense.edge',0,{direction,heading:'east'});const before=s.parts.body.getAttribute('transform');
        s.render('sense.edge',1,{direction,heading:'east'});checks++;
        if(s.parts.body.getAttribute('transform')!==before)errors.push('sensor rotated body');
      }
      if(!s.render('paint.apply',1,{painted:false}).painted)errors.push('paint');checks++;
      if(s.render('paint.erase',1,{painted:true}).painted)errors.push('erase');checks++;
      return {checks,errors};
    }''')
    report['playback']=page.evaluate('''async () => {
      const s=window.demoStage, sleep=ms=>new Promise(r=>setTimeout(r,ms));const errors=[];
      let c=s.play('move.step',{speed:1});c.finished.catch(()=>{});await sleep(40);c.pause();
      const frozen=s.svg.outerHTML;await sleep(70);if(frozen!==s.svg.outerHTML)errors.push('pause changed frame');
      c.resume();await c.finished;if(s.last.progress!==1)errors.push('did not finish');
      c=s.play('move.step',{});const cancelled=c.finished.then(()=>false,e=>e.name==='AbortError');
      await sleep(30);c.cancel();if(!await cancelled)errors.push('cancel did not reject');
      if(s.last.progress!==0)errors.push('cancel did not restore before');
      let settled=false;c=s.play('input.waiting',{input:'key'});c.finished.then(()=>settled=true);
      await sleep(80);if(settled)errors.push('input prematurely completed');
      c.completeInput('space');const value=await c.finished;if(value!=='space')errors.push('input reply lost');
      return {pause:true,cancel:true,input_wait:true,errors};
    }''')
    page.evaluate("pick('paint.apply');document.getElementById('progress').value=65;paintAt(.65)")
    page.locator('#stage').screenshot(path=str(ROOT.parent/'tlfrobot-svg-action-preview.png'))
    page.evaluate("pick('move.step');window.scrollTo(0,0)")
    page.screenshot(path=str(ROOT.parent/'tlfrobot-svg-gallery-preview.png'))
    mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    mobile.set_content((ROOT/'gallery.html').read_text(),wait_until='load')
    report['mobile']=mobile.evaluate('''() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,cards:document.querySelectorAll('.card').length})''')
    mobile.screenshot(path=str(ROOT.parent/'tlfrobot-svg-mobile-preview.png'))
    browser.close()
passed=(not report['errors'] and report['asset_cards']==37 and report['master_image_elements']==0
        and not report['samples']['historyDependentFrames'] and not report['invariants']['errors']
        and not report['playback']['errors'] and report['mobile']['scrollWidth']<=report['mobile']['width'])
report['status']='passed' if passed else 'failed'
(ROOT/'browser-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if not passed:raise SystemExit(1)
