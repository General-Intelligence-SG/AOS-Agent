/**
 * 顶部栏 — Agent 切换 + 操作按钮
 */
import { useState } from 'react';
import useStore from '../stores/appStore';

export default function Header() {
  const { agents, currentAgent, switchAgent, currentView } = useStore();
  const [showAgentPicker, setShowAgentPicker] = useState(false);

  const agent = agents.find((a) => a.name === currentAgent);

  const viewTitles = {
    chat: '对话',
    dashboard: '仪表盘',
    knowledge: '知识库',
    tasks: '任务管理',
    files: '文件管理',
  };

  return (
    <div className="header">
      <div className="header-left">
        <span className="header-title">{viewTitles[currentView] || '对话'}</span>
        {currentView === 'chat' && agent && (
          <div
            className="header-agent"
            onClick={() => setShowAgentPicker(!showAgentPicker)}
            style={{ cursor: 'pointer', position: 'relative' }}
          >
            <span>{agent.avatar_emoji}</span>
            <span>{agent.display_name}</span>
            <span style={{ fontSize: '10px', opacity: 0.6 }}>▼</span>

            {showAgentPicker && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: '8px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                padding: '8px',
                minWidth: '220px',
                zIndex: 50,
                boxShadow: 'var(--shadow-lg)',
              }}>
                {agents.map((a) => (
                  <button
                    key={a.name}
                    className={`nav-item ${a.name === currentAgent ? 'active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      switchAgent(a.name);
                      setShowAgentPicker(false);
                    }}
                  >
                    <span className="nav-item-icon">{a.avatar_emoji}</span>
                    <span>{a.display_name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="header-right">
        <button className="header-btn" title="导出数据">📥</button>
        <button className="header-btn" title="设置">⚙️</button>
      </div>
    </div>
  );
}
