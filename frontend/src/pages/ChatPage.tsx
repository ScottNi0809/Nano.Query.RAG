import { useEffect, useRef } from 'react';
import { BulbOutlined, CodeOutlined, RocketOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '@/stores/chatStore';
import ChatMessageBubble from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';

export default function ChatPage() {
  const { t } = useTranslation();
  const { messages, isLoading, sendMessage } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const isEmpty = messages.length === 0;

  const handleSuggestion = (text: string) => {
    sendMessage(text);
  };

  return (
    <div className="chat-page">
      <div className="chat-messages-area">
        {isEmpty ? (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">
              <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="4" y="8" width="40" height="32" rx="6" className="welcome-shape-1" />
                <circle cx="16" cy="24" r="3" className="welcome-shape-2" />
                <circle cx="24" cy="24" r="3" className="welcome-shape-2" />
                <circle cx="32" cy="24" r="3" className="welcome-shape-2" />
              </svg>
            </div>
            <h1 className="chat-welcome-title">{t('chat.welcomeTitle')}</h1>
            <p className="chat-welcome-subtitle">{t('chat.welcomeSubtitle')}</p>

            <div className="chat-suggestions">
              <button
                className="chat-suggestion-card"
                onClick={() => handleSuggestion(t('chat.suggestion1'))}
              >
                <BulbOutlined className="suggestion-icon" />
                <span>{t('chat.suggestion1')}</span>
              </button>
              <button
                className="chat-suggestion-card"
                onClick={() => handleSuggestion(t('chat.suggestion2'))}
              >
                <CodeOutlined className="suggestion-icon" />
                <span>{t('chat.suggestion2')}</span>
              </button>
              <button
                className="chat-suggestion-card"
                onClick={() => handleSuggestion(t('chat.suggestion3'))}
              >
                <RocketOutlined className="suggestion-icon" />
                <span>{t('chat.suggestion3')}</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="chat-messages-list">
            {messages.map((msg) => (
              <ChatMessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
