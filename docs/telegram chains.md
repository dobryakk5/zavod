По коду логика «UI‑цепочка → Telegram‑бот ведёт по ней» действительно связана. Но живое поведение в Telegram я подтвердить не могу без запуска бота/токена и тестового чата. Ниже — проверка по реализации и важные условия, чтобы это работало.

**Что подтверждено по коду**
1. UI сохраняет цепочку в backend через `chains` API для текущего tenant.  
   Файлы:  
   - `/Users/pavellebedev/Desktop/proj/zavod/frontend/components/chain-editor-refactored/ChainEditor.jsx`  
   - `/Users/pavellebedev/Desktop/proj/zavod/frontend/lib/api/chains.ts`  
   - `/Users/pavellebedev/Desktop/proj/zavod/backend/api/views_chains.py`
2. В backend цепочка — одна на tenant, создаётся/читается через `get_or_create_chain`.  
   Файл: `/Users/pavellebedev/Desktop/proj/zavod/backend/core/services/chain_service.py`
3. Telegram‑бот запускает цепочку и обрабатывает сообщения через `ChainExecutor`, который читает узлы/рёбра/условия из БД.  
   Файлы:  
   - `/Users/pavellebedev/Desktop/proj/zavod/backend/core/management/commands/run_telegram_tasks_bot.py`  
   - `/Users/pavellebedev/Desktop/proj/zavod/backend/core/services/chain_executor.py`
4. Отложенные сообщения и таймауты выполняются через Celery‑таски.  
   Файл: `/Users/pavellebedev/Desktop/proj/zavod/backend/core/tasks/chains.py`

**Критичные условия, без которых “в Telegram работает” не будет**
1. Пользователь должен быть привязан к tenant через deep‑link `/start` (bind), иначе цепочка не запускается.  
   Файл: `/Users/pavellebedev/Desktop/proj/zavod/backend/core/management/commands/run_telegram_tasks_bot.py`
2. Цепочка стартует только по кнопке `WELCOME_BUTTON_TEXT` (“Welcome”), а не автоматически на `/start`.  
   Файл: `/Users/pavellebedev/Desktop/proj/zavod/backend/core/telegram_bot/ui.py`
3. Для задержек/таймаутов нужен запущенный Celery worker.  
   Файл: `/Users/pavellebedev/Desktop/proj/zavod/backend/core/tasks/chains.py`
4. `TELEGRAM_BOT_TOKEN` должен быть задан, иначе отправка сообщений не пойдёт.  
   Файл: `/Users/pavellebedev/Desktop/proj/zavod/backend/core/tasks/chains.py`

**Важная оговорка**
Сейчас статус цепочки (`draft/active/paused`) нигде не проверяется при выполнении — бот использует цепочку независимо от статуса.  
Файлы:  
- `/Users/pavellebedev/Desktop/proj/zavod/backend/core/services/chain_executor.py`  
- `/Users/pavellebedev/Desktop/proj/zavod/backend/core/services/chain_service.py`

Если хочешь, я могу:
1. Прогнать end‑to‑end проверку в вашей среде (нужны токен и возможность запускать бот/worker).  
2. Добавить проверку статуса цепочки, чтобы работала только `active`.  
3. Добавить явный лог/метрику “цепочка запущена/пройдена” для подтверждения в проде.