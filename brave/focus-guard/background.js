import {canonical, allowed, rules} from './policy.js';

const gateURL = chrome.runtime.getURL('gate.html');
let port, state = null, chain = Promise.resolve(), connectionError = '';
const pending = new Map(), gates = new Map();
let activity = {allowed: false, title: '', gate: false};

function enqueue(work) {
  const result = chain.then(work);
  chain = result.catch(() => {});
  return result;
}
function emit(data) { try { port?.postMessage(data); } catch {} }
async function persist() { await chrome.storage.session.set({focus: state}); }
async function refresh() { await chrome.runtime.sendMessage({action: 'refresh'}).catch(() => {}); }

async function restoreMute(tab) {
  if ((!state || state.muted[String(tab.id)] === false) && tab.mutedInfo?.reason === 'extension' && tab.mutedInfo.extensionId === chrome.runtime.id) {
    await chrome.tabs.update(tab.id, {muted: false}).catch(() => {});
  }
  if (state) delete state.muted[String(tab.id)];
}

async function updateRules() {
  const existing = await chrome.declarativeNetRequest.getSessionRules();
  await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: existing.map(rule => rule.id), addRules: state ? rules(state) : []});
}

async function stop(notify = false) {
  const session = state?.session;
  // Clear access restrictions first, even if the native host has stopped responding.
  const existing = await chrome.declarativeNetRequest.getSessionRules();
  await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: existing.map(rule => rule.id)});
  await chrome.alarms.clear('focus-expiry');
  await chrome.alarms.clear('focus-approval');
  for (const tab of await chrome.tabs.query({})) await restoreMute(tab);
  state = null;
  pending.clear();
  await persist();
  const ownTabs = await chrome.tabs.query({url: gateURL});
  await chrome.tabs.remove(ownTabs.map(tab => tab.id)).catch(() => {});
  gates.clear();
  await chrome.action.setBadgeText({text: ''});
  if (notify && session) emit({event: 'emergency', session});
  await refresh();
}

async function syncMute(tab) {
  if (!state || tab.url === gateURL) return;
  if (allowed(state, tab.url)) {
    await restoreMute(tab);
  } else if (!tab.mutedInfo?.muted) {
    state.muted[String(tab.id)] = false;
    await chrome.tabs.update(tab.id, {muted: true}).catch(() => {});
  }
}

async function muteUnapproved() {
  for (const tab of await chrome.tabs.query({})) await syncMute(tab);
  await persist();
}

async function gate(tab, attempted) {
  if (!state || tab.url === gateURL) return;
  tab = await chrome.tabs.get(tab.id).catch(() => null);
  if (!tab?.active || (!attempted && !tab.url)) return;
  pending.set(tab.windowId, {tabId: tab.id, url: attempted || tab.url,
    title: attempted && attempted !== tab.url ? 'New page (not loaded yet)' : tab.title || 'Unapproved page'});
  let gateTab;
  const id = gates.get(tab.windowId);
  if (id !== undefined) gateTab = await chrome.tabs.get(id).catch(() => null);
  if (!gateTab || gateTab.url !== gateURL) {
    gateTab = await chrome.tabs.create({windowId: tab.windowId, url: gateURL, active: true});
    gates.set(tab.windowId, gateTab.id);
  } else await chrome.tabs.update(gateTab.id, {active: true});
  await refresh();
}

async function report() {
  if (!state) return;
  const win = await chrome.windows.getLastFocused({populate: true}).catch(() => null);
  const tab = win?.tabs?.find(tab => tab.active);
  activity = {allowed: !!tab && allowed(state, tab.url), title: tab?.title || '', gate: tab?.url === gateURL};
  emit({event: 'activity', session: state.session, ...activity});
}

async function inspect(tab, attempted) {
  if (!state || tab.incognito || tab.url === gateURL) { await report(); return; }
  if ((attempted || tab.url) === 'about:blank' || (!attempted && !tab.url)) return;
  if (!allowed(state, attempted || tab.url)) {
    if (tab.active) await gate(tab, attempted);
  }
  await syncMute(tab);
  await persist();
  await report();
}

async function scheduleApprovalExpiry() {
  const times = Object.values(state.temporary).filter(until => until > Date.now());
  await chrome.alarms.clear('focus-approval');
  if (times.length) await chrome.alarms.create('focus-approval', {when: Math.min(...times)});
}

