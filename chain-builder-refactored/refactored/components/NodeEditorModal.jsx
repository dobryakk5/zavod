import { useState } from "react";
import { CONDITION_LABELS, CONTENT_TYPES } from '../constants';
import { formatTime, uid } from '../utils';

export function NodeEditorModal({ node, onSave, onClose }) {
  const [type, setType] = useState(node.node_type);
  const [contentType, setContentType] = useState(node.payload.content_type || "text");
  const [text, setText] = useState(node.payload.text || "");
  const [url, setUrl] = useState(
    node.payload.url || 
    node.payload.photo_url || 
    node.payload.video_url || 
    node.payload.audio_url || 
    ""
  );
  const [caption, setCaption] = useState(node.payload.caption || "");
  const [buttons, setButtons] = useState((node.payload.buttons || []).join("\n"));
  const [delaySeconds, setDelaySeconds] = useState(node.delay_seconds || 0);
  const [timerDelay, setTimerDelay] = useState(node.payload.delay_seconds || 10);
  const [routes, setRoutes] = useState(node.payload.routes || []);

  const handleSubmit = () => {
    let payload = {};
    
    if (type === "message") {
      payload.content_type = contentType;
      
      if (contentType === "text") {
        payload.text = text;
      } else if (contentType === "photo") {
        payload.photo_url = url;
        payload.caption = caption;
      } else if (contentType === "video") {
        payload.video_url = url;
        payload.caption = caption;
      } else if (contentType === "audio") {
        payload.audio_url = url;
        payload.caption = caption;
      } else if (contentType === "link") {
        payload.url = url;
        payload.text = text;
      } else if (contentType === "buttons") {
        payload.text = text;
        payload.buttons = buttons.split("\n").filter(b => b.trim());
      }
    } else if (type === "timer") {
      payload = { delay_seconds: timerDelay };
    } else if (type === "router") {
      payload = { routes };
    }

    onSave({ 
      node_type: type, 
      payload, 
      delay_seconds: type === "timer" ? 0 : delaySeconds 
    });
  };

  const addRoute = (condType) => {
    const newRoute = { 
      id: uid(), 
      condition_type: condType, 
      params: {} 
    };
    if (condType === "button_press") newRoute.params.button_label = "";
    else if (condType === "text_contains") newRoute.params.text = "";
    else if (condType === "text_regex") newRoute.params.pattern = "";
    else if (condType === "timeout") newRoute.params.seconds = 60;
    setRoutes([...routes, newRoute]);
  };

  const updateRoute = (id, params) => {
    setRoutes(routes.map(r => r.id === id ? { ...r, params } : r));
  };

  const deleteRoute = (id) => {
    setRoutes(routes.filter(r => r.id !== id));
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full mx-4 p-6 max-h-[90vh] overflow-y-auto" 
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-xl font-bold text-slate-900 mb-4">Редактировать узел</h2>

        {/* Node Type Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">Тип узла</label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { type: "message", label: "💬 Сообщение" },
              { type: "router", label: "🔀 Условие" },
              { type: "timer", label: "⏱ Таймер" }
            ].map(t => (
              <button
                key={t.type}
                onClick={() => setType(t.type)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  type === t.type 
                    ? 'bg-slate-900 text-white' 
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Message Editor */}
        {type === "message" && (
          <MessageEditor
            contentType={contentType}
            setContentType={setContentType}
            text={text}
            setText={setText}
            url={url}
            setUrl={setUrl}
            caption={caption}
            setCaption={setCaption}
            buttons={buttons}
            setButtons={setButtons}
          />
        )}

        {/* Timer Editor */}
        {type === "timer" && (
          <TimerEditor
            timerDelay={timerDelay}
            setTimerDelay={setTimerDelay}
          />
        )}

        {/* Router Editor */}
        {type === "router" && (
          <RouterEditor
            routes={routes}
            addRoute={addRoute}
            updateRoute={updateRoute}
            deleteRoute={deleteRoute}
          />
        )}

        {/* Delay Input (for non-timer nodes) */}
        {type !== "timer" && type !== "router" && (
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Задержка перед отправкой (сек)
            </label>
            <input 
              type="number" 
              min="0" 
              value={delaySeconds} 
              onChange={(e) => setDelaySeconds(Number(e.target.value))} 
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-transparent" 
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button 
            onClick={onClose} 
            className="flex-1 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 font-medium"
          >
            Отмена
          </button>
          <button 
            onClick={handleSubmit} 
            className="flex-1 px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 font-medium"
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageEditor({ contentType, setContentType, text, setText, url, setUrl, caption, setCaption, buttons, setButtons }) {
  return (
    <>
      {/* Content Type Selector */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-700 mb-2">Тип контента</label>
        <div className="grid grid-cols-3 gap-2">
          {CONTENT_TYPES.map(ct => (
            <button
              key={ct.type}
              onClick={() => setContentType(ct.type)}
              className={`px-2 py-2 rounded-lg text-xs font-medium transition-all ${
                contentType === ct.type 
                  ? 'bg-teal-600 text-white' 
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {ct.icon} {ct.label}
            </button>
          ))}
        </div>
      </div>

      {/* Text Content */}
      {contentType === "text" && (
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">Текст сообщения</label>
          <textarea 
            value={text} 
            onChange={(e) => setText(e.target.value)} 
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent resize-none" 
            rows={4} 
            placeholder="Введите текст..." 
          />
        </div>
      )}

      {/* Media Content (Photo/Video/Audio) */}
      {(contentType === "photo" || contentType === "video" || contentType === "audio") && (
        <>
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              URL {contentType === "photo" ? "фото" : contentType === "video" ? "видео" : "аудио"}
            </label>
            <input 
              value={url} 
              onChange={(e) => setUrl(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent" 
              placeholder="https://..." 
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">Подпись (необязательно)</label>
            <input 
              value={caption} 
              onChange={(e) => setCaption(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent" 
              placeholder="Текст подписи..." 
            />
          </div>
        </>
      )}

      {/* Link Content */}
      {contentType === "link" && (
        <>
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">URL ссылки</label>
            <input 
              value={url} 
              onChange={(e) => setUrl(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent" 
              placeholder="https://example.com" 
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">Текст ссылки</label>
            <input 
              value={text} 
              onChange={(e) => setText(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent" 
              placeholder="Нажмите здесь" 
            />
          </div>
        </>
      )}

      {/* Buttons Content */}
      {contentType === "buttons" && (
        <>
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">Текст вопроса</label>
            <input 
              value={text} 
              onChange={(e) => setText(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent" 
              placeholder="Выберите вариант..." 
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">Кнопки (по одной на строке)</label>
            <textarea 
              value={buttons} 
              onChange={(e) => setButtons(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent resize-none" 
              rows={4} 
              placeholder="Кнопка 1&#10;Кнопка 2&#10;Кнопка 3" 
            />
          </div>
        </>
      )}
    </>
  );
}

function TimerEditor({ timerDelay, setTimerDelay }) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-slate-700 mb-2">Задержка (секунды)</label>
      <div className="flex items-center gap-4">
        <input 
          type="range" 
          min="1" 
          max="300" 
          value={timerDelay} 
          onChange={(e) => setTimerDelay(Number(e.target.value))}
          className="flex-1"
        />
        <input 
          type="number" 
          min="1" 
          max="3600"
          value={timerDelay} 
          onChange={(e) => setTimerDelay(Number(e.target.value))}
          className="w-20 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
        />
        <span className="text-sm text-slate-600">сек</span>
      </div>
      <p className="text-xs text-slate-500 mt-2">
        Узел автоматически продолжит цепочку через {formatTime(timerDelay)}
      </p>
    </div>
  );
}

function RouterEditor({ routes, addRoute, updateRoute, deleteRoute }) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-slate-700 mb-2">Условия маршрутизации</label>
      
      {/* Routes List */}
      <div className="space-y-2 mb-3">
        {routes.map((route) => (
          <div key={route.id} className="bg-slate-50 rounded-lg p-3 border border-slate-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-700">
                {CONDITION_LABELS[route.condition_type]}
              </span>
              <button 
                onClick={() => deleteRoute(route.id)} 
                className="text-red-500 hover:text-red-700 text-sm"
              >
                × Удалить
              </button>
            </div>

            {route.condition_type === "button_press" && (
              <input
                value={route.params.button_label || ""}
                onChange={(e) => updateRoute(route.id, { button_label: e.target.value })}
                className="w-full px-2 py-1 border border-slate-300 rounded text-sm"
                placeholder="Текст кнопки..."
              />
            )}

            {route.condition_type === "text_contains" && (
              <input
                value={route.params.text || ""}
                onChange={(e) => updateRoute(route.id, { text: e.target.value })}
                className="w-full px-2 py-1 border border-slate-300 rounded text-sm"
                placeholder="Текст для поиска..."
              />
            )}

            {route.condition_type === "text_regex" && (
              <input
                value={route.params.pattern || ""}
                onChange={(e) => updateRoute(route.id, { pattern: e.target.value })}
                className="w-full px-2 py-1 border border-slate-300 rounded text-sm font-mono"
                placeholder="^[A-Z].*"
              />
            )}

            {route.condition_type === "timeout" && (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  value={route.params.seconds || 60}
                  onChange={(e) => updateRoute(route.id, { seconds: Number(e.target.value) })}
                  className="w-20 px-2 py-1 border border-slate-300 rounded text-sm"
                />
                <span className="text-xs text-slate-600">секунд</span>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* Add Route Buttons */}
      <div>
        <p className="text-xs font-medium text-slate-700 mb-2">Добавить условие:</p>
        <div className="flex flex-wrap gap-2">
          {["button_press", "text_contains", "text_regex", "timeout", "any_reply"].map(condType => (
            <button
              key={condType}
              onClick={() => addRoute(condType)}
              className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-medium"
            >
              + {CONDITION_LABELS[condType]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
