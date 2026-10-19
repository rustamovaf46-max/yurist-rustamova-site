const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname,'../analytics-consent.js'),'utf8');
const KEY = 'rustamova_analytics_consent_v1';
const valid = choice => JSON.stringify({choice,version:'2026-10-18-webvisor',time:Date.now()});

function page(saved,blocked=false) {
  const data = saved === undefined ? {} : {[KEY]:saved};
  const storage = new Proxy(data,{get(object,key){
    if(key==='getItem') return name => object[name] ?? null;
    if(key==='setItem') return (name,value) => {object[name]=value;};
    if(key==='removeItem') return name => {delete object[name];};
    return object[key];
  }});
  const listeners = {}, windowListeners = {}, cookies = new Map([['_ym_uid','visitor']]);
  function element() {
    return {hidden:false,attrs:{},events:{},setAttribute(k,v){this.attrs[k]=v;},
      addEventListener(k,fn){this.events[k]=fn;},focus(){},
      querySelector(s){return s.includes('accept')?accept:reject;}};
  }
  const accept=element(),reject=element(),status=element(),panels=[];
  const bootstrap={src:'/analytics-consent.js',parentNode:{insertBefore(script){document.scripts.push(script);}}};
  const document={readyState:'complete',referrer:'https://example.org/path?private=secret',
    scripts:[bootstrap],body:{appendChild(node){panels.push(node);}},
    createElement:element,getElementsByTagName:()=>[bootstrap],
    addEventListener(name,handler){listeners[name]=handler;},
    querySelectorAll(selector){return selector==='[data-analytics-status]'?[status]:[];}};
  Object.defineProperty(document,'cookie',{get:()=>Array.from(cookies,([k,v])=>`${k}=${v}`).join('; '),
    set(value){const name=value.split('=')[0];if(value.includes('Max-Age=0'))cookies.delete(name);}});
  const window={location:{href:'https://site.example/article.html?private=secret#private',hostname:'site.example',pathname:'/article.html'},
    addEventListener(name,handler){windowListeners[name]=handler;}};
  for(const name of ['localStorage','sessionStorage']) Object.defineProperty(window,name,{get(){
    if(blocked)throw Error('Storage blocked');return storage;
  }});
  const context={window,document,URL,Date,console};
  vm.runInNewContext(code,context);
  return {window,document,data,panels,status,cookies,
    accept:()=>accept.events.click(),reject:()=>reject.events.click(),
    clickLink(href){const link={href,getAttribute:()=>href};listeners.click({target:{closest(selector){
      return selector==='a[href]'?link:null;
    }}});},storageEvent:()=>windowListeners.storage({key:KEY}),
    calls:()=>window.ym?Array.from(window.ym.a||[],x=>Array.from(x)):[]};
}

test('До согласия внешний скрипт не загружается и ym не создаётся',()=>{
  const p=page();assert.equal(p.document.scripts.length,1);assert.equal(p.window.ym,undefined);
  assert.equal(p.panels[0].hidden,false);p.clickLink('tel:+79099282398');assert.equal(p.window.ym,undefined);
});
test('Отказ сохраняется; повторный визит не запускает аналитику',()=>{
  const p=page();p.reject();assert.equal(JSON.parse(p.data[KEY]).choice,'rejected');
  const again=page(p.data[KEY]);assert.equal(again.window.ym,undefined);assert.equal(again.panels[0].hidden,true);
});
test('Разрешение загружает счётчик с Вебвизором один раз',()=>{
  const p=page();p.accept();p.accept();assert.equal(p.document.scripts.length,2);
  const init=p.calls().filter(x=>x[1]==='init');assert.equal(init.length,1);assert.equal(init[0][0],113668938);
  assert.equal(init[0][2].webvisor,true);assert.equal(init[0][2].url,'https://site.example/article.html');
  assert.equal(init[0][2].referrer,'https://example.org/path');
});
test('Действующее согласие включает Вебвизор при следующем посещении',()=>{
  const p=page(valid('accepted'));assert.equal(p.document.scripts.length,2);assert.equal(p.panels[0].hidden,true);
});
test('Отзыв до загрузки tag.js удаляет отложенный init и идентификаторы',()=>{
  const p=page();p.accept();p.reject();assert.equal(p.calls().filter(x=>x[1]==='init').length,0);
  assert.equal(p.calls()[0][1],'destruct');assert.equal(p.cookies.has('_ym_uid'),false);
  assert.equal(JSON.parse(p.data[KEY]).choice,'rejected');p.clickLink('tel:+79099282398');
  assert.equal(p.calls().filter(x=>x[1]==='reachGoal').length,0);
});
test('Истёкшее, повреждённое или чужое согласие не разрешает сбор',()=>{
  for(const raw of ['bad',JSON.stringify({choice:'accepted',time:0,version:'2026-10-18-webvisor'}),
      JSON.stringify({choice:'accepted',time:Date.now(),version:'old'})]) {
    const p=page(raw);assert.equal(p.window.ym,undefined);assert.equal(p.panels[0].hidden,false);
  }
});
test('Блокировка хранилища браузером не мешает принять или отклонить выбор',()=>{
  const p=page(undefined,true);assert.doesNotThrow(()=>p.reject());assert.doesNotThrow(()=>p.accept());
  assert.doesNotThrow(()=>p.reject());assert.equal(p.cookies.has('_ym_uid'),false);
});
test('Контактные события передаются только после согласия',()=>{
  const p=page();p.accept();p.clickLink('tel:+79099282398');p.clickLink('https://max.ru/u/public-contact');
  assert.deepEqual(p.calls().filter(x=>x[1]==='reachGoal').map(x=>x[2]),['contact_phone','contact_max']);
});
test('Отзыв в другой вкладке останавливает открытый счётчик',()=>{
  const p=page(valid('accepted'));p.data[KEY]=valid('rejected');p.storageEvent();
  assert.equal(p.calls().at(-1)[1],'destruct');assert.equal(p.cookies.size,0);
});
