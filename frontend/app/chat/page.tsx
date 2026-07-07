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
  const [showDocs, setShowDocs] = useState(false);
  const [showBackConfirm, setShowBackConfirm] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load chat history from session storage on mount
  useEffect(() => {
    if (!docIdsParam) return;
    const saved = sessionStorage.getItem(`chat_${docIdsParam}`);
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse saved chat:', e);
      }
    }
  }, [docIdsParam]);

  // Save chat history to session storage when it changes
  useEffect(() => {
    if (!docIdsParam) return;
    if (messages.length > 0) {
      sessionStorage.setItem(`chat_${docIdsParam}`, JSON.stringify(messages));
    }
  }, [messages, docIdsParam]);

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

    let currentMessages = [...messages, userMsg, aiMsg];
    setMessages(currentMessages);
    
    // Helper to persist even if component unmounts
    const updateAndPersist = (updater: (msg: Message) => Message) => {
      currentMessages = currentMessages.map(m => m.id === aiMsgId ? updater(m) : m);
      setMessages(currentMessages);
      sessionStorage.setItem(`chat_${docIdsParam}`, JSON.stringify(currentMessages));
    };

    try {
      await sendChatMessage(
        docIds,
        query,
        (token) => {
          updateAndPersist(m => ({ ...m, content: m.content + token, statusMessage: undefined }));
        },
        (sources) => {
          updateAndPersist(m => ({ ...m, sources }));
        },
        (statusMsg) => {
          updateAndPersist(m => ({ ...m, statusMessage: statusMsg }));
        },
        () => {
          updateAndPersist(m => ({ ...m, isStreaming: false }));
          setIsLoading(false);
        },
        (error) => {
          updateAndPersist(m => ({ ...m, content: m.content ? m.content + `\n\nError: ${error}` : `Error: ${error}`, isStreaming: false, statusMessage: undefined }));
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
      {showBackConfirm && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', maxWidth: '400px', textAlign: 'center', border: '1px solid var(--border)' }}>
            <h3 style={{ color: 'var(--text)', marginBottom: '1rem' }}>Are you sure?</h3>
            <p style={{ color: 'var(--text-muted)', marginBottom: '2rem', fontSize: '0.9rem', lineHeight: 1.5 }}>
              This will take you back to uploading documents and you will lose this session. Do you wish to go back?
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button 
                onClick={() => setShowBackConfirm(false)}
                style={{ padding: '0.6rem 1.5rem', background: 'transparent', border: '1px solid var(--text-muted)', color: 'var(--text)', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontWeight: 500 }}
              >
                No
              </button>
              <button 
                onClick={() => router.push('/')}
                style={{ padding: '0.6rem 1.5rem', background: 'var(--error)', border: 'none', color: '#fff', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontWeight: 500 }}
              >
                Yes
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="chat-header" style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button className="chat-header-back" onClick={() => setShowBackConfirm(true)}>
            ←
          </button>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', letterSpacing: '0.05em', fontWeight: 500 }}>USER ID: {docIdsParam.substring(0, 8)}</span>
        </div>
        <div style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span className="chat-header-title" style={{ fontSize: '1.5rem', fontWeight: 700 }}>DocuMind</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginLeft: 'auto' }}>
          <button 
            onClick={() => router.push(`/metrics?doc_ids=${docIdsParam}&filenames=${filenamesParam}`)}
            style={{ background: 'transparent', border: '1px solid #ffffff', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-full)', color: '#ffffff', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', fontWeight: 500 }}
          >
            View Metrics
          </button>
          <div style={{ position: 'relative' }}>
            <button 
              onClick={(e) => { e.stopPropagation(); setShowDocs(!showDocs); }}
              style={{ background: 'transparent', border: '1px solid #ffffff', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-full)', color: '#ffffff', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 500 }}
            >
              Uploaded Documents {showDocs ? '▲' : '▼'}
            </button>
            
            {showDocs && (
              <>
                <div style={{ position: 'fixed', inset: 0, zIndex: 10 }} onClick={() => setShowDocs(false)} />
                <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: '0.5rem', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '0.5rem', boxShadow: 'var(--shadow-md)', minWidth: '200px', zIndex: 20 }}>
                  {filenames.map((f, i) => (
                    <div key={i} style={{ padding: '0.5rem', fontSize: '0.8rem', color: 'var(--text)', borderBottom: i < filenames.length - 1 ? '1px solid var(--border)' : 'none', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '300px' }}>
                      📄 {decodeURIComponent(f)}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
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
        View Sources {isOpen ? '\u25b2' : '\u25bc'}
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
