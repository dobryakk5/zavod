// ═══════════════════════════════════════════════════════════════════════════
// Label Component - Shared form label
// ═══════════════════════════════════════════════════════════════════════════

type LabelProps = {
  children: React.ReactNode;
  className?: string;
  htmlFor?: string;
};

export function Label({ children, className = '', htmlFor }: LabelProps) {
  return (
    <label 
      htmlFor={htmlFor}
      className={`block text-sm font-medium text-slate-700 mb-1.5 ${className}`}
    >
      {children}
    </label>
  );
}
