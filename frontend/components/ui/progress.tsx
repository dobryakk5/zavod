'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
  max?: number;
  intent?: 'default' | 'error';
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value = 0, max = 100, intent = 'default', ...props }, ref) => {
    const percentage = Math.min(100, Math.max(0, (value / max) * 100));
    
    return (
      <div
        ref={ref}
        className={cn(
          'relative w-full overflow-hidden rounded-full bg-gray-200',
          className
        )}
        {...props}
      >
        <div
          className={cn(
            'h-2 w-full flex-1 transition-all',
            intent === 'error' ? 'bg-white' : 'bg-blue-600'
          )}
          style={{ transform: `translateX(-${100 - percentage}%)` }}
        />
      </div>
    );
  }
);
Progress.displayName = 'Progress';

export { Progress };
