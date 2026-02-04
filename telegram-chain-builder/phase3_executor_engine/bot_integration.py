"""
Bot Integration Example
------------------------
How to integrate the ChainExecutor into your existing Telegram bot.

This example uses python-telegram-bot (PTB) but the same principles apply
to aiogram, telebot, or any other bot framework.

KEY INTEGRATION POINTS:

1. Message handler → executor.process_user_message()
2. Callback query (button press) → executor.process_user_message()
3. Starting a chain → executor.start_chain()
4. Executing actions → send messages via bot API
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from executor import ChainExecutor
from conditions import telegram_message_to_dict
from your_db import get_db  # Your async DB session factory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===========================================================================
# BOT HANDLERS
# ===========================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start command → starts the default chain for this tenant.
    
    In a real implementation, you would:
    1. Authenticate the user (get their tenant_id from DB or session)
    2. Determine which chain to start (default onboarding chain, or from deep link)
    3. Call executor.start_chain()
    """
    user_id = update.effective_user.id
    
    # Example: hardcoded tenant and chain for demo
    tenant_id = 1
    chain_id = 1  # Could come from /start deep link: /start chain_123
    
    async with get_db() as db:
        executor = ChainExecutor(db)
        
        try:
            result = await executor.start_chain(
                user_id=user_id,
                chain_id=chain_id,
                tenant_id=tenant_id,
            )
            
            # Execute the initial actions
            await execute_actions(update, result["actions"])
            
        except Exception as e:
            logger.error(f"Error starting chain: {e}")
            await update.message.reply_text("Ошибка запуска цепочки 😔")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles incoming text messages from users.
    
    1. Convert Telegram update to normalized message dict
    2. Call executor.process_user_message()
    3. Execute the returned actions
    """
    user_id = update.effective_user.id
    
    # Get tenant_id from user (from DB or session)
    # In a real app, you'd query the DB to find which tenant this user belongs to
    tenant_id = await get_user_tenant(user_id)
    if not tenant_id:
        # User not associated with any tenant → ignore or onboard
        return
    
    # Convert Telegram message to normalized dict
    user_message = telegram_message_to_dict(update.to_dict())
    
    async with get_db() as db:
        executor = ChainExecutor(db)
        
        try:
            result = await executor.process_user_message(
                user_id=user_id,
                tenant_id=tenant_id,
                user_message=user_message,
            )
            
            # Execute the returned actions
            await execute_actions(update, result["actions"])
            
            if result["session_status"] == "completed":
                logger.info(f"User {user_id} completed chain")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text("Что-то пошло не так 😔")


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles button presses (callback queries).
    
    Button data format: the button label (e.g., "Продукт")
    This is matched against button_press conditions in the executor.
    """
    user_id = update.effective_user.id
    button_data = update.callback_query.data
    
    # Acknowledge the callback
    await update.callback_query.answer()
    
    # Get tenant_id
    tenant_id = await get_user_tenant(user_id)
    if not tenant_id:
        return
    
    # Convert to normalized message dict
    user_message = {"button": button_data}
    
    async with get_db() as db:
        executor = ChainExecutor(db)
        
        try:
            result = await executor.process_user_message(
                user_id=user_id,
                tenant_id=tenant_id,
                user_message=user_message,
            )
            
            # Execute actions
            await execute_actions(update, result["actions"])
            
        except Exception as e:
            logger.error(f"Error processing button: {e}")
            await update.callback_query.edit_message_text("Ошибка 😔")


# ===========================================================================
# ACTION EXECUTION
# ===========================================================================

async def execute_actions(update: Update, actions: list[dict]):
    """
    Executes a list of bot actions returned by the executor.
    
    For actions with delay_seconds > 0, schedules them via task queue.
    For immediate actions, sends them right away.
    """
    for action in actions:
        if action["delay_seconds"] > 0:
            # Schedule via task queue (Celery/ARQ)
            # Example (pseudocode):
            # await schedule_delayed_action(action, update.effective_user.id)
            logger.info(f"Scheduling action with {action['delay_seconds']}s delay: {action['action_type']}")
            # For now, skip (implement task queue integration)
            continue
        
        # Execute immediately
        await execute_single_action(update, action)


