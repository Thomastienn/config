async function send(action) {
  const tab = await chrome.tabs.getCurrent();
  const reply = await chrome.runtime.sendMessage({action, tabId: tab.id});
  if (reply?.error) document.querySelector('#status').textContent = reply.error;
  return reply;
}
async function render() {
  const data = await send('view');
  document.querySelector('#heading').textContent = data.active ? 'Back to your task.' : 'Ready for a small step.';
  document.querySelector('#task').textContent = data.task || 'Start a session from Focus Garden.';
  document.querySelector('#resource').textContent = data.title || '';
  document.querySelector('#status').textContent = data.error || data.message || (data.active ? 'This page is outside your chosen work.'
    : data.connected ? 'Connected to Focus Garden. Start a desktop session and choose your work pages to enable blocking.'
    : 'Desktop connection unavailable. Run setup and click the Lock In toolbar icon to reconnect.');
  document.querySelector('#request').disabled = !data.active || !/^https?:/.test(data.url || '');
  document.querySelector('#back').disabled = !data.active;
  document.querySelector('#end').hidden = !data.active;
}
document.querySelector('#back').onclick = () => send('back');
document.querySelector('#request').onclick = async () => { await send('request'); document.querySelector('#status').textContent = 'Explain the task connection in the desktop prompt. Review runs during the 10-second wait. Alt+Escape ends immediately.'; };
document.querySelector('#end').onclick = () => send('end');
chrome.runtime.onMessage.addListener(message => { if (message.action === 'refresh') render(); });
render();
