'use client';

import { useState, useEffect, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import ChatWindow from '@/components/ChatWindow';
import Sidebar from '@/components/Sidebar';
import { ChatMessage, ChatHistory } from '@/lib/types';
import { listChatHistories, getChatHistory, saveChatHistory } from '@/lib/api';

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [histories, setHistories] = useState<ChatHistory[]>([]);
  const [currentHistoryId, setCurrentHistoryId] = useState<string | null>(null);
  const [currentTitle, setCurrentTitle] = useState<string>('New Chat');

  // Load histories on mount
  useEffect(() => {
    loadHistories();
  }, []);

  const loadHistories = async () => {
    try {
      const result = await listChatHistories();
      setHistories(result);
    } catch (err) {
      console.error('Failed to load histories:', err);
    }
  };

  // Auto-save when messages change
  useEffect(() => {
    if (messages.length === 0) return;
    
    const saveCurrentChat = async () => {
      const historyId = currentHistoryId || uuidv4();
      
      // Generate title from first user message
      const firstUserMessage = messages.find(m => m.role === 'user');
      const title = firstUserMessage 
        ? firstUserMessage.content.slice(0, 50) + (firstUserMessage.content.length > 50 ? '...' : '')
        : 'New Chat';

      const history: ChatHistory = {
        id: historyId,
        title,
        created_at: currentHistoryId ? histories.find(h => h.id === historyId)?.created_at || new Date().toISOString() : new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages,
      };

      try {
        await saveChatHistory(history);
        if (!currentHistoryId) {
          setCurrentHistoryId(historyId);
        }
        setCurrentTitle(title);
        loadHistories();
      } catch (err) {
        console.error('Failed to save history:', err);
      }
    };

    const debounce = setTimeout(saveCurrentChat, 500);
    return () => clearTimeout(debounce);
  }, [messages, currentHistoryId]);

  const handleSelectHistory = async (history: ChatHistory | null) => {
    if (!history) {
      handleNewChat();
      return;
    }

    try {
      const fullHistory = await getChatHistory(history.id);
      if (fullHistory) {
        setMessages(fullHistory.messages);
        setCurrentHistoryId(fullHistory.id);
        setCurrentTitle(fullHistory.title);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setCurrentHistoryId(null);
    setCurrentTitle('New Chat');
  };

  const handleMessagesUpdate = (newMessages: ChatMessage[]) => {
    setMessages(newMessages);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        histories={histories}
        currentHistoryId={currentHistoryId}
        onSelectHistory={handleSelectHistory}
        onNewChat={handleNewChat}
        onHistoriesChange={loadHistories}
      />
      
      <main className="flex-1 flex flex-col bg-[var(--background)]">
        {/* Header */}
        <div className="border-b border-[var(--border)] px-6 py-4">
          <h2 className="text-lg font-medium text-white">{currentTitle}</h2>
        </div>
        
        {/* Chat */}
        <div className="flex-1 overflow-hidden">
          <ChatWindow 
            messages={messages} 
            onMessagesUpdate={handleMessagesUpdate}
          />
        </div>
      </main>
    </div>
  );
}

