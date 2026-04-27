/**
 * 知识库视图
 */
import { useEffect, useState } from 'react';
import useStore from '../stores/appStore';

export default function KnowledgeView() {
  const { documents, loadDocuments, createDocument } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ title: '', content: '', category: '', tags: '' });

  useEffect(() => { loadDocuments(); }, []);

  const handleCreate = async () => {
    if (!form.title.trim()) return;
    await createDocument({
      title: form.title,
      content: form.content,
      category: form.category || null,
      tags: form.tags ? form.tags.split(',').map((t) => t.trim()) : [],
      is_knowledge: true,
    });
    setForm({ title: '', content: '', category: '', tags: '' });
    setShowModal(false);
  };

  return (
    <div className="knowledge-view">
      <div className="view-header">
        <h2>📚 知识库</h2>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          ＋ 新建条目
        </button>
      </div>

      {documents.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📚</div>
          <div className="empty-state-text">知识库暂无内容，点击"新建条目"开始积累知识</div>
        </div>
      ) : (
        <div className="item-list">
          {documents.map((doc) => (
            <div key={doc.id} className="item-card">
              <div className="item-card-title">{doc.title}</div>
              <div className="item-card-meta">
                {doc.category && <span>📁 {doc.category}</span>}
                {doc.file_type && <span>📄 {doc.file_type}</span>}
                <span>{new Date(doc.created_at).toLocaleDateString('zh-CN')}</span>
              </div>
              {doc.tags?.length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {doc.tags.map((tag, i) => (
                    <span key={i} className="item-tag">{tag}</span>
                  ))}
                </div>
              )}
              {doc.content && (
                <p style={{
                  marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)',
                  lineHeight: 1.6, maxHeight: '60px', overflow: 'hidden',
                }}>
                  {doc.content.substring(0, 200)}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>📝 新建知识条目</h3>
            <div className="form-group">
              <label className="form-label">标题</label>
              <input
                className="form-input"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="输入标题..."
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">内容</label>
              <textarea
                className="form-textarea"
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                placeholder="输入内容（支持 Markdown）..."
                rows={6}
              />
            </div>
            <div className="form-group">
              <label className="form-label">分类</label>
              <input
                className="form-input"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="如：工作、学习、项目名..."
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
