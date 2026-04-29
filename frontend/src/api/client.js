/**
 * AOS API 客户端
 */
const BASE = '';

async function request(path, options = {}) {
  const { method = 'GET', body, params } = options;
  let url = `${BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null)
    );
    if (qs.toString()) url += `?${qs}`;
  }

  const fetchOptions = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) fetchOptions.body = JSON.stringify(body);

  const resp = await fetch(url, fetchOptions);
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`API ${resp.status}: ${err}`);
  }
  return resp.json();
}

// ── Chat ──
export const chatAPI = {
  send: (message, sessionId, agentName) =>
    request('/api/chat', {
      method: 'POST',
      body: { message, session_id: sessionId, agent_name: agentName },
    }),
  getSessions: (limit = 20) =>
    request('/api/chat/sessions', { params: { limit } }),
  getMessages: (sessionId) =>
    request(`/api/chat/sessions/${sessionId}/messages`),
  deleteSession: (sessionId) =>
    request(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' }),
};

// ── Knowledge ──
export const knowledgeAPI = {
  create: (doc) =>
    request('/api/knowledge', { method: 'POST', body: doc }),
  list: (params) =>
    request('/api/knowledge', { params }),
  get: (id) =>
    request(`/api/knowledge/${id}`),
  update: (id, doc) =>
    request(`/api/knowledge/${id}`, { method: 'PUT', body: doc }),
  delete: (id) =>
    request(`/api/knowledge/${id}`, { method: 'DELETE' }),
};

// ── Tasks ──
export const tasksAPI = {
  create: (task) =>
    request('/api/tasks', { method: 'POST', body: task }),
  list: (params) =>
    request('/api/tasks', { params }),
  update: (id, update) =>
    request(`/api/tasks/${id}`, { method: 'PUT', body: update }),
  delete: (id) =>
    request(`/api/tasks/${id}`, { method: 'DELETE' }),
};

// ── Agents ──
export const agentsAPI = {
  list: () => request('/api/agents'),
  switch: (agentName, sessionId) =>
    request('/api/agents/switch', {
      method: 'POST',
      body: { agent_name: agentName, session_id: sessionId },
    }),
};

// ── Memory ──
export const memoryAPI = {
  list: (params) => request('/api/memory', { params }),
  create: (mem) =>
    request('/api/memory', { method: 'POST', body: mem }),
};

// ── Export / Import ──
export const dataAPI = {
  export: (options) =>
    request('/api/data/export', { method: 'POST', body: options }),
};

// ── System ──
export const systemAPI = {
  health: () => request('/health'),
  info: () => request('/api/system'),
};
