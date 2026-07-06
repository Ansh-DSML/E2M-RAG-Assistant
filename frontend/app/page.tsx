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
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [stepStatuses, setStepStatuses] = useState<Record<string, { status: string; message: string }>>({}); 

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) validateAndSetFile(droppedFile);
  };

  const validateAndSetFile = (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase();
    if (ext !== 'pdf' && ext !== 'docx') {
      setError('Only PDF and DOCX files are allowed.');
      return;
    }
    if (f.size > 50 * 1024 * 1024) { // Updated to 50MB per user request
      setError('File size must be under 50 MB.');
      return;
    }
    setError(null);
    setFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setStepStatuses({});

    try {
      await uploadDocument(file, (event: UploadProgress) => {
        setStepStatuses(prev => ({
          ...prev,
          [event.step]: { status: event.status, message: event.message },
        }));

        if (event.step === 'done' && event.status === 'complete' && event.doc_id) {
          setTimeout(() => {
            router.push(`/chat?doc_id=${event.doc_id}&filename=${encodeURIComponent(event.filename || file.name)}`);
          }, 800);
        }

        if (event.status === 'error') {
          setError(event.message);
          setIsUploading(false);
        }
      });
    } catch (e: any) {
      setError(e.message || 'Upload failed. Please try again.');
      setIsUploading(false);
    }
  };

  const getStepStatus = (stepKey: string) => {
    return stepStatuses[stepKey]?.status || 'pending';
  };

  const getStepIcon = (status: string) => {
    if (status === 'complete') return '\u2713'; // checkmark
    if (status === 'error') return '\u2717'; // x
    if (status === 'in_progress') return null; // spinner
    return '';
  };

  return (
    <div className="landing-container">
      <div className="landing-header">
        <h1 className="landing-logo">DocuMind</h1>
        <p className="landing-tagline">
          Upload your documents and ask questions. Get accurate, cited answers powered by advanced AI retrieval.
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
                {file ? 'File selected' : 'Drop your document here'}
              </div>
              <div className="upload-zone-subtitle">
                or click to browse files
              </div>
              <input
                id="file-input"
                type="file"
                accept=".pdf,.docx"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) validateAndSetFile(f);
                }}
              />
            </div>

            {file && (
              <div className="upload-file-selected">
                <span>\ud83d\udcce</span>
                <span className="upload-file-name">{file.name}</span>
                <button className="upload-file-remove" onClick={() => setFile(null)}>\u00d7</button>
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
              disabled={!file}
            >
              Upload & Process Document
            </button>
          </>
        ) : (
          <div className="stepper">
            <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>Processing your document</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>{file?.name}</div>
            </div>
            {STEPS.map((step) => {
              const status = getStepStatus(step.key);
              const icon = getStepIcon(status);
              return (
                <div key={step.key} className="stepper-step">
                  <div className={`stepper-icon ${status}`}>
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
        <span className="landing-hint">\ud83d\udcc4 PDF & DOCX allowed</span>
        <span className="landing-hint">\ud83d\udccf Max limit 50 MB</span>
        <span className="landing-hint">\ud83d\udd12 Files stored securely</span>
      </div>
    </div>
  );
}
