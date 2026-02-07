export function ContextMenu({ pos, items, onClose }) {
  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-40" />
      <div 
        style={{ position: "fixed", left: pos.x, top: pos.y }} 
        className="bg-white border border-slate-200 rounded-lg shadow-xl z-50 py-1 min-w-[180px]"
      >
        {items.map((item, i) => (
          <button
            key={i}
            onClick={() => { item.action(); onClose(); }}
            className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
          >
            {item.label}
          </button>
        ))}
      </div>
    </>
  );
}
