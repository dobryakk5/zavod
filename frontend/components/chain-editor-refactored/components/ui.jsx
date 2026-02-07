// ═══════════════════════════════════════════════════════════════════════════
// UI PRIMITIVES (shadcn/ui inspired)
// ═══════════════════════════════════════════════════════════════════════════

export function Card({ children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ children }) {
  return <div className="px-6 py-4 border-b border-slate-100">{children}</div>;
}

export function CardTitle({ children }) {
  return <h3 className="text-lg font-semibold text-slate-900">{children}</h3>;
}

export function CardContent({ children }) {
  return <div className="p-6">{children}</div>;
}

export function CardFooter({ children, className = '' }) {
  return (
    <div className={`px-6 py-4 border-t border-slate-100 flex items-center justify-between ${className}`}>
      {children}
    </div>
  );
}

export function Button({ children, onClick, disabled, variant = 'primary', size = 'md', className = '' }) {
  const baseClass = 'inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';
  const variantClass = {
    primary: 'bg-slate-900 text-white hover:bg-slate-800 focus:ring-slate-900',
    outline: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-slate-500',
    ghost:   'text-slate-700 hover:bg-slate-100 focus:ring-slate-500',
    danger:  'bg-red-600 text-white hover:bg-red-700 focus:ring-red-600',
  }[variant];
  const sizeClass = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  }[size];

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseClass} ${variantClass} ${sizeClass} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
    >
      {children}
    </button>
  );
}

export function Input({ value, onChange, onBlur, placeholder, className = '', type = 'text', ...props }) {
  return (
    <input
      type={type}
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      placeholder={placeholder}
      className={`w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent ${className}`}
      {...props}
    />
  );
}

export function Label({ children, className = '' }) {
  return <label className={`block text-sm font-medium text-slate-700 mb-1.5 ${className}`}>{children}</label>;
}

export function Select({ value, onChange, options, className = '' }) {
  return (
    <select
      value={value}
      onChange={onChange}
      className={`w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 bg-white ${className}`}
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export function Dialog({ open, onClose, children }) {
  if (!open) return null;
  return (
    <>
      <div onClick={onClose} className="fixed inset-0 bg-black/50 z-40" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          {children}
        </div>
      </div>
    </>
  );
}

export function DialogHeader({ children }) {
  return <div className="px-6 py-4 border-b border-slate-100">{children}</div>;
}

export function DialogTitle({ children }) {
  return <h2 className="text-xl font-semibold text-slate-900">{children}</h2>;
}

export function DialogContent({ children }) {
  return <div className="px-6 py-4">{children}</div>;
}

export function DialogFooter({ children }) {
  return <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3">{children}</div>;
}
