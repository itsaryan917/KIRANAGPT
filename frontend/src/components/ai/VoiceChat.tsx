'use client';

import { useState, useRef, useEffect } from 'react';

interface Props {
  storeContext: Record<string, unknown>;
  apiBase?: string;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
  lang: 'hi' | 'en';
}

function isHindi(text: string): boolean {
  return /[\u0900-\u097F]/.test(text);
}

function detectSpeechSupport(): { stt: boolean; tts: boolean; browserName: string } {
  if (typeof window === 'undefined') return { stt: false, tts: false, browserName: 'Unknown' };
  const ua = navigator.userAgent;
  const browserName = /Chrome/.test(ua) ? 'Chrome' : /Firefox/.test(ua) ? 'Firefox' : /Safari/.test(ua) ? 'Safari' : 'Browser';
  const stt = !!(
    (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition ||
    (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition
  );
  const tts = typeof window.speechSynthesis !== 'undefined';
  return { stt, tts, browserName };
}

export function VoiceChat({ storeContext, apiBase = '' }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [error, setError] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const [support, setSupport] = useState({ stt: true, tts: true, browserName: 'Chrome' });
  const recRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSupport(detectSpeechSupport());
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startListening = () => {
    if (!support.stt) return;
    const SR =
      (window as unknown as { SpeechRecognition?: typeof SpeechRecognition }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition;
    if (!SR) return;
    setError('');
    const rec = new SR();
    rec.lang = 'hi-IN';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => setTextInput(e.results[0][0].transcript);
    rec.onerror = (e) => { setListening(false); setError(`Mic error: ${e.error}. Try typing instead.`); };
    rec.onend = () => setListening(false);
    rec.start();
    recRef.current = rec;
    setListening(true);
  };

  const stopListening = () => { recRef.current?.stop(); setListening(false); };

  const speakText = (text: string, lang: 'hi' | 'en') => {
    if (!support.tts || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = lang === 'hi' ? 'hi-IN' : 'en-IN';
    utt.rate = 0.9;
    utt.onstart = () => setSpeaking(true);
    utt.onend = () => setSpeaking(false);
    window.speechSynthesis.speak(utt);
  };

  const askQuestion = async (question: string) => {
    if (!question.trim()) return;
    const userLang: 'hi' | 'en' = isHindi(question) ? 'hi' : 'en';
    const newMsgs = [...messages, { role: 'user' as const, text: question, lang: userLang }];
    setMessages(newMsgs);
    setTextInput('');
    setLoading(true);
    setError('');

    try {
      const base = apiBase || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${base}/voice-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, store_context: storeContext }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      const answer = data.answer || 'Could not get a response.';
      const ansLang: 'hi' | 'en' = isHindi(answer) ? 'hi' : 'en';
      setMessages([...newMsgs, { role: 'assistant', text: answer, lang: ansLang }]);
      speakText(answer, ansLang);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reach AI agent');
    } finally {
      setLoading(false);
    }
  };

  const QUICK = [
    'मेरा लोन क्यों रिजेक्ट हुआ?',
    'How can I improve my score?',
    'मुझे कितना लोन मिल सकता है?',
  ];

  return (
    <div style={{ marginTop: 24, border: '1px solid rgba(99,102,241,0.15)', borderRadius: 14, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '12px 18px', background: 'rgba(99,102,241,0.04)', borderBottom: '1px solid rgba(99,102,241,0.1)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 26, height: 26, borderRadius: 8, background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>🎤</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Voice Assistant</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Hindi + English · Ask anything about your assessment
            {!support.stt && <span style={{ color: 'var(--warning)', marginLeft: 6 }}>· Mic not available in {support.browserName} — text only</span>}
          </div>
        </div>
        {speaking && <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--accent)' }}>🔊 Speaking...</div>}
      </div>

      {/* No STT banner */}
      {!support.stt && (
        <div style={{ padding: '8px 18px', background: '#fffbeb', borderBottom: '1px solid rgba(245,158,11,0.2)', fontSize: 12, color: '#92400e', display: 'flex', gap: 8 }}>
          <span>⚠</span>
          <span>
            Voice input requires <strong>Chrome or Edge</strong>. You can still type questions in Hindi or English below.
          </span>
        </div>
      )}

      {/* Messages */}
      <div style={{ background: 'var(--bg-card)', padding: '16px 18px', minHeight: messages.length > 0 ? 160 : 0, maxHeight: 300, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>🎙️</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Ask in Hindi or English — tap a suggestion below</div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', gap: 8 }}>
              {msg.role === 'assistant' && (
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, flexShrink: 0 }}>🤖</div>
              )}
              <div style={{
                maxWidth: '75%', padding: '10px 14px',
                borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                background: msg.role === 'user' ? 'var(--accent)' : 'var(--bg-elevated)',
                color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                fontSize: 13, lineHeight: 1.6,
              }}>
                {msg.text}
                {msg.role === 'assistant' && support.tts && (
                  <button onClick={() => speakText(msg.text, msg.lang)} style={{ display: 'block', marginTop: 4, background: 'none', border: 'none', fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}>
                    🔊 Replay
                  </button>
                )}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>🤖</div>
            <div style={{ padding: '10px 14px', background: 'var(--bg-elevated)', borderRadius: '14px 14px 14px 4px', fontSize: 13, color: 'var(--text-muted)' }}>Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick questions */}
      {messages.length === 0 && (
        <div style={{ padding: '8px 18px', background: 'var(--bg-secondary)', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {QUICK.map((q, i) => (
            <button key={i} onClick={() => askQuestion(q)} style={{ padding: '4px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 16, fontSize: 11, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div style={{ padding: '10px 14px', background: 'var(--bg-elevated)', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, alignItems: 'center' }}>
        {support.stt && (
          <button
            onClick={listening ? stopListening : startListening}
            style={{
              width: 38, height: 38, borderRadius: '50%',
              background: listening ? 'var(--danger)' : 'var(--accent)',
              border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', flexShrink: 0,
              animation: listening ? 'pulse-glow 1.5s infinite' : 'none',
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
              {listening
                ? <rect x="6" y="6" width="12" height="12" rx="2" />
                : <><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"/></>
              }
            </svg>
          </button>
        )}
        <input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && askQuestion(textInput)}
          placeholder={listening ? 'Listening...' : support.stt ? 'Type or use mic (Hindi / English)' : 'Type in Hindi or English...'}
          style={{ flex: 1, padding: '9px 14px', borderRadius: 20, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text-primary)', fontSize: 13, outline: 'none' }}
        />
        <button
          onClick={() => askQuestion(textInput)}
          disabled={loading || !textInput.trim()}
          style={{ width: 38, height: 38, borderRadius: '50%', background: textInput.trim() ? 'var(--accent)' : 'var(--bg-elevated)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: textInput.trim() ? 'pointer' : 'default', flexShrink: 0 }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={textInput.trim() ? '#fff' : 'var(--text-muted)'} strokeWidth="2">
            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>

      {error && (
        <div style={{ padding: '6px 18px', fontSize: 11, color: 'var(--danger)', background: 'var(--danger-bg)', borderTop: '1px solid var(--border)' }}>
          {error}
        </div>
      )}
    </div>
  );
}
