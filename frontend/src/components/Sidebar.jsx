/**
 * 侧边栏 — 导航 + 会话列表
 */
import useStore from '../stores/appStore';

const NAV_ITEMS = [
  { key: 'chat', icon: '💬', label: '对话' },
  { key: 'dashboard', icon: '📊', label: '仪表盘' },
  { key: 'knowledge', icon: '📚', label: '知识库' },
  { key: 'tasks', icon: '✅', label: '任务' },
];

export default function Sidebar() {
  const {
    currentView, setView, sessions, currentSession,
    selectSession, newChat, tasks,
  } = useStore();

  const todoCount = tasks.filter(
    (t) => t.task_status === 'todo' || t.task_status === 'in_progress'
  ).length;

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">奥</div>
          <div>
            <div className="sidebar-logo-text">AOS 奥思</div>
            <div className="sidebar-logo-sub">Enterprise AI Assistant</div>
          </div>
        </div>
      </div>

      {/* New Chat */}
      <button className="btn-new-chat" onClick={newChat}>
        <span>＋</span> 新对话
      </button>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="nav-section">
          <div className="nav-section-title">功能</div>
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className={`nav-item ${currentView === item.key ? 'active' : ''}`}
              onClick={() => setView(item.key)}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span>{item.label}</span>
              {item.key === 'tasks' && todoCount > 0 && (
                <span className="nav-item-badge">{todoCount}</span>
              )}
            </button>
          ))}
        </div>

        {/* Sessions */}
        <div className="nav-section">
          <div className="nav-section-title">最近对话</div>
          <div className="session-list">
            {sessions.slice(0, 15).map((s) => (
              <div
                key={s.id}
                className={`session-item ${currentSession === s.id ? 'active' : ''}`}
                onClick={() => {
                  selectSession(s.id);
                  setView('chat');
                }}
                title={s.title}
              >
                {s.title || '新对话'}
              </div>
            ))}
            {sessions.length === 0 && (
              <div className="session-item" style={{ color: 'var(--text-muted)', cursor: 'default' }}>
                暂无对话记录
              </div>
            )}
          </div>
        </div>
      </nav>
    </aside>
  );
}
