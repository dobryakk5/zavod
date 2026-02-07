import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

// ═══════════════════════════════════════════════════════════════════════════
// NodeHeader Component - Navigation and status
// ═══════════════════════════════════════════════════════════════════════════

type NodeHeaderProps = {
  mapId: string;
  saving: boolean;
};

export function NodeHeader({ mapId, saving }: NodeHeaderProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button 
        asChild 
        variant="ghost" 
        size="sm" 
        className="text-slate-700 hover:bg-slate-100"
      >
        <Link href={`/map/${mapId}`} className="inline-flex items-center gap-2">
          <ArrowLeft className="h-4 w-4" />
          Назад к карте
        </Link>
      </Button>

      {saving && (
        <span className="text-sm text-slate-500 animate-pulse">
          💾 Сохранение...
        </span>
      )}
    </div>
  );
}
