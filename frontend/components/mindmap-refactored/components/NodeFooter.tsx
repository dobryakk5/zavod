import Link from 'next/link';
import { ExternalLink, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CardFooter } from '@/components/ui/card';

// ═══════════════════════════════════════════════════════════════════════════
// NodeFooter Component - Actions footer
// ═══════════════════════════════════════════════════════════════════════════

type NodeFooterProps = {
  productId: number | null;
  saving: boolean;
  loading: boolean;
  onSave: () => void;
};

export function NodeFooter({ 
  productId, 
  saving, 
  loading, 
  onSave 
}: NodeFooterProps) {
  return (
    <CardFooter className="border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
      {productId ? (
        <Button 
          asChild 
          variant="ghost" 
          size="sm" 
          className="text-slate-700 hover:bg-white"
        >
          <Link href={`/product/${productId}`} className="inline-flex items-center gap-2">
            Открыть продукт
            <ExternalLink className="h-3 w-3" />
          </Link>
        </Button>
      ) : (
        <span />
      )}
      
      <Button
        onClick={onSave}
        disabled={saving || loading}
        className="bg-slate-900 text-white hover:bg-slate-800"
      >
        <Save className="mr-2 h-4 w-4" />
        {saving ? 'Сохранение...' : 'Сохранить все'}
      </Button>
    </CardFooter>
  );
}
