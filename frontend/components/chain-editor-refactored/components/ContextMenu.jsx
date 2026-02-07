export function ContextMenu({ pos, items, onClose }) {
  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-30" />
      <div
        className="fixed z-40 bg-white border border-slate-200 rounded-lg shadow-xl min-w-[180px] overflow-hidden"
        style={{ left: pos.x, top: pos.y }}
      >
        {items.map((it, i) => (
          <button
            key={i}
            onClick={() => {
              it.action();
              onClose();
            }}
            className="block w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b border-slate-100 last:border-0"
          >
            {it.label}
          </button>
        ))}
      </div>
    </>
  );
}
