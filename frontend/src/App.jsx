/**
 * AOS 奥思虚拟助理 — 主应用
 */
import { useEffect } from 'react';
import useStore from './stores/appStore';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatView from './components/ChatView';
import DashboardView from './components/DashboardView';
import KnowledgeView from './components/KnowledgeView';
import TasksView from './components/TasksView';

export default function App() {
  const { currentView, loadAgents, loadSessions } = useStore();

  useEffect(() => {
    loadAgents();
    loadSessions();
  }, []);

  // 跟踪鼠标位置实现渐变跟随
  useEffect(() => {
    const handleMouse = (e) => {
      document.documentElement.style.setProperty('--mouse-x', e.clientX + 'px');
      document.documentElement.style.setProperty('--mouse-y', e.clientY + 'px');
    };
    window.addEventListener('mousemove', handleMouse);
    return () => window.removeEventListener('mousemove', handleMouse);
  }, []);

  const renderView = () => {
    switch (currentView) {
      case 'dashboard': return <DashboardView />;
      case 'knowledge': return <KnowledgeView />;
      case 'tasks': return <TasksView />;
      case 'chat':
      default: return <ChatView />;
    }
  };

  return (
    <div className="app">
      <Sidebar />
      <div className="main-content">
        <Header />
        {renderView()}
      </div>
    </div>
  );
}
