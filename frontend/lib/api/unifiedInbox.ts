import { apiFetch } from '../api';

export type UnifiedInboxChannel = 'telegram' | 'whatsapp' | 'email' | 'vk' | 'instagram';
export type UnifiedInboxInquiryType = 'support' | 'sales' | 'payment' | 'documents' | 'feedback';
export type UnifiedInboxServiceLevel = 'critical' | 'high' | 'normal' | 'low';
export type UnifiedInboxThreadStatus = 'new' | 'in_progress' | 'waiting_client' | 'closed';
export type UnifiedInboxSlaState = 'breached' | 'risk' | 'ok';
export type UnifiedInboxMessageDirection = 'in' | 'out';

export type UnifiedInboxThreadMessage = {
  id: string;
  channel: UnifiedInboxChannel;
  direction: UnifiedInboxMessageDirection;
  author: string;
  text: string;
  createdAtLabel: string;
  createdAtSort: number;
};

export type UnifiedInboxClientChannelHandle = {
  channel: UnifiedInboxChannel;
  handle: string;
};

export type UnifiedInboxClientCard = {
  id: number;
  name: string;
  company?: string | null;
  manager: string;
  phone?: string | null;
  email?: string | null;
  tags: string[];
  channels: UnifiedInboxClientChannelHandle[];
  notes?: string | null;
};

export type UnifiedInboxThread = {
  id: string;
  sourceChannel: UnifiedInboxChannel;
  inquiryType: UnifiedInboxInquiryType;
  serviceLevel: UnifiedInboxServiceLevel;
  slaState: UnifiedInboxSlaState;
  slaDeadlineLabel: string;
  status: UnifiedInboxThreadStatus;
  unreadCount: number;
  client: UnifiedInboxClientCard;
  subject: string;
  lastMessagePreview: string;
  lastMessageAtLabel: string;
  lastMessageSort: number;
  messages: UnifiedInboxThreadMessage[];
};

export type UnifiedInboxSourceInfo = {
  enabled: boolean;
  thread_count: number;
  reason?: string;
};

export type UnifiedInboxResponse = {
  threads: UnifiedInboxThread[];
  sources?: {
    telegram?: UnifiedInboxSourceInfo;
    vk?: UnifiedInboxSourceInfo;
    email?: UnifiedInboxSourceInfo;
  };
  counts?: Record<string, number>;
};

export type UnifiedInboxReplyRequest = {
  thread_id: string;
  channel: UnifiedInboxChannel;
  text: string;
  contact_id?: number;
};

export type UnifiedInboxReplyResponse = {
  ok: boolean;
  thread_id: string;
  channel: UnifiedInboxChannel;
  message: UnifiedInboxThreadMessage;
};

export const unifiedInboxApi = {
  list() {
    return apiFetch<UnifiedInboxResponse>('/client/unified-inbox/');
  },
  reply(payload: UnifiedInboxReplyRequest) {
    return apiFetch<UnifiedInboxReplyResponse>('/client/unified-inbox/reply/', {
      method: 'POST',
      body: payload,
    });
  },
};