async function command(message) {
  switch (message.op) {
    case 'snapshot':
      return {tabs: (await chrome.tabs.query({})).filter(tab => !tab.incognito && /^https?:/.test(tab.url || '')).map(tab => ({id: tab.id, title: tab.title || 'Work page', url: tab.url})), paired: true};
    case 'status':
      await report();
      return {session: state?.session || null, ...activity};
    case 'start': {
      if (typeof message.session !== 'string' || !Array.isArray(message.pages) || !Number.isFinite(message.ends_at) || message.ends_at <= Date.now()) throw new Error('Invalid session');
      const pages = [...new Set(message.pages.map(canonical))];
      if (pages.length > 300) throw new Error('Choose at most 300 work pages');
      if (state) throw new Error('A browser focus session is already running');
      state = {session: message.session, task: String(message.task || '').slice(0, 300), pages, temporary: {}, muted: {}, ends_at: message.ends_at, message: ''};
      try {
        await updateRules();
        await chrome.alarms.create('focus-expiry', {when: state.ends_at});
        await muteUnapproved();
        await chrome.action.setBadgeText({text: 'ON'});
        await chrome.action.setBadgeBackgroundColor({color: '#607b65'});
        for (const tab of await chrome.tabs.query({active: true})) await inspect(tab);
        await persist();
      } catch (error) { await stop(); throw error; }
      return {session: state.session};
    }
    case 'approve': {
      if (message.session !== state?.session) throw new Error('Stale session');
      const url = canonical(message.url);
      state.temporary[url] = Math.min(Date.now() + 300000, state.ends_at);
      await updateRules();
      await scheduleApprovalExpiry();
      await muteUnapproved();
      for (const [windowId, resource] of pending) {
        if (allowed({pages: [url], temporary: {}}, resource.url)) {
          const tab = await chrome.tabs.get(resource.tabId).catch(() => null);
          // Retrying a blocked GET is explicit; never replay an existing form submission.
          if (tab && allowed(state, tab.url)) await chrome.tabs.update(tab.id, {active: true});
          else await chrome.tabs.create({windowId, url, active: true});
          pending.delete(windowId);
        }
      }
      state.message = '';
      await persist();
      await refresh();
      return {};
    }
    case 'ui':
      if (message.session !== state?.session) throw new Error('Stale session');
      state.message = String(message.message || '').slice(0, 300);
      await persist();
      await refresh();
      return {};
    case 'stop':
      if (state && message.session !== state.session) throw new Error('Stale session');
      await stop();
      return {};
    default: throw new Error('Unknown browser operation');
  }
}

function connect() {
  if (port) return;
  connectionError = '';
  port = chrome.runtime.connectNative('org.thomas.focus');
  port.onMessage.addListener(message => enqueue(async () => {
    try { const result = await command(message); emit({id: message.id, ok: true, ...result}); }
    catch (error) { emit({id: message.id, ok: false, error: error.message}); }
  }));
  port.onDisconnect.addListener(() => {
    connectionError = chrome.runtime.lastError?.message || 'Desktop connection closed. Click the Lock In toolbar icon to reconnect.';
    port = null;
    enqueue(() => stop()).catch(() => {});
  });
}

chrome.webNavigation.onBeforeNavigate.addListener(details => {
  if (details.frameId !== 0 || !state || allowed(state, details.url) || details.url === gateURL) return;
  enqueue(async () => { const tab = await chrome.tabs.get(details.tabId).catch(() => null); if (tab) await inspect(tab, details.url); });
});
for (const event of [chrome.webNavigation.onHistoryStateUpdated, chrome.webNavigation.onReferenceFragmentUpdated]) {
  event.addListener(details => {
    if (details.frameId === 0) enqueue(async () => { const tab = await chrome.tabs.get(details.tabId).catch(() => null); if (tab) await inspect(tab); });
  });
}
chrome.tabs.onActivated.addListener(({tabId}) => enqueue(async () => { const tab = await chrome.tabs.get(tabId).catch(() => null); if (tab) await inspect(tab); }));
chrome.tabs.onUpdated.addListener((tabId, changes, tab) => {
  if (changes.url || changes.title || changes.status === 'complete') enqueue(async () => {
    // Queued snapshots may still say a tab is active after its approval gate opened.
    const current = await chrome.tabs.get(tabId).catch(() => null);
    if (current?.url) await inspect(current);
  });
});
chrome.tabs.onRemoved.addListener(tabId => {
  for (const [windowId, id] of gates) if (id === tabId) gates.delete(windowId);
});
chrome.windows.onFocusChanged.addListener(() => enqueue(report));
chrome.alarms.onAlarm.addListener(alarm => enqueue(async () => {
  if (!state) return;
  if (alarm.name === 'focus-expiry') { const session = state.session; await stop(); emit({event: 'expired', session}); }
  if (alarm.name === 'focus-approval') {
    for (const [url, until] of Object.entries(state.temporary)) if (until <= Date.now()) delete state.temporary[url];
    await updateRules();
    await scheduleApprovalExpiry();
    await muteUnapproved();
    for (const tab of await chrome.tabs.query({active: true})) await inspect(tab);
  }
}));
chrome.action.onClicked.addListener(tab => { connect(); enqueue(async () => { if (state) await gate(tab); else await chrome.tabs.create({url: gateURL}); }); });
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id || sender.url !== gateURL) return;
  enqueue(async () => {
    const source = sender.tab || await chrome.tabs.get(message.tabId).catch(() => null);
    if (source?.url !== gateURL) throw new Error('Invalid approval page');
    const win = source.windowId;
    const resource = pending.get(win);
    switch (message.action) {
      case 'view': return {active: !!state, connected: !!port, error: connectionError, task: state?.task, message: state?.message, title: resource?.title, url: resource?.url};
      case 'request':
        if (state && resource && /^https?:/.test(resource.url || '')) emit({event: 'approval', session: state.session, ...resource});
        return {};
      case 'end': await stop(true); return {};
      case 'back': {
        const work = (await chrome.tabs.query({windowId: win})).find(tab => state && allowed(state, tab.url));
        if (work) await chrome.tabs.update(work.id, {active: true});
        return {};
      }
      default: return {};
    }
  }).then(reply, error => reply({error: error.message}));
  return true;
});

enqueue(async () => {
  state = (await chrome.storage.session.get('focus')).focus || null;
  // A worker restart breaks the guard's connection; finish instead of resuming unacknowledged rules.
  await stop();
  connect();
}).catch(() => {});
