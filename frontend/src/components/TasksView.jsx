/**
 * 任务管理视图
 */
import { useEffect, useState } from 'react';
import useStore from '../stores/appStore';

const STATUS_LABELS = {
  todo: { icon: '⬜', label: '待办' },
  in_progress: { icon: '🔄', label: '进行中' },
  waiting: { icon: '⏳', label: '等待' },
  done: { icon: '✅', label: '已完成' },
  cancelled: { icon: '❌', label: '已取消' },
};

const PRIORITY_LABELS = {
  urgent: '🔴 紧急',
  high: '🟠 高',
  medium: '🔵 中',
  low: '⚪ 低',
};

export default function TasksView() {
  const { tasks, loadTasks, createTask, updateTask } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState({
    title: '', description: '', priority: 'medium', project: '', tags: '',
  });

  useEffect(() => { loadTasks(); }, []);

  const filteredTasks = tasks.filter((t) => {
    if (filter === 'all') return t.task_status !== 'cancelled';
    return t.task_status === filter;
  });

  const handleCreate = async () => {
    if (!form.title.trim()) return;
    await createTask({
      title: form.title,
      description: form.description || null,
      priority: form.priority,
      project: form.project || null,
      tags: form.tags ? form.tags.split(',').map((t) => t.trim()) : [],
    });
    setForm({ title: '', description: '', priority: 'medium', project: '', tags: '' });
    setShowModal(false);
  };

  const toggleStatus = async (task) => {
    const next = task.task_status === 'todo' ? 'in_progress'
      : task.task_status === 'in_progress' ? 'done'
      : task.task_status === 'done' ? 'todo' : 'todo';
    await updateTask(task.id, { task_status: next });
  };

  return (
    <div className="tasks-view">
      <div className="view-header">
        <h2>✅ 任务管理</h2>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          ＋ 新建任务
        </button>
      </div>

      {/* Filter */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {[
          { key: 'all', label: '全部' },
          { key: 'todo', label: '⬜ 待办' },
          { key: 'in_progress', label: '🔄 进行中' },
          { key: 'done', label: '✅ 已完成' },
        ].map((f) => (
          <button
            key={f.key}
            className={filter === f.key ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setFilter(f.key)}
            style={{ fontSize: '12px' }}
          >
            {f.label} ({tasks.filter((t) =>
              f.key === 'all' ? t.task_status !== 'cancelled' : t.task_status === f.key
            ).length})
          </button>
        ))}
      </div>

      {filteredTasks.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">✅</div>
          <div className="empty-state-text">
            {filter === 'all' ? '暂无任务，点击"新建任务"开始' : '此分类暂无任务'}
          </div>
        </div>
      ) : (
        <div className="item-list">
          {filteredTasks.map((task) => (
            <div
              key={task.id}
              className={`item-card priority-${task.priority}`}
              style={{ cursor: 'pointer' }}
              onClick={() => toggleStatus(task)}
            >
              <div className="item-card-title">
                <span>{STATUS_LABELS[task.task_status]?.icon || '⬜'}</span>{' '}
                <span style={{
                  textDecoration: task.task_status === 'done' ? 'line-through' : 'none',
                  opacity: task.task_status === 'done' ? 0.6 : 1,
                }}>
                  {task.title}
                </span>
              </div>
              {task.description && (
                <p style={{
                  marginTop: '4px', fontSize: '12px', color: 'var(--text-secondary)',
                  paddingLeft: '24px',
                }}>
                  {task.description}
                </p>
              )}
              <div className="item-card-meta" style={{ paddingLeft: '24px', marginTop: '4px' }}>
                <span>{PRIORITY_LABELS[task.priority]}</span>
                {task.project && <span>📁 {task.project}</span>}
                {task.assigned_agent && <span>🤖 {task.assigned_agent}</span>}
                {task.due_date && (
                  <span>⏰ {new Date(task.due_date).toLocaleDateString('zh-CN')}</span>
                )}
              </div>
              {task.tags?.length > 0 && (
                <div style={{ marginTop: '6px', paddingLeft: '24px', display: 'flex', gap: '4px' }}>
                  {task.tags.map((tag, i) => (
                    <span key={i} className="item-tag">{tag}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>📋 新建任务</h3>
            <div className="form-group">
              <label className="form-label">标题</label>
              <input
                className="form-input"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="输入任务标题..."
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">描述</label>
              <textarea
                className="form-textarea"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="详细描述..."
                rows={3}
              />
            </div>
            <div className="form-group">
              <label className="form-label">优先级</label>
              <select
                className="form-input"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
              >
                <option value="low">⚪ 低</option>
                <option value="medium">🔵 中</option>
                <option value="high">🟠 高</option>
                <option value="urgent">🔴 紧急</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">项目</label>
              <input
                className="form-input"
                value={form.project}
                onChange={(e) => setForm({ ...form, project: e.target.value })}
                placeholder="所属项目..."
              />
            </div>
            <div className="form-group">
              <label className="form-label">标签（逗号分隔）</label>
              <input
                className="form-input"
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                placeholder="标签1, 标签2, ..."
              />
            </div>
            <div className="form-actions">
              <button className="btn-secondary" onClick={() => setShowModal(false)}>取消</button>
              <button className="btn-primary" onClick={handleCreate}>创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
