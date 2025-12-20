'use client';

import { Loader2 } from 'lucide-react';

export default function LoadingWordstatDetail() {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground p-4">
      <Loader2 className="h-4 w-4 animate-spin" />
      Загружаем Wordstat...
    </div>
  );
}
