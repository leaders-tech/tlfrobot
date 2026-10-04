/* Timo vector-art preview player. No Python bridge and no game rules. */
(function (global) {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const clamp = x => Math.min(1, Math.max(0, x));
  const smooth = x => { x=clamp(x); return x*x*(3-2*x); };
  const phase = (p,a,b) => smooth((p-a)/(b-a));
  const pulse = p => Math.sin(Math.PI*clamp(p));
  const DIR = {north:0,east:90,south:180,west:270};
  let nextId=0;
  function el(tag,attrs={},parent) {
    const node=document.createElementNS(NS,tag);
    for(const [k,v] of Object.entries(attrs)) node.setAttribute(k,String(v));
    if(parent) parent.appendChild(node);
    return node;
  }
  function opacity(node,value) { node.setAttribute('opacity',String(value)); }
  function mount(text,parent,x=0,y=0,w=128,h=128) {
    const parsed=new DOMParser().parseFromString(text,'image/svg+xml');
    if(parsed.querySelector('parsererror')) throw new Error('Invalid SVG asset.');
    const node=document.importNode(parsed.documentElement,true);
    const prefix='timo-'+(++nextId)+'-';
    const ids=new Map();
    for(const n of [node,...node.querySelectorAll('[id]')]) {
      if(n.id) { ids.set(n.id,prefix+n.id); n.id=prefix+n.id; }
    }
    for(const n of [node,...node.querySelectorAll('*')]) {
      for(const attr of Array.from(n.attributes)) {
        let value=attr.value;
        if((attr.localName==='href') && value.startsWith('#') && ids.has(value.slice(1))) value='#'+ids.get(value.slice(1));
        value=value.replace(/url\(#([^)]+)\)/g,(all,id)=>ids.has(id)?'url(#'+ids.get(id)+')':all);
        if(value!==attr.value) n.setAttributeNS(attr.namespaceURI,attr.name,value);
      }
    }
    node.setAttribute('x',x);node.setAttribute('y',y);node.setAttribute('width',w);node.setAttribute('height',h);
    node.setAttribute('overflow','visible');parent.appendChild(node);return node;
  }
  const C = [
    ['move.step',350,'move()','Шаг'],['turn',220,'turn_left()','Поворот'],
    ['crystal.transfer',420,'take() / put()','Перенос кристалла'],['paint.apply',450,'paint()','Закраска'],
    ['paint.erase',350,'erase()','Стирание'],['sense.edge',180,'front_clear()','Проверка границы'],
    ['sense.cell',180,'on_crystal() / painted()','Проверка клетки'],['sense.bag',180,'bag_empty()','Проверка сумки'],
    ['sense.heading',180,'facing_north()','Проверка направления'],['error.wall',280,'move() → error','Столкновение'],
    ['error.object',240,'take() / put() → error','Нет предмета'],['error.status',160,'Python / runtime error','Ошибка'],
    ['input.waiting',1000,'wait_key() / wait_click() / wait()','Ожидание ввода'],
    ['input.received',120,'wait_key() → key','Полученный ввод'],['lifecycle',160,'program completed','Завершение'],
    ['verdict',360,'checker verdict','Результат проверки'],['view.reset',120,'Reset','Сброс'],
    ['view.camera',180,'Pan / zoom','Камера'],['focus.feedback',120,'source / value / counter','Подсветка'],
    ['idle.blink',120,'ambient only','Моргание']
  ].map((a,i)=>({id:'C'+String(i+1).padStart(2,'0'),key:a[0],duration:a[1],call:a[2],title:a[3]}));
  const DATA=Object.fromEntries(C.map(c=>[c.key,c]));

  class Stage {
    constructor(container,assets) {
      this.assets=assets;this.container=container;
      this.svg=el('svg',{viewBox:'0 0 620 432',role:'img','aria-label':'Timo vector animation demonstration'});
      this.svg.style.width='100%';this.svg.style.display='block';
      container.replaceChildren(this.svg);
      const defs=el('defs',{},this.svg);this.clipId='paint-clip-'+(++nextId);
      this.clip=el('clipPath',{id:this.clipId,clipPathUnits:'userSpaceOnUse'},defs);
      this.wipe=el('rect',{x:152,y:152,width:128,height:128},this.clip);
      this.world=el('g',{},this.svg);
      for(let y=0;y<3;y++) for(let x=0;x<3;x++) {
        el('rect',{x:24+x*128,y:24+y*128,width:128,height:128,fill:(x+y)%2?'#F5F7F5':'#FBFCF9',stroke:'#D8E2E4','stroke-width':1},this.world);
        el('circle',{cx:88+x*128,cy:88+y*128,r:1.5,fill:'#CAD8DD'},this.world);
      }
      this.paintGroup=el('g',{'clip-path':`url(#${this.clipId})`},this.world);
      this.paint=mount(assets['world/paint.svg'],this.paintGroup,152,152,128,128);
      this.target=mount(assets['world/marker-target.svg'],this.world,152,152,128,128);
      this.wallGroup=el('g',{},this.world);
      this.wall=mount(assets['world/wall.svg'],this.wallGroup,152,140,128,24);
      this.edgeMark=el('line',{x1:166,y1:152,x2:266,y2:152,stroke:'#367FC1','stroke-width':4,'stroke-linecap':'round'},this.wallGroup);
      this.actor=el('g',{transform:'translate(152 152)'},this.world);
      this.robot=mount(assets['robot/robot.svg'],this.actor);
      this.parts=Object.fromEntries(Array.from(this.robot.querySelectorAll('[data-part]')).map(n=>[n.dataset.part,n]));
      this.base=Object.fromEntries(Object.entries(this.parts).map(([k,n])=>[k,{transform:n.getAttribute('transform')||'',opacity:n.getAttribute('opacity')??'1'}]));
      this.armBack=el('path',{fill:'none',stroke:'#21364B','stroke-width':6,'stroke-linecap':'round'},this.actor);
      this.armFront=el('path',{fill:'none',stroke:'#CCDCE2','stroke-width':3,'stroke-linecap':'round'},this.actor);
      // Only the known claw geometry is lifted above the procedural telescoping link.
      this.claw=el('g',{},this.actor);
      this.clawParts=['gripper-left','gripper-right'].map(n=>{
        const c=this.parts[n].cloneNode(true);c.removeAttribute('id');c.removeAttribute('data-part');
        for(const d of c.querySelectorAll('[id]')) d.removeAttribute('id');
        this.claw.appendChild(c);return c;
      });
      this.object=mount(assets['world/crystal.svg'],this.world,247,245,32,32);
      this.objectBadge=el('rect',{x:251,y:267,width:26,height:12,rx:5,fill:'#F8F6EE',stroke:'#21364B','stroke-width':.8},this.world);
      this.objectCount=el('text',{x:264,y:277,'text-anchor':'middle','font-size':10,'font-family':'system-ui, sans-serif','font-weight':700,fill:'#21364B'},this.world);
      this.carried=mount(assets['world/crystal.svg'],this.world,0,0,24,24);
      this.edgePulseGroup=el('g',{},this.world);
      this.edgePulse=mount(assets['hints/sensor-pulse.svg'],this.edgePulseGroup,200,150,32,36);
      this.arrowGroup=el('g',{},this.world);this.arrow=mount(assets['hints/direction-arrow.svg'],this.arrowGroup,200,152,32,32);
      this.focus=mount(assets['hints/focus-ring.svg'],this.world,152,152,128,128);
      this.focusSmall=mount(assets['hints/focus-ring.svg'],this.world,240,239,47,47);
      el('rect',{x:431,y:24,width:165,height:384,rx:20,fill:'#EDF3F4'},this.svg);
      this.label('CARGO',513,51,11,'#537486');
      this.bag=mount(assets['hud/bag.svg'],this.svg,477,67,72,72);
      this.bagValue=this.label('0',513,160,19,'#21364B');
      this.bagFocus=mount(assets['hints/focus-ring.svg'],this.svg,465,55,96,96);
      this.compass=mount(assets['hud/compass.svg'],this.svg,485,186,56,56);
      this.compassFocus=mount(assets['hints/focus-ring.svg'],this.svg,471,172,84,84);
      this.statusRoot=el('g',{},this.svg);
      this.statuses={};
      for(const name of ['boolean-true','boolean-false','error','completed','success'])
        this.statuses[name]=mount(assets['status/'+name+'.svg'],this.statusRoot,491,277,44,44);
      this.inputs={};
      for(const name of ['keyboard','pointer','clock'])
        this.inputs[name]=mount(assets['input/'+name+'.svg'],this.statusRoot,491,277,44,44);
      this.value=this.label('',513,344,16,'#21364B');
      this.note=this.label('SVG · live preview',513,378,10,'#537486');
      this.active=null;
      this.render('move.step',0,{});
    }
    label(text,x,y,size,fill) {
      const n=el('text',{x,y,'text-anchor':'middle','font-size':size,'font-family':'system-ui, sans-serif',fill},this.svg);n.textContent=text;return n;
    }
    setPart(name,t='',alpha=1) {
      const n=this.parts[name];if(!n) return;
      if(t) n.setAttribute('transform',t); else n.removeAttribute('transform');
      opacity(n,alpha);
    }
    badge(name,alpha=1,text='') {
      if(this.statuses[name]) opacity(this.statuses[name],alpha);
      this.value.textContent=text;opacity(this.value,alpha);
    }
    inputBadge(name,alpha=1,text='') {
      opacity(this.inputs[name],alpha);this.value.textContent=text;opacity(this.value,alpha);
    }
    render(key,progress,options={}) {
      if(!DATA[key]) throw new RangeError('Unknown clip '+key);
      const p=clamp(progress),q=smooth(p),n=options;
      const angle=DIR[n.direction||'north'];const head=DIR[n.heading||'north'];
      const dx=Math.sin(angle*Math.PI/180),dy=-Math.cos(angle*Math.PI/180);
      const reduced=!!n.reduced;
      this.world.removeAttribute('transform');opacity(this.world,1);opacity(this.actor,1);
      this.actor.setAttribute('transform','translate(152 152)');
      for(const name of Object.keys(this.parts)) this.setPart(name,this.base[name].transform,this.base[name].opacity);
      for(const name of ['gripper-base','gripper-left','gripper-right','roller','eraser','eyelids'])this.setPart(name,'',0);
      for(const name of ['drive','body','heading'])this.setPart(name,`rotate(${head} 64 64)`,1);
      opacity(this.parts.heading,n.policy==='absolute'?0:1);
      // Independent probe is stowed in a fixed upward presentation between calls.
      this.setPart('sensor','',1);
      for(const node of [this.armBack,this.armFront,this.claw,this.carried,this.edgePulseGroup,this.arrowGroup,this.focus,this.focusSmall,this.bagFocus,this.compassFocus])opacity(node,0);
      for(const node of [...Object.values(this.statuses),...Object.values(this.inputs)])opacity(node,0);
      this.value.textContent='';opacity(this.value,1);
      this.carried.setAttribute('x',0);this.carried.setAttribute('y',0);this.claw.removeAttribute('transform');
      this.armBack.removeAttribute('d');this.armFront.removeAttribute('d');
      for(const node of this.clawParts)opacity(node,1);
      this.inputs.clock.querySelector('[data-part="clock-hand"]').removeAttribute('transform');
      this.note.textContent=DATA[key].id+' · '+key;
      this.compass.querySelector('[data-part="compass-pointer"]').setAttribute('transform',`rotate(${angle} 32 32)`);
      this.wallGroup.setAttribute('transform',`rotate(${angle} 216 216)`);
      opacity(this.wallGroup,0);opacity(this.wall,1);opacity(this.edgeMark,0);
      this.edgePulseGroup.setAttribute('transform',`rotate(${angle} 216 216)`);
      this.arrowGroup.setAttribute('transform',`rotate(${angle} 216 216)`);
      this.focus.setAttribute('x',152);this.focus.setAttribute('y',152);
      opacity(this.target,n.target===false?0:1);
      let count=Number.isSafeInteger(n.count)?Math.max(0,n.count):2;
      let bag=n.bag==='infinite'?'infinite':(Number.isSafeInteger(n.bag)?Math.max(0,n.bag):1);
      let paint=!!n.painted;
      this.wipe.setAttribute('x',152);this.wipe.setAttribute('width',128);
      const event={clip:key,progress:p,cellCount:count,bagCount:bag,carried:0,painted:paint};
      const shown=phase(p,0,.22);
      const active=p>0&&p<1;
      const arm=(x,y,a=1)=>{
        const d=`M 91 83 Q 104 89 ${x} ${y}`;
        for(const node of [this.armBack,this.armFront]){node.setAttribute('d',d);opacity(node,a);}
        this.claw.setAttribute('transform',`translate(${x-109} ${y-107})`);opacity(this.claw,a);
        for(const node of this.clawParts)opacity(node,1);
      };
      switch(key) {
        case 'move.step': {
          const t=reduced?(p===1?1:0):q;
          this.actor.setAttribute('transform',`translate(${152+128*dx*t} ${152+128*dy*t})`);
          if(n.policy==='absolute')opacity(this.arrowGroup,active?1:0);
          opacity(this.focus,active?.45:0);
          break;
        }
        case 'turn': {
          const degrees=n.turn==='right'?90:n.turn==='around'?180:-90;
          const t=reduced?(p===1?1:0):q;
          for(const name of ['body','drive','heading'])this.setPart(name,`rotate(${head+degrees*t} 64 64)`,1);
          opacity(this.parts.heading,n.policy==='absolute'?0:1);
          break;
        }
        case 'crystal.transfer': {
          const putting=n.transfer==='put';
          if(putting&&bag!== 'infinite'&&bag===0)bag=1;
          if(!putting&&count===0)count=1;
          let picked=p>=.25, deposited=p>=.8;
          if(reduced){picked=p===1;deposited=p===1;}
          let t=phase(p,.25,.8);if(putting)t=1-t;
          const x=111+(64-111)*t,y=109+(92-109)*t-8*Math.sin(Math.PI*t);
          if(active)arm(x,y,reduced?0:1);
          if(picked&&!deposited){
            opacity(this.carried,1);this.carried.setAttribute('x',152+x-12);this.carried.setAttribute('y',152+y-12);
          }
          if(putting){if(picked&&bag!=='infinite')bag--;if(deposited)count++;}
          else {if(picked)count--;if(deposited&&bag!=='infinite')bag++;}
          event.carried=picked&&!deposited?1:0;
          if(!reduced)this.setPart('cargo-hatch',`rotate(${-14*pulse(p)} 64 84)`,1);
          opacity(this.bagFocus,active?.45:0);
          break;
        }
        case 'paint.apply': {
          const repeated=!!n.painted;
          let t=repeated?1:phase(p,.15,.85);if(reduced&&!repeated)t=p===1?1:0;
          paint=t>0;this.wipe.setAttribute('width',128*t);
          const x=28+78*phase(p,.15,.85);
          if(active&&!reduced)this.setPart('roller',`translate(${x-107} 0)`,1);
          event.paintCoverage=t;
          break;
        }
        case 'paint.erase': {
          const initiallyPainted=n.painted!==false;
          let t=phase(p,.15,.85);if(reduced)t=p===1?1:0;
          paint=initiallyPainted&&t<1;this.wipe.setAttribute('x',152+128*t);this.wipe.setAttribute('width',128*(1-t));
          const x=28+78*phase(p,.15,.85);
          if(active&&!reduced)this.setPart('eraser',`translate(${x-109} 0)`,1);
          event.paintCoverage=initiallyPainted?1-t:0;
          break;
        }
        case 'sense.edge': {
          const result=n.result!==false;
          opacity(this.wallGroup,1);opacity(this.wall,result?0:1);opacity(this.edgeMark,shown*.65);
          if(!reduced)this.setPart('sensor',`rotate(${(angle>180?angle-360:angle)*phase(p,0,.3)} 64 64)`,1);
          opacity(this.edgePulseGroup,active?1:0);
          this.badge(result?'boolean-true':'boolean-false',phase(p,.25,.5),result?'True':'False');
          event.result=result;break;
        }
        case 'sense.cell': {
          let result=n.result!==false;
          if(n.subject==='paint')paint=result;
          else if(n.subject!=='count')count=result?Math.max(1,count):0;
          const value=n.subject==='count'?String(count):(result?'True':'False');
          opacity(n.subject==='paint'?this.focus:this.focusSmall,shown);
          if(n.subject==='count') {this.value.textContent=value;opacity(this.value,shown);}
          else this.badge(result?'boolean-true':'boolean-false',shown,value);
          event.result=n.subject==='count'?count:result;break;
        }
        case 'sense.bag': {
          const result=n.subject==='count'?(bag==='infinite'?null:bag):bag===0;
          opacity(this.bagFocus,shown);
          const text=result===null?'None':typeof result==='boolean'?(result?'True':'False'):String(result);
          if(typeof result==='boolean')this.badge(result?'boolean-true':'boolean-false',shown,text);
          else {this.value.textContent=text;opacity(this.value,shown);}
          event.result=result;break;
        }
        case 'sense.heading': {
          const result=angle===head;
          opacity(this.compassFocus,shown);this.badge(result?'boolean-true':'boolean-false',shown,result?'True':'False');
          event.result=result;break;
        }
        case 'error.wall': {
          opacity(this.wallGroup,1);const t=reduced?0:8*pulse(p);
          this.actor.setAttribute('transform',`translate(${152+t*dx} ${152+t*dy})`);
          this.edgeMark.setAttribute('stroke','#C1664F');opacity(this.edgeMark,shown);
          this.badge('error',shown,'WALL_COLLISION');break;
        }
        case 'error.object': {
          const emptyBag=n.subject==='bag';if(emptyBag)bag=0;else count=0;
          if(active&&!reduced)arm(emptyBag?73:111,emptyBag?95:109,pulse(p));
          opacity(emptyBag?this.bagFocus:this.focusSmall,shown);
          this.badge('error',shown,emptyBag?'EMPTY_BAG':'NO_CRYSTAL');break;
        }
        case 'error.status':this.badge('error',shown,n.error||'COMMAND_UNAVAILABLE');break;
        case 'input.waiting': {
          const kind=n.input==='click'?'pointer':n.input==='time'?'clock':'keyboard';
          this.inputBadge(kind,1,kind==='keyboard'?'wait_key()':kind==='pointer'?'wait_click()':'wait()');
          this.inputs.clock.querySelector('[data-part="clock-hand"]').setAttribute('transform',`rotate(${360*p} 32 34)`);
          break;
        }
        case 'input.received': {
          const click=n.input==='click';this.inputBadge(click?'pointer':'keyboard',shown,click?'(1, 1)':n.key||'space');
          if(click)opacity(this.focus,shown);break;
        }
        case 'lifecycle': {
          const state=n.lifecycle||'completed';
          if(state==='ready'){opacity(this.actor,shown);this.value.textContent='Ready';}
          else this.badge('completed',shown,state==='cancelled'?'Stopped':'Completed');
          break;
        }
        case 'verdict': {
          const pass=n.result!==false;this.badge(pass?'success':'error',shown,pass?'Accepted':'Check target');
          if(!pass)opacity(this.focus,shown);break;
        }
        case 'view.reset':opacity(this.actor,reduced?1:Math.abs(2*p-1));paint=p<.5;break;
        case 'view.camera': {
          const t=reduced?(p===1?1:0):q;
          this.world.setAttribute('transform',`translate(${24*t} ${16*t}) translate(216 216) scale(${1-.16*t}) translate(-216 -216)`);break;
        }
        case 'focus.feedback':opacity(this.focus,reduced?(active?1:0):pulse(p));this.value.textContent=n.label||'Current cell';break;
        case 'idle.blink':if(!reduced)opacity(this.parts.eyelids,p>0&&p<1?pulse(p):0);break;
      }
      if(key!=='error.wall')this.edgeMark.setAttribute('stroke','#367FC1');
      opacity(this.paintGroup,paint?1:0);
      opacity(this.object,count>0?1:0);opacity(this.objectBadge,count>0?1:0);this.objectCount.textContent=count>0?String(count):'';
      this.objectCount.setAttribute('font-size',Math.max(7,Math.min(10,23/Math.max(1,String(count).length*.64))));
      this.value.setAttribute('font-size',Math.max(9,Math.min(16,148/Math.max(1,this.value.textContent.length*.63))));
      this.bagValue.textContent=bag==='infinite'?'∞':String(bag);
      opacity(this.bag.querySelector('[data-part="bag-contents"]'),bag===0?0:1);
      event.cellCount=count;event.bagCount=bag;event.painted=paint;
      this.last={key,progress:p,options:{...options},visual:event};
      return event;
    }
    play(key,options={}) {
      if(this.active)this.active.cancel();
      const data=DATA[key];if(!data)throw new RangeError('Unknown clip '+key);
      const speed=options.speed??1;if(!(speed>0))throw new RangeError('speed must be positive');
      let duration=data.duration;
      if(key==='turn'&&options.turn==='around')duration=360;
      if(key==='paint.apply'&&options.painted)duration=180;
      if(key==='paint.erase'&&options.painted===false)duration=180;
      if(key==='input.waiting'&&options.input==='time')duration=(options.waitSeconds??1)*1000;
      const waitsForInput=key==='input.waiting'&&options.input!=='time';
      let resolve,reject,raf=0,elapsed=0,previous=0,paused=false,done=false;
      const finished=new Promise((a,b)=>{resolve=a;reject=b;});
      const clean=()=>{cancelAnimationFrame(raf);if(options.signal)options.signal.removeEventListener('abort',cancel);if(this.active===ctl)this.active=null;};
      const finish=value=>{if(done)return;done=true;this.render(key,1,options);clean();resolve(value);};
      const cancel=()=>{if(done)return;done=true;this.render(key,0,options);clean();reject(new DOMException('Animation cancelled','AbortError'));};
      const tick=now=>{
        if(done||paused)return;
        if(previous)elapsed+=(now-previous)*speed;previous=now;
        const p=waitsForInput?0:clamp(elapsed/duration);
        this.render(key,p,options);if(options.onProgress)options.onProgress(p);
        if(p>=1)finish();else if(!waitsForInput)raf=requestAnimationFrame(tick);
      };
      const ctl={finished,cancel,pause:()=>{paused=true;cancelAnimationFrame(raf);},
        resume:()=>{if(!done&&paused){paused=false;previous=0;raf=requestAnimationFrame(tick);}},
        completeInput:value=>{if(waitsForInput&&!paused)finish(value);}};
      this.active=ctl;this.render(key,0,options);
      if(options.signal){options.signal.addEventListener('abort',cancel,{once:true});if(options.signal.aborted){cancel();return ctl;}}
      raf=requestAnimationFrame(tick);return ctl;
    }
    destroy(){if(this.active)this.active.cancel();this.container.replaceChildren();}
  }
  global.TlfRobotArt={Stage,mount,clips:C};
})(typeof window!=='undefined'?window:globalThis);