async def execute_single_action(update: Update, action: dict):
    """
    Executes a single bot action immediately.
    """
    action_type = action["action_type"]
    payload = action["payload"]
    
    if action_type == "send_text":
        await update.effective_chat.send_message(text=payload["text"])
    
    elif action_type == "send_photo":
        await update.effective_chat.send_photo(
            photo=payload["photo_url"],
            caption=payload.get("caption", ""),
        )
    
    elif action_type == "send_buttons":
        # Create inline keyboard from button labels
        buttons = payload.get("buttons", [])
        keyboard = [
            [InlineKeyboardButton(btn, callback_data=btn)]
            for btn in buttons
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.effective_chat.send_message(
            text=payload["text"],
            reply_markup=reply_markup,
        )
    
    elif action_type == "schedule_timeout":
        # Schedule timeout task via task queue
        # Example (pseudocode):
        # await schedule_timeout_task(payload)
        logger.info(f"Scheduling timeout: {payload}")


# ===========================================================================
# HELPERS
# ===========================================================================

async def get_user_tenant(user_id: int) -> int | None:
    """
    Gets the tenant_id for a user.
    
    In your real implementation, query the database:
      SELECT tenant_id FROM user_tenant_mapping WHERE telegram_user_id = $1
    
    Or use your existing auth system.
    """
    # Example hardcoded for demo:
    return 1


# ===========================================================================
# BOT SETUP
# ===========================================================================

def main():
    """
    Main bot entry point.
    """
    # Get bot token from env
    import os
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Start bot
    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()


# ===========================================================================
# INTEGRATION CHECKLIST
# ===========================================================================
"""
□ Install dependencies:
  pip install python-telegram-bot asyncpg  # or your DB driver

□ Set up database connection pool in your_db.py

□ Implement get_user_tenant() to map Telegram users to tenants

□ Integrate task queue (Celery or ARQ) for delayed messages:
  - Implement schedule_delayed_action()
  - Implement schedule_timeout_task()

□ Add error handling and logging

□ Test with a simple chain:
  1. Create chain in DB via Phase 1 API
  2. Send /start to bot
  3. Verify bot sends first message
  4. Reply to bot → verify transition works

□ Monitor chain_sessions table to debug user flows

□ Add admin commands:
  /chains - list available chains
  /mystatus - show current session
  /reset - restart current chain
"""


# ===========================================================================
# ADMIN COMMANDS (BONUS)
# ===========================================================================

async def chains_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists available chains for this tenant."""
    tenant_id = await get_user_tenant(update.effective_user.id)
    
    async with get_db() as db:
        chains = await db.fetch(
            "SELECT id, name, description FROM chains.chains WHERE tenant_id = $1 AND status = 'active'",
            tenant_id,
        )
        
        if not chains:
            await update.message.reply_text("Нет активных цепочек")
            return
        
        text = "Доступные цепочки:\n\n"
        for c in chains:
            text += f"• {c['name']} (ID: {c['id']})\n"
            if c['description']:
                text += f"  {c['description']}\n"
        
        await update.message.reply_text(text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows user's current session status."""
    user_id = update.effective_user.id
    tenant_id = await get_user_tenant(user_id)
    
    async with get_db() as db:
        session = await db.fetchrow(
            """
            SELECT s.*, c.name as chain_name, n.payload as current_node_payload
            FROM chains.chain_sessions s
            JOIN chains.chains c ON c.id = s.chain_id
            LEFT JOIN chains.chain_nodes n ON n.id = s.current_node_id
            WHERE s.user_id = $1 AND s.tenant_id = $2 AND s.status = 'active'
            ORDER BY s.last_activity_at DESC
            LIMIT 1
            """,
            user_id, tenant_id,
        )
        
        if not session:
            await update.message.reply_text("У вас нет активных цепочек")
            return
        
        text = f"Ваша текущая цепочка: {session['chain_name']}\n"
        text += f"Статус: {session['status']}\n"
        text += f"Начата: {session['started_at'].strftime('%Y-%m-%d %H:%M')}\n"
        
        if session['current_node_payload']:
            preview = session['current_node_payload'].get('text', '')[:50]
            text += f"\nТекущий шаг: {preview}..."
        
        await update.message.reply_text(text)


# Add these to your bot setup:
# app.add_handler(CommandHandler("chains", chains_command))
# app.add_handler(CommandHandler("status", status_command))
