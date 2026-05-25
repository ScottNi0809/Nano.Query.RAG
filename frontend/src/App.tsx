import { useState } from 'react';
import {
  MessageOutlined,
  FileTextOutlined,
  SunOutlined,
  MoonOutlined,
  GlobalOutlined,
  DeleteOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  CloseOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useThemeStore } from '@/stores/themeStore';
import { useChatStore } from '@/stores/chatStore';
import ChatPage from '@/pages/ChatPage';
import DocumentsPage from '@/pages/DocumentsPage';
import BenchmarkPage from '@/pages/BenchmarkPage';
import '@/i18n';

type PageKey = 'chat' | 'documents' | 'benchmark';

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageKey>('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { mode, toggle } = useThemeStore();
  const { sessions, activeSessionId, newSession, switchSession, deleteSession, clearMessages } = useChatStore();
  const { t, i18n } = useTranslation();

  const toggleLang = () => {
    const next = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(next);
    localStorage.setItem('wtg-rag-lang', next);
  };

  const handleNewChat = () => {
    newSession();
    setCurrentPage('chat');
  };

  const handleSelectSession = (id: string) => {
    switchSession(id);
    setCurrentPage('chat');
  };

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteSession(id);
  };

  const formatSessionDate = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays === 0) return t('chat.today');
    if (diffDays === 1) return t('chat.yesterday');
    if (diffDays < 7) return t('chat.daysAgo', { count: diffDays });
    return d.toLocaleDateString();
  };

  return (
    <div className={`app-root ${mode}`} data-theme={mode}>
      {/* Sidebar */}
      <aside className={`app-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-top">
          <div className="sidebar-brand">
            <div className="brand-logo">
              <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="2" width="28" height="28" rx="8" className="brand-shape" />
                <path d="M10 16L14 20L22 12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            {!sidebarCollapsed && <span className="brand-text">{t('common.appName')}</span>}
          </div>

          <button
            className="sidebar-collapse-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            aria-label="Toggle sidebar"
          >
            {sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
        </div>

        <nav className="sidebar-nav">
          <button
            className={`sidebar-nav-item ${currentPage === 'chat' ? 'active' : ''}`}
            onClick={() => setCurrentPage('chat')}
          >
            <MessageOutlined />
            {!sidebarCollapsed && <span>{t('nav.chat')}</span>}
          </button>
          <button
            className={`sidebar-nav-item ${currentPage === 'documents' ? 'active' : ''}`}
            onClick={() => setCurrentPage('documents')}
          >
            <FileTextOutlined />
            {!sidebarCollapsed && <span>{t('nav.documents')}</span>}
          </button>
          <button
            className={`sidebar-nav-item ${currentPage === 'benchmark' ? 'active' : ''}`}
            onClick={() => setCurrentPage('benchmark')}
          >
            <ExperimentOutlined />
            {!sidebarCollapsed && <span>{t('nav_benchmark')}</span>}
          </button>
        </nav>

        {/* Chat History */}
        {!sidebarCollapsed && (
          <div className="sidebar-history">
            <div className="sidebar-history-header">
              <span className="sidebar-history-title">{t('chat.history')}</span>
              <button className="sidebar-history-new" onClick={handleNewChat} title={t('chat.newChat')}>
                <PlusOutlined />
              </button>
            </div>
            <div className="sidebar-history-list">
              {sessions.length === 0 ? (
                <div className="sidebar-history-empty">{t('chat.noHistory')}</div>
              ) : (
                sessions.map((session) => (
                  <button
                    key={session.id}
                    className={`sidebar-history-item ${activeSessionId === session.id ? 'active' : ''}`}
                    onClick={() => handleSelectSession(session.id)}
                  >
                    <div className="history-item-content">
                      <span className="history-item-title">{session.title}</span>
                      <span className="history-item-date">{formatSessionDate(session.updatedAt)}</span>
                    </div>
                    <button
                      className="history-item-delete"
                      onClick={(e) => handleDeleteSession(e, session.id)}
                      title={t('common.delete')}
                    >
                      <CloseOutlined />
                    </button>
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        <div className="sidebar-bottom">
          <button className="sidebar-action-btn" onClick={clearMessages} title={t('chat.clearHistory')}>
            <DeleteOutlined />
            {!sidebarCollapsed && <span>{t('chat.clearHistory')}</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="app-main">
        {/* Top Bar */}
        <header className="app-topbar">
          <div className="topbar-left">
            <h2 className="topbar-title">
              {currentPage === 'chat' ? t('nav.chat') : currentPage === 'documents' ? t('documents.title') : t('benchmark.title')}
            </h2>
          </div>
          <div className="topbar-right">
            <button className="topbar-btn" onClick={toggleLang} title="Language">
              <GlobalOutlined />
              <span className="topbar-btn-label">{i18n.language === 'en' ? 'EN' : '中'}</span>
            </button>
            <button className="topbar-btn" onClick={toggle} title={t(`theme.${mode === 'light' ? 'dark' : 'light'}`)}>
              {mode === 'light' ? <MoonOutlined /> : <SunOutlined />}
            </button>
          </div>
        </header>

        {/* Page Content */}
        <div className="app-content">
          {currentPage === 'chat' && <ChatPage />}
          {currentPage === 'documents' && <DocumentsPage />}
          {currentPage === 'benchmark' && <BenchmarkPage />}
        </div>
      </main>
    </div>
  );
}
