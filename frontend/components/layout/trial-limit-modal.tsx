'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  TRIAL_LIMIT_MESSAGE,
  TRIAL_LIMIT_PAYMENT_URL,
  emitTrialLimitModalOpen,
  isTrialLimitMessage,
  parseTrialLimitDetails,
  subscribeToTrialLimitModalOpen,
} from '@/lib/trial-limit';

let isToastPatched = false;
let originalToastError: typeof toast.error | null = null;

export function TrialLimitModal() {
  const [open, setOpen] = useState(false);
  const [details, setDetails] = useState<{
    label?: string;
    used?: number;
    limit?: number;
    message?: string;
  } | null>(null);

  useEffect(() => {
    const unsubscribe = subscribeToTrialLimitModalOpen((detail) => {
      setDetails(detail ?? null);
      setOpen(true);
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (isToastPatched) {
      return;
    }

    originalToastError = toast.error;
    toast.error = ((...args) => {
      const [message] = args;
      if (isTrialLimitMessage(message)) {
        emitTrialLimitModalOpen(parseTrialLimitDetails(message) ?? { message: String(message) });
        return '';
      }
      return originalToastError?.(...args) ?? '';
    }) as typeof toast.error;
    isToastPatched = true;

    return () => {
      if (originalToastError) {
        toast.error = originalToastError;
      }
      isToastPatched = false;
    };
  }, []);

  const summary =
    details?.label && details.used !== undefined && details.limit !== undefined
      ? `${details.label} ${details.used}/${details.limit}`
      : details?.message;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="bg-white text-gray-900 dark:bg-white dark:text-gray-900">
        <DialogHeader>
          <DialogTitle>{TRIAL_LIMIT_MESSAGE}</DialogTitle>
          {summary ? <DialogDescription className="text-gray-600">{summary}</DialogDescription> : null}
        </DialogHeader>
        <div className="text-sm">
          <Link
            className="text-primary underline underline-offset-4"
            href={TRIAL_LIMIT_PAYMENT_URL}
            onClick={() => setOpen(false)}
          >
            Получить безлимит
          </Link>
        </div>
      </DialogContent>
    </Dialog>
  );
}
