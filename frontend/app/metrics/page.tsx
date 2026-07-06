'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

interface MetricRecord {
  timestamp: number;
  question: string;
  answer_preview: string;
  latency_ttft: number;
  latency_total: number;
  faithfulness: number;
  answer_relevancy: number;
  context_relevance: number;
}

interface MetricsData {
  history: MetricRecord[];
  averages: {
    latency_ttft: number;
    latency_total: number;
    faithfulness: number;
    answer_relevancy: number;
    context_relevance: number;
  };
}

function MetricsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const docIdsParam = searchParams.get('doc_ids') || '';
  
  const [data, setData] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let url = 'http://localhost:8000/metrics';
    if (docIdsParam) {
      url += `?session_id=${docIdsParam}`;
    }
    
    fetch(url)
      .then(res => res.json())
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading metrics...</div>;
  }

  const history = data?.history || [];
  const averages = data?.averages;

  // Format data for chart
  const chartData = history.map((h, i) => ({
    name: `Q${i + 1}`,
    Faithfulness: h.faithfulness * 100,
    'Answer Relevancy': h.answer_relevancy * 100,
    'Context Relevance': h.context_relevance * 100,
  }));

  const latencyChartData = history.map((h, i) => ({
    name: `Q${i + 1}`,
    'TTFT (s)': h.latency_ttft,
    'Total (s)': h.latency_total,
  }));

  return (
    <div className="chat-container" style={{ maxWidth: '1000px', overflowY: 'auto', paddingBottom: '2rem' }}>
      <div className="chat-header">
        <button className="chat-header-back" onClick={() => router.push(`/chat?doc_ids=${docIdsParam}`)}>
          ← Back to Chat
        </button>
        <span className="chat-header-title" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>System Metrics</span>
      </div>

      <div style={{ padding: '2rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          <div style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Avg Faithfulness</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>
              {averages?.faithfulness !== undefined ? (averages.faithfulness * 100).toFixed(1) + '%' : 'N/A'}
            </div>
          </div>
          <div style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Avg Answer Relevancy</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>
              {averages?.answer_relevancy !== undefined ? (averages.answer_relevancy * 100).toFixed(1) + '%' : 'N/A'}
            </div>
          </div>
          <div style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Avg Context Relevance</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>
              {averages?.context_relevance !== undefined ? (averages.context_relevance * 100).toFixed(1) + '%' : 'N/A'}
            </div>
          </div>
          <div style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Avg Time to First Token</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>
              {averages?.latency_ttft !== undefined ? averages.latency_ttft.toFixed(2) + 's' : 'N/A'}
            </div>
          </div>
        </div>

        {history.length > 0 ? (
          <>
            <h3 style={{ marginBottom: '1rem' }}>Quality Trends over Time</h3>
            <div style={{ width: '100%', height: 300, background: 'var(--surface)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', marginBottom: '2rem' }}>
              <ResponsiveContainer>
                <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" />
                  <YAxis stroke="var(--text-muted)" domain={[0, 100]} />
                  <Tooltip contentStyle={{ background: 'var(--bg)', border: '1px solid var(--border)' }} />
                  <Legend />
                  <Line type="monotone" dataKey="Faithfulness" stroke="#ffffff" strokeWidth={2} />
                  <Line type="monotone" dataKey="Answer Relevancy" stroke="#a3a3a3" strokeWidth={2} />
                  <Line type="monotone" dataKey="Context Relevance" stroke="#737373" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <h3 style={{ marginBottom: '1rem' }}>Latency Trends over Time</h3>
            <div style={{ width: '100%', height: 300, background: 'var(--surface)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', marginBottom: '2rem' }}>
              <ResponsiveContainer>
                <LineChart data={latencyChartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" />
                  <YAxis stroke="var(--text-muted)" />
                  <Tooltip contentStyle={{ background: 'var(--bg)', border: '1px solid var(--border)' }} />
                  <Legend />
                  <Line type="monotone" dataKey="TTFT (s)" stroke="#ffffff" strokeWidth={2} />
                  <Line type="monotone" dataKey="Total (s)" stroke="#a3a3a3" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <h3 style={{ marginBottom: '1rem' }}>Question-wise Log</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '3rem' }}>
              {history.map((h, i) => (
                <div key={i} style={{ background: 'var(--surface)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Q: {h.question}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>A: {h.answer_preview}</div>
                  <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem', color: 'var(--text-light)', flexWrap: 'wrap' }}>
                    <span>TTFT: {h.latency_ttft?.toFixed(2)}s</span>
                    <span>|</span>
                    <span>Total: {h.latency_total?.toFixed(2)}s</span>
                    <span>|</span>
                    <span>Faithful: {(h.faithfulness * 100).toFixed(0)}%</span>
                    <span>|</span>
                    <span>Relevancy: {(h.answer_relevancy * 100).toFixed(0)}%</span>
                    <span>|</span>
                    <span>Context: {(h.context_relevance * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
            No metrics recorded yet. Ask a question in the chat to generate metrics! (Metrics may take a few seconds to calculate in the background).
          </div>
        )}

        <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid var(--border)' }}>
          <h3 style={{ marginBottom: '1rem' }}>Metric Definitions</h3>
          <ul style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: '1rem', paddingLeft: '1.2rem' }}>
            <li>
              <strong style={{ color: 'var(--text)' }}>Time to Answer (Latency):</strong> Operational metric. You can easily track Time to First Token (TTFT) (crucial for streaming UX) and Total Generation Time.
            </li>
            <li>
              <strong style={{ color: 'var(--text)' }}>Faithfulness (Hallucination Index):</strong> Can be measured without ground truth. This evaluates: Is the generated answer entirely derived from the retrieved context? The LLM judge looks at the Answer and Context and penalizes any claims made in the answer that aren't supported by the context.
            </li>
            <li>
              <strong style={{ color: 'var(--text)' }}>Answer Relevancy:</strong> Can be measured without ground truth. This evaluates: Does the answer directly address the user's question? The LLM judge looks at the Question and Answer to ensure the response isn't evasive or off-topic.
            </li>
            <li>
              <strong style={{ color: 'var(--text)' }}>Context Precision / Relevance:</strong> Can be measured without ground truth. This evaluates: Did the retrieval system fetch useful information? The LLM judge looks at the Question and Context and scores how much of the retrieved text is actually useful versus just noise.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function MetricsPage() {
  return (
    <Suspense fallback={<div style={{ padding: '2rem', textAlign: 'center' }}>Loading metrics...</div>}>
      <MetricsContent />
    </Suspense>
  );
}
