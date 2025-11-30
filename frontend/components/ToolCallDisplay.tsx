'use client';

import { ChatMessage } from '@/lib/types';

interface ToolCallDisplayProps {
  toolCallMessage: ChatMessage;
  toolResultMessage?: ChatMessage;
}

export default function ToolCallDisplay({ toolCallMessage, toolResultMessage }: ToolCallDisplayProps) {
  const toolCalls = toolCallMessage.tool_calls || [];
  
  return (
    <div className="my-3 mx-4">
      {toolCalls.map((call, idx) => (
        <div key={call.id || idx} className="tool-call-block rounded-lg p-4 mb-2">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-accent text-sm font-mono">⚡ Tool Call</span>
            <span className="text-gray-400 text-xs font-mono bg-black/30 px-2 py-0.5 rounded">
              {call.name}
            </span>
          </div>
          
          {/* Query/Args */}
          <div className="mb-3">
            <div className="text-xs text-gray-500 mb-1">Query:</div>
            <div className="bg-black/30 rounded p-2 font-mono text-sm text-gray-300">
              {typeof call.args === 'object' 
                ? JSON.stringify(call.args, null, 2)
                : String(call.args)
              }
            </div>
          </div>
          
          {/* Result */}
          {toolResultMessage && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Result:</div>
              <div className="bg-black/30 rounded p-2 font-mono text-xs text-gray-400 max-h-40 overflow-y-auto">
                <pre className="whitespace-pre-wrap break-words">
                  {toolResultMessage.content}
                </pre>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

