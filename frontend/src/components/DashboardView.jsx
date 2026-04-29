/**
 * 仪表盘视图
 */
import { useEffect } from 'react';
import useStore from '../stores/appStore';

export default function DashboardView() {
  const {
    agents, tasks, documents, sessions,
    loadTasks, loadDocuments, setView, switchAgent,
  } = useStore();

  useEffect(() => {
    loadTasks();
    loadDocuments();
  }, []);

  const todoCount = tasks.filter((t) => t.task_status === 'todo').length;
  const inProgressCount = tasks.filter((t) => t.task_status === 'in_progress').length;
  const doneCount = tasks.filter((t) => t.task_status === 'done').length;

  const stats = [
    {
      icon: '💬', label: '总对话', value: sessions.length,
      color: 'rgba(99, 102, 241, 0.15)',
    },
    {
      icon: '📋', label: '待办任务', value: todoCount,
      color: 'rgba(245, 158, 11, 0.15)',
    },
    {
      icon: '🔄', label: '进行中', value: inProgressCount,
      color: 'rgba(6, 182, 212, 0.15)',
    },
    {
      icon: '✅', label: '已完成', value: doneCount,
      color: 'rgba(16, 185, 129, 0.15)',
    },
    {
      icon: '📚', label: '知识库', value: documents.length,
      color: 'rgba(168, 85, 247, 0.15)',
    },
    {
      icon: '🤖', label: '活跃 Agent', value: agents.filter((a) => a.is_active).length,
      color: 'rgba(99, 102, 241, 0.15)',
    },
  ];

  return (
    <div className="dashboard">
      <h2>📊 今日概览</h2>

      {/* Stats Grid */}
      <div className="dashboard-grid">
        {stats.map((s, i) => (
          <div key={i} className="dashboard-card">
            <div className="dashboard-card-header">
              <div
                className="dashboard-card-icon"
                style={{ background: s.color }}
              >
                {s.icon}
              </div>
              <div>
                <div className="dashboard-card-title">{s.label}</div>
              </div>
            </div>
            <div className="dashboard-card-value">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Agent Overview */}
      <h2 style={{ marginTop: '32px' }}>🤖 Agent 团队</h2>
      <div className="agent-grid">
        {agents.map((a) => (
          <div
            key={a.name}
            className="agent-card"
            onClick={() => {
              switchAgent(a.name);
              setView('chat');
            }}
          >
            <div className="agent-card-emoji">{a.avatar_emoji}</div>
            <div className="agent-card-name">{a.display_name}</div>
            <div className="agent-card-role">{a.role_type.replace('_', ' ')}</div>
            <div className="agent-card-desc">{a.description}</div>
          </div>
        ))}
      </div>

      {/* Recent Tasks */}
      {tasks.length > 0 && (
        <>
          <h2 style={{ marginTop: '32px' }}>📋 近期任务</h2>
          <div className="item-list">
            {tasks.slice(0, 5).map((t) => (
              <div key={t.id} className={`item-card priority-${t.priority}`}>
                <div className="item-card-title">
                  <span className={`status-${t.task_status}`}>
                    {t.task_status === 'done' ? '✅' : t.task_status === 'in_progress' ? '🔄' : '⬜'}
                  </span>{' '}
                  {t.title}
                </div>
                <div className="item-card-meta">
                  <span>{t.priority}</span>
                  {t.project && <span>📁 {t.project}</span>}
                  {t.assigned_agent && <span>🤖 {t.assigned_agent}</span>}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
