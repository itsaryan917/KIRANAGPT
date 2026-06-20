'use client';

import { useState, useCallback } from 'react';
import { submitUnderwrite } from '../lib/api';
import { saveUnderwritingResult } from '../lib/db';
import type {
  UnderwritingResult,
  GpsCoordinates,
  UploadStatus,
} from '../types/underwriting';

interface UseUnderwriteState {
  status: UploadStatus;
  result: (UnderwritingResult & Record<string, unknown>) | null;
  error: string | null;
}

interface UseUnderwriteReturn extends UseUnderwriteState {
  submit: (
    images: File[],
    gps: GpsCoordinates,
    optional?: { shop_size?: number; rent?: number; years_in_operation?: number },
    useAI?: boolean
  ) => Promise<void>;
  reset: () => void;
}

export function useUnderwrite(): UseUnderwriteReturn {
  const [state, setState] = useState<UseUnderwriteState>({
    status: 'idle',
    result: null,
    error: null,
  });

  const submit = useCallback(
    async (
      images: File[],
      gps: GpsCoordinates,
      optional?: { shop_size?: number; rent?: number; years_in_operation?: number },
      useAI = true
    ) => {
      setState({ status: 'uploading', result: null, error: null });
      await new Promise((r) => setTimeout(r, 600));
      setState((s) => ({ ...s, status: 'analyzing' }));

      const response = await submitUnderwrite({ images, gps, optional, useAI });

      if (!response.success || !response.data) {
        setState({
          status: 'error',
          result: null,
          error: response.error ?? 'Unknown error occurred',
        });
        return;
      }

      try {
        await saveUnderwritingResult(response.data);
      } catch {
        console.warn('[useUnderwrite] Failed to persist to Supabase');
      }

      setState({ status: 'done', result: response.data, error: null });
    },
    []
  );

  const reset = useCallback(() => {
    setState({ status: 'idle', result: null, error: null });
  }, []);

  return { ...state, submit, reset };
}
