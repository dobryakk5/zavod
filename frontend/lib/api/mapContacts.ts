import {
  crmContactTagsApi,
  crmContactsApi,
  type Contact,
} from './crm';

export type MapClient = Contact;

type Id = number | string;

const toNumericId = (value: Id): number => (typeof value === 'number' ? value : Number(value));

// DEPRECATED: use `@/lib/api/crm` (`crmContactsApi`, `crmContactTagsApi`) directly.
// Kept as a compatibility alias while legacy imports are being removed.
export const mapContactsApi = {
  list: async (): Promise<MapClient[]> => {
    return crmContactsApi.list();
  },

  detail: async (id: Id): Promise<MapClient> => {
    return crmContactsApi.detail(id);
  },

  create: async (payload: { name: string }) => {
    return crmContactsApi.create({ name: payload.name });
  },

  update: async (id: Id, payload: { name: string }) => {
    return crmContactsApi.update(id, { name: payload.name });
  },

  delete: async (id: Id) => {
    return crmContactsApi.delete(id);
  }
};

export const contactTagsApi = {
  assign: async (contactId: Id, tagId: Id) => {
    return crmContactTagsApi.create({
      contact_id: toNumericId(contactId),
      tag_id: toNumericId(tagId),
    });
  },

  remove: async (contactId: Id, tagId: Id) => {
    return crmContactTagsApi.delete({
      contact_id: toNumericId(contactId),
      tag_id: toNumericId(tagId),
    });
  }
};
