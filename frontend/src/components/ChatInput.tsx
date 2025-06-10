'use client';

import { useEffect, useRef, useState } from 'react';

interface ChatInputProps {
  onSendMessage: (content: string) => void;
  disabled?: boolean;
  isLoading?: boolean;
}

const ChatInput = ({ onSendMessage, disabled = false, isLoading = false }: ChatInputProps) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled && !isLoading) {
      onSendMessage(message);
      setMessage('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = '44px';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = '44px'; // Reset to min height
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [message]);

  return (
    <form onSubmit={handleSubmit} className="chat-input bg-white flex items-end gap-2 p-4 border-t">
      <div className="flex-1">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Posez votre question..."
          className={`w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none min-h-[44px] ${
            disabled || isLoading ? 'bg-gray-100 cursor-not-allowed' : ''
          }`}
          disabled={disabled || isLoading}
          rows={1}
          onFocus={() => {
            setTimeout(() => {
              textareaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }, 100);
          }}
        />
      </div>
      <button
        type="submit"
        className={`p-3 rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center ${
          disabled || isLoading ? 'opacity-50 cursor-not-allowed' : ''
        }`}
        disabled={disabled || isLoading}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z"
            clipRule="evenodd"
          />
        </svg>
      </button>
    </form>
  );
};

export default ChatInput; 