const API_BASE = '/api';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ChatResponse {
  response: string;
  history: ChatMessage[];
}

export interface FileMetadata {
  name: string;
  date_ingested: string;
  description: string;
  row_count: number;
  columns: string[];
}

export interface ChatHistory {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

// Helper to safely parse error responses
async function parseErrorResponse(res: Response): Promise<string> {
  try {
    const text = await res.text();
    try {
      const json = JSON.parse(text);
      return json.detail || json.message || text;
    } catch {
      return text || `Error ${res.status}`;
    }
  } catch {
    return `Error ${res.status}`;
  }
}

// Chat API
export async function sendMessage(message: string, history: ChatMessage[] = []): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  });
  
  if (!res.ok) {
    const error = await parseErrorResponse(res);
    throw new Error(error);
  }
  
  return res.json();
}

export async function refreshAgent(): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/refresh`, { method: 'POST' });
  if (!res.ok) {
    const error = await parseErrorResponse(res);
    throw new Error(error);
  }
}

// Files API
export async function uploadFile(file: File): Promise<{ name: string; description: string }> {
  const formData = new FormData();
  formData.append('file', file);
  
  const res = await fetch(`${API_BASE}/files/ingest`, {
    method: 'POST',
    body: formData,
  });
  
  if (!res.ok) {
    const error = await parseErrorResponse(res);
    throw new Error(error);
  }
  
  return res.json();
}

export async function listFiles(): Promise<{ files: FileMetadata[] }> {
  const res = await fetch(`${API_BASE}/files`);
  if (!res.ok) {
    const error = await parseErrorResponse(res);
    throw new Error(error);
  }
  return res.json();
}

export async function deleteFile(filename: string): Promise<void> {
  const res = await fetch(`${API_BASE}/files/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const error = await parseErrorResponse(res);
    throw new Error(error);
  }
}

// History API
export async function listChatHistories(): Promise<ChatHistory[]> {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) return [];
  return res.json();
}

export async function getChatHistory(id: string): Promise<ChatHistory | null> {
  const res = await fetch(`${API_BASE}/history/${id}`);
  if (!res.ok) return null;
  return res.json();
}

export async function saveChatHistory(history: ChatHistory): Promise<void> {
  await fetch(`${API_BASE}/history/${history.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(history),
  });
}

export async function deleteChatHistory(id: string): Promise<void> {
  await fetch(`${API_BASE}/history/${id}`, { method: 'DELETE' });
}
