'use client';

import { useState, useRef, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { sendChatMessage, Source } from '../lib/api';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
  statusMessage?: string;
}

function ChatContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const docIdsParam = searchParams.get('doc_ids') || '';
  const docIds = docIdsParam.split(',').filter(Boolean);
  const filenamesParam = searchParams.get('filenames') || '';
  const filenames = filenamesParam.split(',').filter(Boolean);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (docIds.length === 0) {
    router.push('/');
    return null;
  }

  const handleSend = async () => {
    const query = input.trim();
    if (!query || isLoading) return;

    setInput('');
    setIsLoading(true);

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
    };

    const aiMsgId = (Date.now() + 1).toString();
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'ai',
      content: '',
      isStreaming: true,
      statusMessage: 'Thinking...',
    };

    setMessages(prev => [...prev, userMsg, aiMsg]);

    try {
      await sendChatMessage(
        docIds,
        query,
        (token) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === aiMsgId
                ? { ...m, content: m.content + token, statusMessage: undefined }
                : m
            )
          );
        },
        (sources) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === aiMsgId ? { ...m, sources } : m
            )
          );
        },
        (statusMsg) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === aiMsgId ? { ...m, statusMessage: statusMsg } : m
            )
          );
        },
        () => {
          setMessages(prev =>
            prev.map(m =>
              m.id === aiMsgId ? { ...m, isStreaming: false } : m
            )
          );
          setIsLoading(false);
        },
        (error) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === aiMsgId
                ? { ...m, content: `Error: ${error}`, isStreaming: false }
                : m
            )
          );
          setIsLoading(false);
        }
      );
    } catch (e: any) {
      setMessages(prev =>
        prev.map(m =>
          m.id === aiMsgId
            ? { ...m, content: `Error: ${e.message}`, isStreaming: false }
            : m
        )
      );
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <button className="chat-header-back" onClick={() => router.push('/')}>
          \u2190
        </button>
        <span className="chat-header-title">DocuMind</span>
        <span className="chat-header-doc">
          \ud83d\udcc4 {filenames.length} document{filenames.length !== 1 ? 's' : ''} ({filenames.map(f => decodeURIComponent(f)).join(', ')})
        </span>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon">\ud83d\udcac</div>
            <div className="chat-empty-text">Ask anything about your document</div>
            <div className="chat-empty-hint">Your answers will include citations with page numbers</div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === 'user' ? 'U' : 'AI'}
            </div>
            <div>
              <div className="message-content">
                {msg.statusMessage && !msg.content ? (
                  <div className="message-thinking">
                    {msg.statusMessage}
                    <div className="thinking-dots">
                      <span /><span /><span />
                    </div>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
              {msg.sources && msg.sources.length > 0 && !msg.isStreaming && (
                <SourcesPanel sources={msg.sources} />
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-bar">
        <form
          className="chat-input-form"
          onSubmit={(e) => { e.preventDefault(); handleSend(); }}
        >
          <input
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your document..."
            disabled={isLoading}
          />
          <button
            type="submit"
            className="chat-send-btn"
            disabled={isLoading || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

function SourcesPanel({ sources }: { sources: Source[] }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div>
      <button className="sources-toggle" onClick={() => setIsOpen(!isOpen)}>
        \ud83d\udcda {sources.length} source{sources.length !== 1 ? 's' : ''} {isOpen ? '\u25b2' : '\u25bc'}
      </button>
      {isOpen && (
        <div className="sources-list">
          {sources.map((src, i) => (
            <div key={src.chunk_id || i} className="source-card">
              <div className="source-header">
                <span className="source-badge">
                  {src.source_filename} \u00b7 Page {src.page_number}
                </span>
                <span className="source-score">
                  Score: {(src.score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="source-snippet">
                {src.text_snippet}
              </div>
              {src.signed_url && (
                <a
                  href={src.signed_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-link"
                >
                  \ud83d\udd17 View original document
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div style={{ padding: '2rem', textAlign: 'center' }}>Loading chat...</div>}>
      <ChatContent />
    </Suspense>
  );
}
