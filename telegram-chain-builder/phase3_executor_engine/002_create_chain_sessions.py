"""create chain_sessions table

Revision ID: 002_chain_sessions
Revises: 001_chains
Create Date: 2025-02-03

This table tracks the execution state of chains for each user.
Each row represents one user's journey through one chain.
"""

from alembic import op
import sqlalchemy as sa

revision = "002_chain_sessions"
down_revision = "001_chains"
branch_labels = None
depends_on = None


SCHEMA = "chains"


def upgrade():
    # ── chain_sessions ──────────────────────────────────────────────────
    # Tracks active user sessions in chains.
    # 
    # user_id      – Telegram user ID (BIGINT or TEXT depending on your schema)
    # tenant_id    – which tenant owns this chain
    # chain_id     – the chain being executed
    # current_node_id – where the user is right now in the chain
    # status       – active | completed | paused | failed
    # context      – JSONB: stores user answers, timestamps, arbitrary state
    #                Example: { "answers": { "2": "Продукт" }, "started_at": "..." }
    # 
    # A user can have multiple sessions (different chains), but only ONE
    # active session per chain at a time.
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.chain_sessions (
            id                BIGSERIAL PRIMARY KEY,
            user_id           BIGINT    NOT NULL,  -- Telegram user ID
            tenant_id         BIGINT    NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
            chain_id          BIGINT    NOT NULL REFERENCES {SCHEMA}.chains(id) ON DELETE CASCADE,
            current_node_id   BIGINT    REFERENCES {SCHEMA}.chain_nodes(id) ON DELETE SET NULL,
            status            VARCHAR(20) NOT NULL DEFAULT 'active'
                                  CHECK (status IN ('active', 'completed', 'paused', 'failed')),
            context           JSONB     NOT NULL DEFAULT '{{}}',
            
            -- when this session started
            started_at        TIMESTAMP NOT NULL DEFAULT now(),
            
            -- last activity (updated on every transition)
            last_activity_at  TIMESTAMP NOT NULL DEFAULT now(),
            
            -- if completed/failed, when
            completed_at      TIMESTAMP,
            
            created_at        TIMESTAMP NOT NULL DEFAULT now(),
            updated_at        TIMESTAMP NOT NULL DEFAULT now(),
            
            -- one active session per user+chain
            UNIQUE (user_id, chain_id, status)
        );
        """
    )

    # ── indexes ─────────────────────────────────────────────────────────
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_chains_sessions_user_status "
        f"ON {SCHEMA}.chain_sessions(user_id, status);"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_chains_sessions_tenant "
        f"ON {SCHEMA}.chain_sessions(tenant_id, status);"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_chains_sessions_chain "
        f"ON {SCHEMA}.chain_sessions(chain_id, status);"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_chains_sessions_last_activity "
        f"ON {SCHEMA}.chain_sessions(last_activity_at) "
        f"WHERE status = 'active';"
    )

    # ── trigger for updated_at ──────────────────────────────────────────
    # Reuse the set_updated_at function from the chains schema
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_chains_sessions_updated') THEN
                CREATE TRIGGER trg_chains_sessions_updated
                    BEFORE UPDATE ON {SCHEMA}.chain_sessions
                    FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.set_updated_at();
            END IF;
        END $$;
        """
    )


def downgrade():
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.chain_sessions CASCADE")
