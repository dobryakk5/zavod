"""
Celery Tasks for Chain Executor
--------------------------------
Production-ready Celery tasks for Telegram chain execution.

Setup:
    1. Install: pip install celery redis
    2. Configure Redis connection in celery_config.py
    3. Start worker: celery -A tasks worker --loglevel=info

These tasks are scheduled by the executor when:
- A node has delay_seconds > 0 → send_delayed_message
- An edge has a timeout condition → check_timeout
"""

from celery import Celery
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ===========================================================================
# CELERY APP CONFIGURATION
# ===========================================================================

app = Celery(
    'telegram_chains',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
)

app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    
    # Retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Result expiration
    result_expires=3600,
)

# ===========================================================================
# IMPORTS (adjust to your project structure)
# ===========================================================================
# These imports need to be updated to match your project:
#
# from executor import ChainExecutor
# from your_db import get_db
# from your_bot import send_telegram_message
#
# For now, they're shown as comments to prevent import errors.


# ===========================================================================
# HELPER: Get DB connection
# ===========================================================================

async def get_db_connection():
    """
    Returns an async database connection.
    
    Replace this with your actual DB connection logic.
    Example with asyncpg:
        import asyncpg
        return await asyncpg.connect(
            host='localhost',
            database='your_db',
            user='user',
            password='password',
        )
    """
    # TODO: Import and use your actual get_db() function
    raise NotImplementedError("Import your get_db() function")


# ===========================================================================
# HELPER: Send Telegram message
# ===========================================================================

async def send_telegram_message(user_id: int, **kwargs):
    """
    Sends a message via your Telegram bot.
    
    Replace this with your actual bot send function.
    
    Args:
        user_id: Telegram user ID
        **kwargs: Message params (text, photo, buttons, etc.)
    
    Examples:
        await send_telegram_message(12345, text="Hello")
        await send_telegram_message(12345, photo="url", caption="...")
        await send_telegram_message(12345, text="Choose:", buttons=["A","B"])
    """
    # TODO: Import and use your actual bot send function
    raise NotImplementedError("Import your Telegram bot send function")


# ===========================================================================
# TASK: Send Delayed Message
# ===========================================================================

