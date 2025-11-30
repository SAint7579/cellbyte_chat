'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
        {isUser ? (
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                li: ({ children }) => <li className="text-gray-200">{children}</li>,
                h1: ({ children }) => <h1 className="text-xl font-bold mb-2 text-white">{children}</h1>,
                h2: ({ children }) => <h2 className="text-lg font-bold mb-2 text-white">{children}</h2>,
                h3: ({ children }) => <h3 className="text-base font-bold mb-2 text-white">{children}</h3>,
                code: ({ className, children, ...props }) => {
                  const isInline = !className;
                  return isInline ? (
                    <code className="bg-black/40 px-1.5 py-0.5 rounded text-accent font-mono text-sm" {...props}>
                      {children}
                    </code>
                  ) : (
                    <code className={`${className} block bg-black/40 p-3 rounded-lg overflow-x-auto font-mono text-sm`} {...props}>
                      {children}
                    </code>
                  );
                },
                pre: ({ children }) => <pre className="mb-2">{children}</pre>,
                a: ({ href, children }) => (
                  <a href={href} className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">
                    {children}
                  </a>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-accent pl-3 italic text-gray-400 mb-2">
                    {children}
                  </blockquote>
                ),
                table: ({ children }) => (
                  <div className="overflow-x-auto mb-2">
                    <table className="min-w-full border-collapse">{children}</table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border border-gray-600 px-3 py-1.5 bg-black/30 text-left font-medium">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border border-gray-700 px-3 py-1.5">{children}</td>
                ),
                strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
                em: ({ children }) => <em className="italic text-gray-300">{children}</em>,
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
