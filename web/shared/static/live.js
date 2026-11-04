// Live updates from the FreshFlow API WebSocket.
// Usage: FF.live({api, token, channels:[...], on:(evt)=>{}})
window.FF = (function () {
  function toast(title, body) {
    let host = document.querySelector('.toast-host');
    if (!host) { host = document.createElement('div'); host.className = 'toast-host'; document.body.appendChild(host); }
    const t = document.createElement('div'); t.className = 'toast';
    t.innerHTML = '<b></b><span></span>'; t.querySelector('b').textContent = title; t.querySelector('span').textContent = body || '';
    host.appendChild(t); setTimeout(() => t.remove(), 6000);
  }
  function live(opts) {
    if (!opts.token) return;
    const url = opts.api.replace(/^http/, 'ws') + '/ws?token=' + encodeURIComponent(opts.token) +
      '&channels=' + encodeURIComponent((opts.channels || []).join(','));
    const dot = document.querySelector('.live-dot');
    let retry = 1000;
    (function connect() {
      const ws = new WebSocket(url);
      ws.onopen = () => { retry = 1000; dot && dot.classList.add('on'); };
      ws.onclose = () => { dot && dot.classList.remove('on'); setTimeout(connect, retry = Math.min(retry * 2, 15000)); };
      ws.onmessage = (m) => {
        if (m.data === 'pong') return;
        const evt = JSON.parse(m.data);
        if (evt.event === 'notification') toast(evt.data.title, evt.data.body);
        opts.on && opts.on(evt);
      };
      setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000);
    })();
  }
  return { live, toast };
})();
