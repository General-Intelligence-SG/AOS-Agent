/**
 * AOS 全局状态管理 (Zustand)
 */
import { create } from 'zustand';
import { chatAPI, agentsAPI, knowledgeAPI, tasksAPI } from '../api/client';

const useStore = create((set, get) => ({
  // ── 导航 ──
  currentView: 'chat',   // chat | dashboard | knowledge | tasks | files
  setView: (view) => set({ currentView: view }),

  // ── Agent ──
  agents: [],
  currentAgent: 'architect',
  loadAgents: async () => {
    try {
      const agents = await agentsAPI.list();
      set({ agents });
    } catch (e) {
      console.error('Load agents failed:', e);
    }
  },
  switchAgent: async (name) => {
    const { currentSession } = get();
    set({ currentAgent: name });
    if (currentSession) {
      await agentsAPI.switch(name, currentSession);
    }
  },

  // ── Chat ──
  sessions: [],
  currentSession: null,
  messages: [],
  isLoading: false,

  loadSessions: async () => {
    try {
      const sessions = await chatAPI.getSessions();
      set({ sessions });
    } catch (e) {
      console.error('Load sessions failed:', e);
    }
  },

  selectSession: async (sessionId) => {
    set({ currentSession: sessionId, isLoading: true });
    try {
      const messages = await chatAPI.getMessages(sessionId);
      set({ messages, isLoading: false });
      // 更新当前 agent
      const { sessions } = get();
      const session = sessions.find((s) => s.id === sessionId);
      if (session) set({ currentAgent: session.current_agent });
    } catch (e) {
      set({ isLoading: false });
      console.error('Load messages failed:', e);
    }
  },

  newChat: () => {
    set({ currentSession: null, messages: [], currentView: 'chat' });
  },

  sendMessage: async (text) => {
    const { currentSession, currentAgent, messages } = get();

    // 立即添加用户消息
    const userMsg = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    set({ messages: [...messages, userMsg], isLoading: true });

    try {
      const resp = await chatAPI.send(text, currentSession, currentAgent);

      const assistantMsg = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: resp.reply,
        agent_name: resp.agent,
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        messages: [...state.messages, assistantMsg],
        isLoading: false,
        currentSession: resp.session_id,
        currentAgent: resp.agent,
      }));

      // 刷新会话列表
      get().loadSessions();

      return resp;
    } catch (e) {
      const errMsg = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `⚠️ 请求失败: ${e.message}\n\n请检查后端服务是否运行以及 LLM API Key 是否配置。`,
        agent_name: 'system',
        created_at: new Date().toISOString(),
      };
      set((state) => ({
        messages: [...state.messages, errMsg],
        isLoading: false,
      }));
    }
  },

  // ── Knowledge ──
  documents: [],
  loadDocuments: async () => {
    try {
      const docs = await knowledgeAPI.list({ limit: 50 });
      set({ documents: docs });
    } catch (e) {
      console.error('Load docs failed:', e);
    }
  },

  createDocument: async (doc) => {
    try {
      await knowledgeAPI.create(doc);
      get().loadDocuments();
    } catch (e) {
      console.error('Create doc failed:', e);
    }
  },

  // ── Tasks ──
  tasks: [],
  loadTasks: async () => {
    try {
      const tasks = await tasksAPI.list({ limit: 50 });
      set({ tasks });
    } catch (e) {
      console.error('Load tasks failed:', e);
    }
  },

  createTask: async (task) => {
    try {
      await tasksAPI.create(task);
      get().loadTasks();
    } catch (e) {
      console.error('Create task failed:', e);
    }
  },

  updateTask: async (id, update) => {
    try {
      await tasksAPI.update(id, update);
      get().loadTasks();
    } catch (e) {
      console.error('Update task failed:', e);
    }
  },
}));

export default useStore;
