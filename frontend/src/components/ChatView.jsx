/**
 * 聊天视图 — 消息列表 + 输入框
 */
import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import useStore from '../stores/appStore';

export default function ChatView() {
  const {
    messages, isLoading, sendMessage, agents, currentAgent, switchAgent,
  } = useStore();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    await sendMessage(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const agentInfo = agents.find((a) => a.name === currentAgent);

  return (
    <div className="chat-area">
      <div className="chat-messages">
        {messages.length === 0 ? (
          <WelcomeScreen agents={agents} onSelectAgent={(name) => {
            switchAgent(name);
            sendMessage(`你好，请介绍一下你自己和你能做什么。`);
          }} />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                agents={agents}
              />
            ))}
            {isLoading && (
              <div className="message assistant">
                <div className="message-avatar">
                  {agentInfo?.avatar_emoji || '🤖'}
                </div>
                <div className="message-body">
                  <div className="message-content" style={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-subtle)',
                    borderTopLeftRadius: 'var(--space-1)',
                  }}>
                    <div className="loading-dots">
                      <span /><span /><span />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={`向 ${agentInfo?.display_name || 'AOS'} 发送消息...`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
          >
            ▶
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message, agents }) {
  const isUser = message.role === 'user';
  const agent = agents.find((a) => a.name === message.agent_name);

  return (
    <div className={`message ${message.role}`}>
      <div className="message-avatar">
        {isUser ? '👤' : (agent?.avatar_emoji || '🤖')}
      </div>
      <div className="message-body">
        <div className="message-meta">
          <span>{isUser ? '你' : (agent?.display_name || message.agent_name || 'AOS')}</span>
          <span>·</span>
          <span>{formatTime(message.created_at)}</span>
        </div>
        <div className="message-content">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

function WelcomeScreen({ agents, onSelectAgent }) {
  return (
    <div className="welcome">
      <div className="welcome-icon">奥</div>
      <h1>你好，我是 AOS 奥思</h1>
      <p>
        你的企业级虚拟助理。我有 {agents.length} 个专职 Agent 协同工作，
        可以帮你管理知识、整理事务、撰写文档、处理邮件等。选择一个 Agent 开始吧：
      </p>
      <div className="welcome-agents">
        {agents.map((a) => (
          <div
            key={a.name}
            className="welcome-agent-chip"
            onClick={() => onSelectAgent(a.name)}
          >
            <span>{a.avatar_emoji}</span>
            <span>{a.display_name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}
