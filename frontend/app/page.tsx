'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadDocument, UploadProgress } from './lib/api';

const STEPS = [
  { key: 'uploading', label: 'Uploading file to storage' },
  { key: 'parsing', label: 'Parsing document pages' },
  { key: 'chunking', label: 'Creating smart chunks' },
  { key: 'embedding', label: 'Generating embeddings' },
  { key: 'storing', label: 'Storing in vector database' },
];

export default function Home() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [stepStatuses, setStepStatuses] = useState<Record<string, { status: string; message: string }>>({});
  const [currentFileIndex, setCurrentFileIndex] = useState(0);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length > 0) {
      validateAndAddFiles(Array.from(e.dataTransfer.files));
    }
  };

  const validateAndAddFiles = (newFiles: File[]) => {
    let validFiles: File[] = [];
    let errorMessage = '';

    for (const f of newFiles) {
      const ext = f.name.split('.').pop()?.toLowerCase();
      if (ext !== 'pdf' && ext !== 'docx') {
        errorMessage = 'Only PDF and DOCX files are allowed.';
        continue;
      }
      if (f.size > 50 * 1024 * 1024) {
        errorMessage = 'File size must be under 50 MB per file.';
        continue;
      }
      validFiles.push(f);
    }

    if (errorMessage && validFiles.length === 0) {
      setError(errorMessage);
      return;
    }

    const totalFiles = [...files, ...validFiles];
    if (totalFiles.length > 10) {
      setError('You can only upload up to 10 files at a time. The first 10 selected files have been queued for processing.');
      validFiles = totalFiles.slice(0, 10).slice(files.length);
    } else {
      setError(null);
    }

    setFiles(prev => [...prev, ...validFiles].slice(0, 10));
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setIsUploading(true);
    setError(null);

    const docIds: string[] = [];
    const filenames: string[] = [];
    let hasError = false;

    for (let i = 0; i < files.length; i++) {
      setCurrentFileIndex(i);
      setStepStatuses({}); // Reset progress for the new file
      const currentFile = files[i];

      try {
        await new Promise<void>((resolve, reject) => {
          uploadDocument(currentFile, (event: UploadProgress) => {
            setStepStatuses(prev => ({
              ...prev,
              [event.step]: { status: event.status, message: event.message },
            }));

            if (event.step === 'done' && event.status === 'complete' && event.doc_id) {
              docIds.push(event.doc_id);
              filenames.push(event.filename || currentFile.name);
              resolve();
            }

            if (event.status === 'error') {
              reject(new Error(event.message));
            }
          }).catch(reject);
        });
      } catch (e: any) {
        hasError = true;
        setError(`Failed on ${currentFile.name}: ${e.message}`);
        setIsUploading(false);
        break;
      }
    }

    if (!hasError && docIds.length > 0) {
      setTimeout(() => {
        const queryParams = new URLSearchParams();
        queryParams.append('doc_ids', docIds.join(','));
        queryParams.append('filenames', filenames.join(','));
        router.push(`/chat?${queryParams.toString()}`);
      }, 800);
    }
  };

  const getStepStatus = (stepKey: string) => {
    return stepStatuses[stepKey]?.status || 'pending';
  };

  const getStepIcon = (status: string) => {
    if (status === 'complete') return '\u2713';
    if (status === 'error') return '\u2717';
    if (status === 'in_progress') return null;
    return '';
  };

  return (
    <div className="landing-container">
      <div className="landing-header">
        <h1 className="landing-logo">DocuMind</h1>
        <p className="landing-tagline">
          Upload up to 10 documents and ask questions across all of them. Get accurate, cited answers powered by advanced AI retrieval.
        </p>
      </div>

      <div className="landing-card">
        {!isUploading ? (
          <>
            <div
              className={`upload-zone ${dragOver ? 'dragover' : ''}`}
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <div className="upload-zone-icon">\ud83d\udcc4</div>
              <div className="upload-zone-title">
                {files.length > 0 ? `${files.length} file(s) selected` : 'Drop your documents here'}
              </div>
              <div className="upload-zone-subtitle">
                or click to browse files
              </div>
              <input
                id="file-input"
                type="file"
                multiple
                accept=".pdf,.docx"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files) {
                    validateAndAddFiles(Array.from(e.target.files));
                  }
                  e.target.value = ''; // Reset input to allow selecting the same file again
                }}
              />
            </div>

            {files.length > 0 && (
              <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {files.map((file, i) => (
                  <div key={i} className="upload-file-selected" style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <button className="upload-file-remove" onClick={() => removeFile(i)} style={{ background: 'transparent', border: 'none', color: 'var(--error)', cursor: 'pointer', fontSize: '1.2rem', padding: '0 0.5rem 0 0', lineHeight: 1 }}>×</button>
                    <span>📎</span>
                    <span className="upload-file-name" style={{ flexGrow: 1 }}>{file.name}</span>
                  </div>
                ))}
              </div>
            )}

            {error && (
              <div style={{ color: 'var(--error)', fontSize: '0.85rem', marginTop: '0.75rem', textAlign: 'center' }}>
                {error}
              </div>
            )}

            <button
              className="upload-btn"
              onClick={handleUpload}
              disabled={files.length === 0}
            >
              Upload & Process Document{files.length !== 1 ? 's' : ''}
            </button>
          </>
        ) : (
          <div className="stepper">
            <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                Processing file {currentFileIndex + 1} of {files.length}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                {files[currentFileIndex]?.name}
              </div>
            </div>
            {STEPS.map((step) => {
              const status = getStepStatus(step.key);
              const icon = getStepIcon(status);
              return (
                <div key={step.key} className="stepper-step">
                  <div className={`stepper-icon ${status}`} style={{ color: status === 'complete' ? '#00ff00' : 'inherit' }}>
                    {status === 'in_progress' ? (
                      <div className="spinner" />
                    ) : (
                      icon
                    )}
                  </div>
                  <span className={`stepper-label ${status}`}>
                    {step.label}
                  </span>
                  {stepStatuses[step.key]?.message && status === 'complete' && (
                    <span className="stepper-detail">
                      {stepStatuses[step.key].message}
                    </span>
                  )}
                </div>
              );
            })}
            {error && (
              <div style={{ color: 'var(--error)', fontSize: '0.85rem', marginTop: '1rem', textAlign: 'center' }}>
                {error}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="landing-hints">
        <span className="landing-hint">\ud83d\udcc4 Multiple PDF & DOCX allowed (Max 10)</span>
        <span className="landing-hint">\ud83d\udccf Max limit 50 MB per file</span>
        <span className="landing-hint">\ud83d\udd12 Files stored securely</span>
      </div>
    </div>
  );
}
