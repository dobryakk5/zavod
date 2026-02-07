export function Alert({ children, variant = 'info' }) {
  const variantClass = {
    info: 'bg-blue-50 text-blue-900 border-blue-200',
    error: 'bg-red-50 text-red-900 border-red-200',
    warning: 'bg-amber-50 text-amber-900 border-amber-200',
    success: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  }[variant];

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${variantClass}`}>
      {children}
    </div>
  );
}
