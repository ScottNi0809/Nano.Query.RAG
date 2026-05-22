import { useRef, useState, type KeyboardEvent } from 'react';
import { SendOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '@/stores/chatStore';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [historyIndex, setHistoryIndex] = useState(-1);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { t } = useTranslation();
  const messages = useChatStore((s) => s.messages);

  const userMessages = messages.filter((m) => m.role === 'user').map((m) => m.content);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
    setHistoryIndex(-1);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'ArrowUp' && userMessages.length > 0) {
      e.preventDefault();
      const nextIndex = historyIndex + 1;
      if (nextIndex < userMessages.length) {
        const msg = userMessages[userMessages.length - 1 - nextIndex];
        setValue(msg);
        setHistoryIndex(nextIndex);
      } else {
        // Already at oldest question, move cursor to beginning
        textareaRef.current?.setSelectionRange(0, 0);
      }
    }
    if (e.key === 'ArrowDown' && historyIndex >= 0) {
      e.preventDefault();
      const nextIndex = historyIndex - 1;
      if (nextIndex < 0) {
        setValue('');
        setHistoryIndex(-1);
      } else {
        const msg = userMessages[userMessages.length - 1 - nextIndex];
        setValue(msg);
        setHistoryIndex(nextIndex);
      }
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  };

  return (
    <div className="chat-input-container">
      <div className="chat-input-wrapper">
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={t('chat.placeholder')}
          disabled={disabled}
          rows={1}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          aria-label={t('chat.send')}
        >
          <SendOutlined />
        </button>
      </div>
    </div>
  );
}
