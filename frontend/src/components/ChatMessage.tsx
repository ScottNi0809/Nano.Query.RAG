import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { CopyOutlined, CheckOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useThemeStore } from '@/stores/themeStore';
import SourceCitation from './SourceCitation';
import type { ChatMessage } from '@/stores/chatStore';

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

export default function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const { t } = useTranslation();
  const theme = useThemeStore((s) => s.mode);
  const isUser = message.role === 'user';

  return (
    <div className={`chat-message ${isUser ? 'chat-message-user' : 'chat-message-assistant'}`}>
      <div className={`chat-message-avatar ${isUser ? 'avatar-user' : 'avatar-assistant'}`}>
        {isUser ? '🧑' : '🤖'}
      </div>
      <div className="chat-message-body">
        {isUser ? (
          <p className="chat-message-text">{message.content}</p>
        ) : (
          <>
            <div className="chat-message-markdown">
              {message.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '');
                      const codeString = String(children).replace(/\n$/, '');

                      if (match) {
                        return (
                          <CodeBlock
                            language={match[1]}
                            code={codeString}
                            theme={theme}
                            copyLabel={t('chat.copyCode')}
                            copiedLabel={t('chat.copied')}
                          />
                        );
                      }

                      return (
                        <code className="inline-code" {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              ) : (
                message.isStreaming && (
                  <div className="thinking-indicator">
                    <span className="thinking-dot" />
                    <span className="thinking-dot" />
                    <span className="thinking-dot" />
                    <span className="thinking-text">{t('chat.thinking')}</span>
                  </div>
                )
              )}
            </div>

            {!message.isStreaming && message.sources && message.sources.length > 0 && (
              <SourceCitation sources={message.sources} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function CodeBlock({
  language,
  code,
  theme,
  copyLabel,
  copiedLabel,
}: {
  language: string;
  code: string;
  theme: string;
  copyLabel: string;
  copiedLabel: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-block-lang">{language}</span>
        <button className="code-copy-btn" onClick={handleCopy}>
          {copied ? <CheckOutlined /> : <CopyOutlined />}
          <span>{copied ? copiedLabel : copyLabel}</span>
        </button>
      </div>
      <SyntaxHighlighter
        style={theme === 'dark' ? oneDark : oneLight}
        language={language}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: '0 0 8px 8px',
          fontSize: '13px',
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
