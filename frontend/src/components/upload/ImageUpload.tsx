'use client';

import { useCallback, useRef, useState } from 'react';

const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp', 'image/heic'];
const MAX_SIZE_MB = 10;

// Each slot is locked to a specific view — user must upload to the correct slot
const SLOTS = [
  {
    key: 'front',
    label: 'Front',
    fullLabel: 'Store Exterior / Front',
    icon: '🏪',
    hint: 'Street view, signage, entrance',
    critical: false,
  },
  {
    key: 'billing_area',
    label: 'Counter',
    fullLabel: 'Billing / Counter Area',
    icon: '🧾',
    hint: 'POS counter, cash desk',
    critical: false,
  },
  {
    key: 'left_wall',
    label: 'Left Wall',
    fullLabel: 'Left Interior Shelves',
    icon: '◧',
    hint: 'Left side shelf wall',
    critical: false,
  },
  {
    key: 'centre_wall',
    label: 'Centre Wall',
    fullLabel: 'Centre / Back Wall ★',
    icon: '▣',
    hint: 'Main shelf — used for Shelf Density Index',
    critical: true,   // most important for SDI
  },
  {
    key: 'right_wall',
    label: 'Right Wall',
    fullLabel: 'Right Interior Shelves',
    icon: '◨',
    hint: 'Right side shelf wall',
    critical: false,
  },
];

export type SlotImages = { [key: string]: File | null };

interface ImageUploadProps {
  // Returns ordered File[] matching slot order (index 0=front … 4=right_wall)
  images: File[];
  onChange: (files: File[]) => void;
}

export function ImageUpload({ images, onChange }: ImageUploadProps) {
  // Internal state: keyed by slot name so order is always correct
  const [slotMap, setSlotMap] = useState<SlotImages>(() => {
    const m: SlotImages = {};
    SLOTS.forEach((s, i) => { m[s.key] = images[i] ?? null; });
    return m;
  });
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const inputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({});

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED.includes(file.type) && !file.name.toLowerCase().endsWith('.heic')) {
      return `"${file.name}" is not a supported image type (JPEG/PNG/WebP/HEIC)`;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      return `"${file.name}" exceeds ${MAX_SIZE_MB}MB limit`;
    }
    return null;
  };

  const handleSlotFile = useCallback(
    (slotKey: string, file: File) => {
      const err = validateFile(file);
      if (err) {
        setErrors(prev => ({ ...prev, [slotKey]: err }));
        return;
      }
      setErrors(prev => { const n = { ...prev }; delete n[slotKey]; return n; });
      const newMap = { ...slotMap, [slotKey]: file };
      setSlotMap(newMap);
      // Always emit in SLOT order so backend receives images in correct sequence
      onChange(SLOTS.map(s => newMap[s.key]).filter(Boolean) as File[]);
    },
    [slotMap, onChange]
  );

  const handleRemove = useCallback(
    (slotKey: string) => {
      const newMap = { ...slotMap, [slotKey]: null };
      setSlotMap(newMap);
      setErrors(prev => { const n = { ...prev }; delete n[slotKey]; return n; });
      onChange(SLOTS.map(s => newMap[s.key]).filter(Boolean) as File[]);
      // Reset file input
      if (inputRefs.current[slotKey]) {
        inputRefs.current[slotKey]!.value = '';
      }
    },
    [slotMap, onChange]
  );

  const filledCount = SLOTS.filter(s => slotMap[s.key] !== null).length;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--accent-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          </div>
          <label style={{ fontWeight: 600, fontSize: 14 }}>
            Store Images
            <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 12, marginLeft: 6 }}>
              (Upload each view to the correct slot)
            </span>
          </label>
        </div>
        <span style={{
          fontSize: 12, fontWeight: 600,
          color: filledCount === 5 ? 'var(--success)' : 'var(--text-muted)',
          background: filledCount === 5 ? 'var(--success-bg)' : 'var(--bg-elevated)',
          padding: '3px 10px', borderRadius: 20,
          border: `1px solid ${filledCount === 5 ? 'rgba(16,185,129,0.3)' : 'var(--border)'}`,
        }}>
          {filledCount} / 5
        </span>
      </div>

      {/* Slot grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 10 }}>
        {SLOTS.map((slot) => {
          const file = slotMap[slot.key];
          const hasError = !!errors[slot.key];

          return (
            <div key={slot.key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {/* Image box */}
              <div
                onClick={() => !file && inputRefs.current[slot.key]?.click()}
                style={{
                  aspectRatio: '1',
                  border: `2px ${file ? 'solid' : 'dashed'} ${
                    file ? 'var(--success)' : hasError ? 'var(--danger)' : slot.critical ? 'var(--accent)' : 'var(--border-bright)'
                  }`,
                  borderRadius: 10,
                  overflow: 'hidden',
                  position: 'relative',
                  background: file ? 'transparent' : slot.critical ? 'rgba(99,102,241,0.04)' : 'var(--bg-elevated)',
                  cursor: file ? 'default' : 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                {file ? (
                  <>
                    <img
                      src={URL.createObjectURL(file)}
                      alt={slot.fullLabel}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                    {/* Checkmark */}
                    <div style={{
                      position: 'absolute', top: 5, right: 5, width: 20, height: 20,
                      borderRadius: '50%', background: 'var(--success)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      boxShadow: '0 2px 6px rgba(16,185,129,0.4)',
                    }}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    {/* Remove */}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRemove(slot.key); }}
                      style={{
                        position: 'absolute', top: 5, left: 5, background: 'rgba(239,68,68,0.9)',
                        color: '#fff', border: 'none', borderRadius: '50%', width: 20, height: 20,
                        cursor: 'pointer', fontSize: 14, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', lineHeight: 1,
                      }}
                    >×</button>
                    {/* File name overlay */}
                    <div style={{
                      position: 'absolute', bottom: 0, left: 0, right: 0,
                      background: 'rgba(0,0,0,0.55)', padding: '3px 5px',
                      fontSize: 9, color: '#fff', textAlign: 'center',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {file.name}
                    </div>
                  </>
                ) : (
                  <div style={{ textAlign: 'center', paddingTop: '22%', paddingLeft: 4, paddingRight: 4 }}>
                    <div style={{ fontSize: 20, marginBottom: 4 }}>{slot.icon}</div>
                    <div style={{ fontSize: 9, fontWeight: 700, color: slot.critical ? 'var(--accent)' : 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      Tap to upload
                    </div>
                  </div>
                )}
              </div>

              {/* Hidden input per slot */}
              <input
                ref={el => { inputRefs.current[slot.key] = el; }}
                type="file"
                accept={ACCEPTED.join(',')}
                style={{ display: 'none' }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleSlotFile(slot.key, f);
                }}
              />

              {/* Slot label */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                  {slot.critical && (
                    <span style={{ fontSize: 9, background: 'var(--accent)', color: '#fff', padding: '1px 5px', borderRadius: 3, fontWeight: 700 }}>
                      SDI
                    </span>
                  )}
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {slot.label}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.3 }}>
                  {slot.hint}
                </div>
                {errors[slot.key] && (
                  <div style={{ fontSize: 10, color: 'var(--danger)', marginTop: 2 }}>
                    {errors[slot.key]}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Centre wall reminder */}
      <div style={{
        marginTop: 12, padding: '8px 12px',
        background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(99,102,241,0.12)',
        borderRadius: 8, fontSize: 11, color: 'var(--text-secondary)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span>★</span>
        <span><strong>Centre Wall</strong> is the most important image — it drives the Shelf Density Index (SDI) which determines the revenue estimate.</span>
      </div>
    </div>
  );
}
