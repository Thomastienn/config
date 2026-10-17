export function canonical(raw) {
  const url = new URL(raw);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Use an HTTP(S) work page');
  if (!/^#!?\//.test(url.hash)) url.hash = '';
  return url.href;
}

export function allowed(state, raw, now = Date.now()) {
  try {
    const url = canonical(raw);
    return state.pages.includes(url) || (state.temporary[url] || 0) > now;
  } catch { return false; }
}

export function rules(state, now = Date.now()) {
  const urls = [...new Set([...state.pages, ...Object.keys(state.temporary).filter(url => state.temporary[url] > now)])];
  const result = [{id: 1, priority: 1, action: {type: 'block'}, condition: {regexFilter: '^https?://', resourceTypes: ['main_frame']}}];
  urls.forEach((url, index) => {
    // Network requests omit fragments; SPA events enforce hash routes separately.
    const base = url.split('#')[0].replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result.push({id: index + 2, priority: 2, action: {type: 'allow'}, condition: {regexFilter: '^' + base + '$', resourceTypes: ['main_frame']}});
  });
  return result;
}
