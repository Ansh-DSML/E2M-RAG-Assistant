const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface UploadProgress {
  step: string;
  status: 'in_progress' | 'complete' | 'error';
  message: string;
  doc_id?: string;
  filename?: string;
  chunk_count?: number;
  pages?: number;
  parents?: number;
  children?: number;
}

export interface Source {
  chunk_id: string;
  doc_id: string;
  source_filename: string;
  page_number: number;
  text_snippet: string;
  score: number;
  signed_url: string | null;
}

export async function uploadDocument(
  file: File,
  onProgress: (event: UploadProgress) => void
): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.trim()) {
        try {
          const event: UploadProgress = JSON.parse(line);
          onProgress(event);
        } catch (e) {
          // skip malformed lines
        }
      }
    }
  }

  // Process remaining buffer
  if (buffer.trim()) {
    try {
      onProgress(JSON.parse(buffer));
    } catch (e) {}
  }
}

export async function sendChatMessage(
  docIds: string[],
  query: string,
  onToken: (token: string) => void,
  onSources: (sources: Source[]) => void,
  onStatus: (message: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_ids: docIds, query }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Chat failed' }));
    throw new Error(err.detail || 'Chat failed');
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed === ':') continue;

      // Parse SSE format
      if (trimmed.startsWith('event:')) continue;
      if (trimmed.startsWith('data:')) {
        const dataStr = trimmed.slice(5).trim();
        if (!dataStr) continue;

        try {
          const data = JSON.parse(dataStr);
          // The event type comes from the previous 'event:' line
          // but we can infer from data shape
          if (data.token !== undefined) {
            onToken(data.token);
          } else if (data.sources !== undefined) {
            onSources(data.sources);
          } else if (data.message !== undefined) {
            onStatus(data.message);
          }
        } catch (e) {}
      }
    }
  }

  onDone();
}
