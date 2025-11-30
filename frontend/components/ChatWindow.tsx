'use client';

import { useState, useRef, useEffect } from 'react';
import { ChatMessage } from '@/lib/types';
import { sendMessage } from '@/lib/api';
import MessageBubble from './MessageBubble';

interface ChatWindowProps {
  messages: ChatMessage[];
  onMessagesUpdate: (messages: ChatMessage[]) => void;
}

export default function ChatWindow({ messages, onMessagesUpdate }: ChatWindowProps) {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);
    setIsLoading(true);

    try {
      const response = await sendMessage(userMessage, messages);
      onMessagesUpdate(response.history);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      // Add the user message to show it was sent
      onMessagesUpdate([...messages, { role: 'user', content: userMessage }]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 chat-container">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <div className="text-4xl mb-4">💬</div>
              <div className="text-lg font-medium mb-2">Start a conversation</div>
              <div className="text-sm">Ask questions about your CSV data</div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, idx) => (
              <MessageBubble 
                key={idx} 
                message={msg} 
                allMessages={messages}
                messageIndex={idx}
              />
            ))}
            {isLoading && (
              <div className="flex justify-start mb-4">
                <div className="message-assistant rounded-2xl px-4 py-3">
                  <div className="text-xs text-accent mb-1 font-medium">CellByte</div>
                  <div className="loading-dots flex gap-1">
                    <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        {error && (
          <div className="bg-red-900/30 border border-red-500/50 text-red-300 px-4 py-2 rounded-lg mb-4">
            {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-[var(--border)] p-4">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your data..."
            className="flex-1 bg-[var(--card)] border border-[var(--border)] rounded-xl px-4 py-3 
                       text-white placeholder-gray-500 resize-none focus:outline-none 
                       focus:border-accent transition-colors"
            rows={1}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed
                       text-white px-6 py-3 rounded-xl font-medium transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

