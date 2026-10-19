/* Яндекс.Метрика 113668938: загрузка только после отдельного согласия. */
(function () {
  'use strict';
  if (window.rustamovaAnalyticsConsent) return;
  var COUNTER = 113668938;
  var VERSION = '2026-10-18-webvisor';
  var KEY = 'rustamova_analytics_consent_v1';
  var LIFETIME = 180 * 24 * 60 * 60 * 1000;
  var started = false;
  var choice = readChoice();
  var panel;

  function readChoice() {
    try {
      var value = JSON.parse(window.localStorage.getItem(KEY));
      if (value && value.version === VERSION &&
          (value.choice === 'accepted' || value.choice === 'rejected') &&
          typeof value.time === 'number' && value.time <= Date.now() &&
          Date.now() - value.time < LIFETIME) return value.choice;
    } catch (_) { /* Без хранилища решение действует на текущей странице. */ }
    return null;
  }

  function pageUrl(value) {
    try {
      var url = new URL(value);
      return /^https?:$/.test(url.protocol) ? url.origin + url.pathname : '';
    } catch (_) { return ''; }
  }

  function start() {
    if (started || choice !== 'accepted') return;
    started = true;
    // Официальный загрузчик Яндекса выполняется только после согласия.
    (function(m,e,t,r,i,k,a){
      m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
      m[i].l=1*new Date();
      for (var j=0;j<document.scripts.length;j++) {if(document.scripts[j].src===r) return;}
      k=e.createElement(t);a=e.getElementsByTagName(t)[0];k.async=1;k.src=r;
      k.id='rustamova-metrika-tag';a.parentNode.insertBefore(k,a);
    })(window,document,'script','https://mc.yandex.ru/metrika/tag.js?id=113668938','ym');
    window.ym(COUNTER,'init',{
      ssr:true,clickmap:true,webvisor:true,trackLinks:true,accurateTrackBounce:true,
      referrer:pageUrl(document.referrer),url:pageUrl(window.location.href)
    });
  }

  function removeMetrikaStorage() {
    var domains = ['', window.location.hostname, '.' + window.location.hostname];
    var paths = ['/'];
    var parts = window.location.pathname.split('/');
    for (var p=1;p<parts.length;p++) paths.push(parts.slice(0,p+1).join('/') || '/');
    document.cookie.split(';').forEach(function (cookie) {
      var name = cookie.trim().split('=')[0];
      if (!/^_ym/.test(name)) return;
      domains.forEach(function (domain) {
        paths.forEach(function (path) {
          document.cookie = name + '=; Max-Age=0; path=' + path +
            (domain ? '; domain=' + domain : '') + '; SameSite=Lax';
        });
      });
    });
    ['localStorage', 'sessionStorage'].forEach(function (storageName) {
      try {
        var storage = window[storageName];
        Object.keys(storage).forEach(function (name) {
          if (/^_ym/.test(name)) storage.removeItem(name);
        });
      } catch (_) { /* Хранилище может быть отключено браузером. */ }
    });
  }

  function stop() {
    if (started && typeof window.ym === 'function') {
      // Не оставляем отложенный init, если отказ дан до загрузки tag.js.
      if (Array.isArray(window.ym.a)) window.ym.a.length = 0;
      window.ym(COUNTER,'destruct');
    }
    started = false;
    removeMetrikaStorage();
  }

  function choose(value) {
    choice = value;
    try {
      window.localStorage.setItem(KEY,JSON.stringify({choice:value,time:Date.now(),version:VERSION}));
    } catch (_) { /* Работа сайта не зависит от доступа к localStorage. */ }
    if (value === 'accepted') start(); else stop();
    panel.hidden = true;
    document.querySelectorAll('[data-analytics-status]').forEach(function (node) {
      node.textContent = value === 'accepted' ? 'Аналитика и Вебвизор включены.' : 'Аналитика и Вебвизор выключены.';
    });
  }

  function show() {
    panel.hidden = false;
    panel.querySelector('[data-analytics-reject]').focus();
  }

  function init() {
    panel = document.createElement('section');
    panel.className = 'analytics-consent ym-hide-content';
    panel.setAttribute('role','region');
    panel.setAttribute('aria-label','Настройки аналитики и Вебвизора');
    panel.innerHTML = '<p><strong>Аналитика сайта и Вебвизор</strong></p>' +
      '<p>Яндекс Метрика использует cookie и записывает действия на страницах: клики, прокрутку и движения указателя. Нажимая «Разрешить», вы даёте <a href="/analytics-consent.html">отдельное согласие</a> на такую обработку данных. <a href="/privacy-policy.html#analytics">Политика обработки данных</a>.</p>' +
      '<div class="analytics-consent__actions"><button type="button" data-analytics-accept>Разрешить</button>' +
      '<button type="button" data-analytics-reject>Без аналитики</button></div>';
    panel.hidden = choice !== null;
    document.body.appendChild(panel);
    panel.querySelector('[data-analytics-accept]').addEventListener('click',function(){choose('accepted');});
    panel.querySelector('[data-analytics-reject]').addEventListener('click',function(){choose('rejected');});
    document.addEventListener('click',function(event){
      var target = event.target;
      if (!target || typeof target.closest !== 'function') return;
      if (target.closest('[data-analytics-settings]')) { event.preventDefault(); show(); return; }
      if (choice !== 'accepted' || !started || typeof window.ym !== 'function') return;
      var link = target.closest('a[href]');
      if (!link) return;
      if (/^tel:/i.test(link.getAttribute('href'))) window.ym(COUNTER,'reachGoal','contact_phone');
      else if (/^https:\/\/(www\.)?max\.ru\//i.test(link.href)) window.ym(COUNTER,'reachGoal','contact_max');
    });
    // Отзыв в другой вкладке останавливает сбор и в уже открытой странице.
    window.addEventListener('storage',function(event){
      if (event.key !== KEY && event.key !== null) return;
      choice = readChoice();
      if (choice === 'accepted') start(); else stop();
      panel.hidden = choice !== null;
    });
    if (choice === 'accepted') start();
    document.querySelectorAll('[data-analytics-status]').forEach(function(node){
      node.textContent = choice === 'accepted' ? 'Аналитика и Вебвизор включены.' : 'Аналитика и Вебвизор выключены.';
    });
  }
  window.rustamovaAnalyticsConsent = {open:show};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