@app.task(
    name='chains.send_delayed_message',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_delayed_message(self, session_id: int, node_id: int):
    """
    Sends a delayed message for a chain node.
    
    This task is scheduled with countdown=delay_seconds when the executor
    advances to a node with delay_seconds > 0.
    
    Args:
        session_id: Chain session ID
        node_id:    Node to send
    """
    try:
        asyncio.run(_send_delayed_message_async(session_id, node_id))
    except Exception as exc:
        logger.error(f"Error sending delayed message: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _send_delayed_message_async(session_id: int, node_id: int):
    """Async implementation of send_delayed_message."""
    
    # TODO: Uncomment when you have your imports set up
    # async with get_db() as db:
    #     # Load session
    #     session_row = await db.fetchrow(
    #         'SELECT * FROM chains.chain_sessions WHERE id = $1',
    #         session_id,
    #     )
    #     if not session_row:
    #         logger.warning(f"Session {session_id} not found")
    #         return
    #     
    #     session = dict(session_row)
    #     
    #     # Check session is still active and on this node
    #     if session['status'] != 'active':
    #         logger.info(f"Session {session_id} is not active (status={session['status']})")
    #         return
    #     
    #     if session['current_node_id'] != node_id:
    #         logger.info(f"Session {session_id} moved away from node {node_id}")
    #         return
    #     
    #     # Load node
    #     node_row = await db.fetchrow(
    #         'SELECT * FROM chains.chain_nodes WHERE id = $1',
    #         node_id,
    #     )
    #     if not node_row:
    #         logger.error(f"Node {node_id} not found")
    #         return
    #     
    #     node = dict(node_row)
    #     user_id = session['user_id']
    #     
    #     # Send message based on node type
    #     if node['node_type'] == 'text':
    #         await send_telegram_message(
    #             user_id,
    #             text=node['payload']['text']
    #         )
    #     
    #     elif node['node_type'] == 'photo':
    #         await send_telegram_message(
    #             user_id,
    #             photo=node['payload']['photo_url'],
    #             caption=node['payload'].get('caption', '')
    #         )
    #     
    #     elif node['node_type'] == 'buttons':
    #         await send_telegram_message(
    #             user_id,
    #             text=node['payload']['text'],
    #             buttons=node['payload']['buttons']
    #         )
    #     
    #     logger.info(f"Sent delayed message for session {session_id}, node {node_id}")
    
    # Placeholder implementation
    logger.info(f"[PLACEHOLDER] Would send message for session {session_id}, node {node_id}")


# ===========================================================================
# TASK: Check Timeout
# ===========================================================================

@app.task(
    name='chains.check_timeout',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def check_timeout(self, session_id: int, edge_id: int):
    """
    Checks if a session has timed out on an edge.
    
    If the user hasn't replied within timeout_seconds, this task fires
    and advances the session to the timeout edge's target node.
    
    Args:
        session_id: Chain session ID
        edge_id:    Edge with timeout condition
    """
    try:
        asyncio.run(_check_timeout_async(session_id, edge_id))
    except Exception as exc:
        logger.error(f"Error checking timeout: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _check_timeout_async(session_id: int, edge_id: int):
    """Async implementation of check_timeout."""
    
    # TODO: Uncomment when you have your imports set up
    # async with get_db() as db:
    #     from executor import ChainExecutor
    #     
    #     executor = ChainExecutor(db)
    #     result = await executor.process_timeout(session_id, edge_id)
    #     
    #     # Execute the returned actions
    #     for action in result.get('actions', []):
    #         await _execute_action(action, session_id, db)
    #     
    #     logger.info(f"Processed timeout for session {session_id}, edge {edge_id}")
    
    # Placeholder implementation
    logger.info(f"[PLACEHOLDER] Would process timeout for session {session_id}, edge {edge_id}")


# ===========================================================================
# HELPER: Execute Action
# ===========================================================================

async def _execute_action(action: dict, session_id: int, db):
    """
    Executes a single bot action.
    
    Called by check_timeout when processing timeout results.
    """
    action_type = action['action_type']
    payload = action['payload']
    delay = action.get('delay_seconds', 0)
    
    # Get user_id from session
    session_row = await db.fetchrow(
        'SELECT user_id FROM chains.chain_sessions WHERE id = $1',
        session_id,
    )
    if not session_row:
        return
    
    user_id = session_row['user_id']
    
    # If delayed, schedule it
    if delay > 0 and action_type in ('send_text', 'send_photo', 'send_buttons'):
        # Extract node_id from the action (you may need to adjust this)
        # For now, we'll just log
        logger.info(f"Would schedule delayed action: {action_type} with {delay}s delay")
        # send_delayed_message.apply_async(
        #     args=[session_id, node_id],
        #     countdown=delay
        # )
        return
    
    # Execute immediately
    if action_type == 'send_text':
        await send_telegram_message(user_id, text=payload['text'])
    
    elif action_type == 'send_photo':
        await send_telegram_message(
            user_id,
            photo=payload['photo_url'],
            caption=payload.get('caption', '')
        )
    
    elif action_type == 'send_buttons':
        await send_telegram_message(
            user_id,
            text=payload['text'],
            buttons=payload['buttons']
        )
    
    elif action_type == 'schedule_timeout':
        # Schedule another timeout task
        timeout_payload = payload
        check_timeout.apply_async(
            args=[timeout_payload['session_id'], timeout_payload['edge_id']],
            countdown=timeout_payload['timeout_seconds']
        )


# ===========================================================================
# INTEGRATION FUNCTIONS (for use in executor.py)
# ===========================================================================

def schedule_delayed_message(session_id: int, node_id: int, delay_seconds: int):
    """
    Schedules a delayed message task.
    
    Call this from executor.py when advancing to a node with delay_seconds > 0.
    
    Example:
        from tasks import schedule_delayed_message
        schedule_delayed_message(session_id=123, node_id=456, delay_seconds=10)
    """
    send_delayed_message.apply_async(
        args=[session_id, node_id],
        countdown=delay_seconds
    )
    logger.info(f"Scheduled message for session {session_id}, node {node_id} in {delay_seconds}s")


def schedule_timeout_check(session_id: int, edge_id: int, timeout_seconds: int):
    """
    Schedules a timeout check task.
    
    Call this from executor.py when there's a timeout condition on an edge.
    
    Example:
        from tasks import schedule_timeout_check
        schedule_timeout_check(session_id=123, edge_id=789, timeout_seconds=300)
    """
    check_timeout.apply_async(
        args=[session_id, edge_id],
        countdown=timeout_seconds
    )
    logger.info(f"Scheduled timeout check for session {session_id}, edge {edge_id} in {timeout_seconds}s")


# ===========================================================================
# STARTUP / MONITORING
# ===========================================================================

@app.task(name='chains.health_check')
def health_check():
    """Health check task for monitoring."""
    return {'status': 'ok', 'worker': 'chains'}


# ===========================================================================
# EXAMPLE: How to use in executor.py
# ===========================================================================
"""
In your executor.py, when generating actions:

from tasks import schedule_delayed_message, schedule_timeout_check

# In _advance_to_node method:
for action in actions:
    if action['action_type'] in ('send_text', 'send_photo', 'send_buttons'):
        if action['delay_seconds'] > 0:
            # Schedule delayed send
            schedule_delayed_message(
                session_id=session_id,
                node_id=node_id,
                delay_seconds=action['delay_seconds']
            )
        else:
            # Send immediately (your existing logic)
            await self._send_message_immediately(action, session_id)
    
    elif action['action_type'] == 'schedule_timeout':
        payload = action['payload']
        schedule_timeout_check(
            session_id=payload['session_id'],
            edge_id=payload['edge_id'],
            timeout_seconds=payload['timeout_seconds']
        )
"""


# ===========================================================================
# WORKER STARTUP
# ===========================================================================
"""
To run the Celery worker:

celery -A tasks worker --loglevel=info --concurrency=4

For production, use supervisor or systemd:

[program:celery_chains]
command=celery -A tasks worker --loglevel=info --concurrency=4
directory=/path/to/your/project
user=your_user
autostart=true
autorestart=true
stdout_logfile=/var/log/celery/chains.log
stderr_logfile=/var/log/celery/chains_error.log

Monitoring with Flower:
pip install flower
celery -A tasks flower --port=5555
"""
