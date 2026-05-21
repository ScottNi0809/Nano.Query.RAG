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
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useThemeStore } from '@/stores/themeStore';
import { useChatStore } from '@/stores/chatStore';
import ChatPage from '@/pages/ChatPage';
import DocumentsPage from '@/pages/DocumentsPage';
import '@/i18n';

type PageKey = 'chat' | 'documents';

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageKey>('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { mode, toggle } = useThemeStore();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const { t, i18n } = useTranslation();

  const toggleLang = () => {
    const next = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(next);
    localStorage.setItem('wtg-rag-lang', next);
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
        </nav>

        <div className="sidebar-bottom">
          {currentPage === 'chat' && (
            <button className="sidebar-action-btn" onClick={clearMessages} title={t('chat.clearHistory')}>
              <DeleteOutlined />
              {!sidebarCollapsed && <span>{t('chat.clearHistory')}</span>}
            </button>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="app-main">
        {/* Top Bar */}
        <header className="app-topbar">
          <div className="topbar-left">
            <h2 className="topbar-title">
              {currentPage === 'chat' ? t('nav.chat') : t('documents.title')}
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
          {currentPage === 'chat' ? <ChatPage /> : <DocumentsPage />}
        </div>
      </main>
    </div>
  );
}
