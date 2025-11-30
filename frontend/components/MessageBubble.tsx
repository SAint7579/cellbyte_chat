'use client';

import { ChatMessage } from '@/lib/types';
import ToolCallDisplay from './ToolCallDisplay';

interface MessageBubbleProps {
  message: ChatMessage;
  nextMessage?: ChatMessage;
}

export default function MessageBubble({ message, nextMessage }: MessageBubbleProps) {
  // Don't render tool messages directly - they're shown in ToolCallDisplay
  if (message.role === 'tool') {
    return null;
  }
  
  // If this is an assistant message with tool_calls, show the tool call display
  if (message.role === 'assistant' && message.tool_calls && message.tool_calls.length > 0) {
    // Find the corresponding tool result (next message should be a tool message)
    const toolResult = nextMessage?.role === 'tool' ? nextMessage : undefined;
    return <ToolCallDisplay toolCallMessage={message} toolResultMessage={toolResult} />;
  }
  
  // Skip empty assistant messages (these come before tool calls)
  if (message.role === 'assistant' && !message.content) {
    return null;
  }
  
  const isUser = message.role === 'user';
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'message-user text-white'
            : 'message-assistant text-gray-100'
        }`}
      >
        {!isUser && (
          <div className="text-xs text-accent mb-1 font-medium">CellByte</div>
        )}
        <div className="whitespace-pre-wrap break-words">{message.content}</div>
      </div>
    </div>
  );
}

