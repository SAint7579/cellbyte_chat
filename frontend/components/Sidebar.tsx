'use client';

import { useState, useRef, useEffect } from 'react';
import { ChatHistory, FileMetadata } from '@/lib/types';
import { uploadFile, listFiles, deleteFile, refreshAgent, listChatHistories, deleteChatHistory } from '@/lib/api';

interface SidebarProps {
  histories: ChatHistory[];
  currentHistoryId: string | null;
  onSelectHistory: (history: ChatHistory | null) => void;
  onNewChat: () => void;
  onHistoriesChange: () => void;
}

export default function Sidebar({ 
  histories, 
  currentHistoryId, 
  onSelectHistory, 
  onNewChat,
  onHistoriesChange 
}: SidebarProps) {
  const [files, setFiles] = useState<FileMetadata[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadFiles();
  }, []);

  const loadFiles = async () => {
    try {
      const result = await listFiles();
      setFiles(result.files);
    } catch (err) {
      console.error('Failed to load files:', err);
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!file.name.endsWith('.csv')) {
      setUploadError('Only CSV files are supported');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      await uploadFile(file);
      await refreshAgent();
      await loadFiles();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleDeleteFile = async (filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;
    try {
      await deleteFile(filename);
      await refreshAgent();
      await loadFiles();
    } catch (err) {
      console.error('Failed to delete file:', err);
    }
  };

  const handleDeleteHistory = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this chat?')) return;
    try {
      await deleteChatHistory(id);
      onHistoriesChange();
    } catch (err) {
      console.error('Failed to delete history:', err);
    }
  };

  return (
    <div className="w-80 bg-[var(--card)] border-r border-[var(--border)] flex flex-col h-screen">
      {/* Header */}
      <div className="p-4 border-b border-[var(--border)]">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <span className="text-2xl">📊</span> CellByte
        </h1>
        <p className="text-xs text-gray-500 mt-1">AI-powered CSV explorer</p>
      </div>

      {/* New Chat Button */}
      <div className="p-4">
        <button
          onClick={onNewChat}
          className="w-full bg-accent hover:bg-accent-hover text-white py-2.5 px-4 
                     rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          <span>+</span> New Chat
        </button>
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto px-4">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Chat History</div>
        {histories.length === 0 ? (
          <div className="text-sm text-gray-600 py-2">No previous chats</div>
        ) : (
          <div className="space-y-1">
            {histories.map((history) => (
              <div
                key={history.id}
                onClick={() => onSelectHistory(history)}
                className={`group flex items-center justify-between p-2.5 rounded-lg cursor-pointer 
                           transition-colors ${
                             currentHistoryId === history.id
                               ? 'bg-accent/20 text-white'
                               : 'hover:bg-[var(--card-hover)] text-gray-400'
                           }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{history.title}</div>
                  <div className="text-xs text-gray-600">
                    {new Date(history.updated_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteHistory(history.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 
                             p-1 transition-opacity"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* File Upload Section */}
      <div className="p-4 border-t border-[var(--border)]">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Data Files</div>
        
        {/* Upload Zone */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`file-upload-zone rounded-lg p-4 text-center cursor-pointer mb-3 
                     ${isDragging ? 'dragging' : ''}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
            className="hidden"
          />
          {isUploading ? (
            <div className="text-sm text-gray-400">Uploading...</div>
          ) : (
            <>
              <div className="text-2xl mb-1">📁</div>
              <div className="text-sm text-gray-400">Drop CSV or click</div>
            </>
          )}
        </div>

        {uploadError && (
          <div className="text-xs text-red-400 mb-2">{uploadError}</div>
        )}

        {/* File List */}
        <div className="space-y-1 max-h-32 overflow-y-auto">
          {files.map((file) => (
            <div
              key={file.name}
              className="flex items-center justify-between text-sm p-2 rounded 
                         bg-[var(--background)] group"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-green-400">📄</span>
                <span className="truncate text-gray-300" title={file.name}>
                  {file.name}
                </span>
              </div>
              <button
                onClick={() => handleDeleteFile(file.name)}
                className="opacity-0 group-hover:opacity-100 text-gray-500 
                           hover:text-red-400 transition-opacity"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

