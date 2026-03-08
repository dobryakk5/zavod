export type PaymentProvider = 'yookassa' | 'tbank';

export const PAYMENT_PROVIDER_LABELS: Record<PaymentProvider, string> = {
  yookassa: 'YooKassa',
  tbank: 'T-Bank',
};

export type PublicBuyProductResponse = {
  id?: string;
  payment_url?: string;
  confirmation_url?: string;
};

export type PublicProductPaymentStatusResponse = {
  payment_id?: string;
  provider?: PaymentProvider | string;
  status?: string;
  paid?: boolean;
  delivery?: {
    ready?: boolean;
    url?: string;
    document_title?: string;
    course_title?: string;
    message?: string;
    missing_course?: boolean;
  } | null;
};

export const resolvePackagePrice = (raw: unknown): number | null => {
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return raw > 0 ? raw : null;
  }
  if (typeof raw === 'string') {
    const parsed = Number.parseFloat(raw.replace(',', '.'));
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return null;
};

export const parseResponseDetail = (rawText: string): string => {
  if (!rawText.trim()) {
    return '';
  }
  try {
    const parsed = JSON.parse(rawText) as { detail?: unknown };
    const detail = String(parsed?.detail ?? '').trim();
    return detail;
  } catch {
    return '';
  }
};
