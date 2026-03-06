import type { ClientProduct } from '@/lib/types';
import {
  isEventProductType,
  isProductActive,
  resolveMinPackagePrice,
} from '../events/event-products';

export type PublicProductRow = {
  id: number;
  name: string;
  shortDescription: string;
  typeName: string;
  priceLabel: string;
};

export const buildPublicProductRows = (
  products: ClientProduct[],
  rubFormatter: Intl.NumberFormat,
): PublicProductRow[] => {
  return products
    .filter((product) => isProductActive(product))
    .filter((product) => !isEventProductType(product))
    .map((product) => {
      const minPackagePrice = resolveMinPackagePrice(product);
      return {
        id: product.id,
        name: (product.name || '').trim() || `Продукт #${product.id}`,
        shortDescription: (product.short_description || '').trim(),
        typeName: (product.product_type_name || product.product_type?.name || '').trim() || 'Без типа',
        priceLabel: minPackagePrice !== null ? `от ${rubFormatter.format(minPackagePrice)}` : '',
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'));
};
