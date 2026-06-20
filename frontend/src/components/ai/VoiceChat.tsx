'use client';

import { useState, useRef, useEffect } from 'react';

type SpeechRecognition = any;

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

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
  const browserName =
    /Chrome/.test(ua) ? 'Chrome' :
    /Firefox/.test(ua) ? 'Firefox' :
    /Safari/.test(ua) ? 'Safari' : 'Browser';

  const stt = !!(
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition
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
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SR) return;

    setError('');

    const rec = new SR();
    rec.lang = 'hi-IN';
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    rec.onresult = (e: any) =>
      setTextInput(e.results[0][0].transcript);

    rec.onerror = (e: any) => {
      setListening(false);
      setError(`Mic error: ${e.error}. Try typing instead.`);
    };

    rec.onend = () => setListening(false);

    rec.start();
    recRef.current = rec;
    setListening(true);
  };

  const stopListening = () => {
    recRef.current?.stop();
    setListening(false);
  };

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

    const newMsgs: Message[] = [
      ...messages,
      { role: 'user', text: question, lang: userLang },
    ];

    setMessages(newMsgs);
    setTextInput('');
    setLoading(true);
    setError('');

    try {
      const base =
        apiBase ||
        process.env.NEXT_PUBLIC_API_BASE_URL ||
        'http://127.0.0.1:8000';

      const res = await fetch(`${base}/voice-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          store_context: storeContext,
        }),
      });

      if (!res.ok) throw new Error(`Server error ${res.status}`);

      const data = await res.json();
      const answer = data.answer || 'Could not get a response.';

      const ansLang: 'hi' | 'en' = isHindi(answer) ? 'hi' : 'en';

      setMessages([
        ...newMsgs,
        { role: 'assistant', text: answer, lang: ansLang },
      ]);

      speakText(answer, ansLang);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to reach AI agent'
      );
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

      <div style={{ padding: '12px 18px', background: 'rgba(99,102,241,0.04)', borderBottom: '1px solid rgba(99,102,241,0.1)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 26, height: 26, borderRadius: 8, background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>🎤</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Voice Assistant</div>
          <div style={{ fontSize: 11, color: '#666' }}>
            Hindi + English
          </div>
        </div>
        {speaking && <div style={{ marginLeft: 'auto' }}>🔊 Speaking...</div>}
      </div>

      <div style={{ padding: 16, minHeight: 160, maxHeight: 300, overflowY: 'auto' }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 10 }}>
            <b>{msg.role}:</b> {msg.text}
          </div>
        ))}

        {loading && <div>Thinking...</div>}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ display: 'flex', gap: 8, padding: 10 }}>
        <button onClick={listening ? stopListening : startListening}>
          🎤
        </button>

        <input
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && askQuestion(textInput)}
          placeholder="Type or speak..."
          style={{ flex: 1 }}
        />

        <button onClick={() => askQuestion(textInput)}>
          ➤
        </button>
      </div>

      {error && (
        <div style={{ color: 'red', padding: 8 }}>{error}</div>
      )}
    </div>
  );
}
