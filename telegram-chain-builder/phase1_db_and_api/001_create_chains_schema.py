"""create chains schema and tables

Revision ID: 001_chains
Revises: <your_current_head>
Create Date: 2025-02-03

Tables created:
    chains.chains           – the chain itself (owner = tenant)
    chains.chain_nodes      – every message-node inside a chain
    chains.chain_edges      – directed edge source_node → target_node
    chains.chain_conditions – one or more conditions attached to an edge
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# revision identifiers
# ---------------------------------------------------------------------------
revision = "001_chains"
down_revision = None          # <-- replace with your current head
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
SCHEMA = "chains"


def _ensure_updated_at_fn():
    """
    Reuse the trigger function that already exists in the `map` schema.
    If for some reason it does not exist we create an identical copy in
    the `chains` schema so the migration is self-contained.
    """
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def _add_updated_at_trigger(table: str):
    trigger_name = f"trg_{SCHEMA}_{table}_updated"
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '{trigger_name}') THEN
                CREATE TRIGGER {trigger_name}
                    BEFORE UPDATE ON {SCHEMA}.{table}
                    FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.set_updated_at();
            END IF;
        END $$;
        """
    )


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade():
    # ── schema ──────────────────────────────────────────────────────────
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    _ensure_updated_at_fn()

    # ── chains ──────────────────────────────────────────────────────────
    # Core entity.  Every chain belongs to exactly one tenant (core_client).
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.chains (
            id              BIGSERIAL PRIMARY KEY,
            tenant_id       BIGINT   NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
            name            VARCHAR(255) NOT NULL,
            description     TEXT,
            status          VARCHAR(20)  NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft', 'active', 'paused', 'archived')),
            start_node_id   BIGINT,                          -- set after first node is created
            created_at      TIMESTAMP NOT NULL DEFAULT now(),
            updated_at      TIMESTAMP NOT NULL DEFAULT now()
        );
        """
    )
    _add_updated_at_trigger("chains")

    # ── chain_nodes ─────────────────────────────────────────────────────
    # Every single message inside a chain.
    # node_type   – what kind of Telegram message this is
    # payload     – JSONB that holds the actual content depending on node_type:
    #                 text   → { "text": "..." }
    #                 photo  → { "photo_url": "...", "caption": "..." }
    #                 buttons→ { "text": "...", "buttons": ["btn1","btn2"] }
    # delay_seconds – how long to wait BEFORE sending this node after
    #                 the previous transition fires (0 = instant)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.chain_nodes (
            id              BIGSERIAL PRIMARY KEY,
            chain_id        BIGINT   NOT NULL REFERENCES {SCHEMA}.chains(id) ON DELETE CASCADE,
            node_type       VARCHAR(20) NOT NULL DEFAULT 'text'
                                CHECK (node_type IN ('text', 'photo', 'buttons')),
            payload         JSONB    NOT NULL,
            delay_seconds   INTEGER  NOT NULL DEFAULT 0 CHECK (delay_seconds >= 0),
            -- layout position (saved from the frontend canvas)
            pos_x           FLOAT    NOT NULL DEFAULT 0,
            pos_y           FLOAT    NOT NULL DEFAULT 0,
            created_at      TIMESTAMP NOT NULL DEFAULT now(),
            updated_at      TIMESTAMP NOT NULL DEFAULT now()
        );
        """
    )
    _add_updated_at_trigger("chain_nodes")

    # ── chain_edges ─────────────────────────────────────────────────────
    # Directed edge: source_node  →  target_node.
    # An edge with NO conditions on it is an unconditional ("default") transition.
    # An edge WITH conditions fires only when ALL its conditions match.
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.chain_edges (
            id              BIGSERIAL PRIMARY KEY,
            chain_id        BIGINT   NOT NULL REFERENCES {SCHEMA}.chains(id) ON DELETE CASCADE,
            source_node_id  BIGINT   NOT NULL REFERENCES {SCHEMA}.chain_nodes(id) ON DELETE CASCADE,
            target_node_id  BIGINT   NOT NULL REFERENCES {SCHEMA}.chain_nodes(id) ON DELETE CASCADE,
            -- priority matters when multiple edges leave the same source:
            -- the engine evaluates them in ascending order and takes the first match.
            -- The unconditional ("default") edge should always have the highest number.
            priority        INTEGER  NOT NULL DEFAULT 0,
            created_at      TIMESTAMP NOT NULL DEFAULT now(),
            updated_at      TIMESTAMP NOT NULL DEFAULT now(),

            -- one edge cannot be duplicated
            UNIQUE (source_node_id, target_node_id)
        );
        """
    )
    _add_updated_at_trigger("chain_edges")

    # ── chain_conditions ────────────────────────────────────────────────
    # Conditions live ON an edge.  Multiple conditions on the same edge
    # are ANDed together by the engine.
    #
    # condition_type  – the kind of check:
    #     "button_press"   → user pressed a specific button
    #                        { "button_label": "Да" }
    #     "text_contains"  → user's text message contains a substring
    #                        { "substring": "да", "case_sensitive": false }
    #     "text_regex"     → user's text matches a regex
    #                        { "pattern": "^да$", "flags": "i" }
    #     "timeout"        → user did NOT reply within N seconds
    #                        { "timeout_seconds": 300 }
    #     "any_reply"      → user sent anything (catch-all)
    #                        {}
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.chain_conditions (
            id              BIGSERIAL PRIMARY KEY,
            edge_id         BIGINT   NOT NULL REFERENCES {SCHEMA}.chain_edges(id) ON DELETE CASCADE,
            condition_type  VARCHAR(30) NOT NULL
                                CHECK (condition_type IN (
                                    'button_press',
                                    'text_contains',
                                    'text_regex',
                                    'timeout',
                                    'any_reply'
                                )),
            params          JSONB    NOT NULL DEFAULT '{}',
            created_at      TIMESTAMP NOT NULL DEFAULT now()
        );
        """
    )

    # ── indexes ─────────────────────────────────────────────────────────
    # Mirroring the idx_map_* naming convention already in the project.
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_chains_tenant       ON {SCHEMA}.chains(tenant_id);")
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_chains_status       ON {SCHEMA}.chains(tenant_id, status);")

    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_nodes_chain         ON {SCHEMA}.chain_nodes(chain_id);")

    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_edges_chain         ON {SCHEMA}.chain_edges(chain_id);")
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_edges_source        ON {SCHEMA}.chain_edges(source_node_id, priority);")
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_edges_target        ON {SCHEMA}.chain_edges(target_node_id);")

    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_conditions_edge     ON {SCHEMA}.chain_conditions(edge_id);")
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_chains_conditions_type     ON {SCHEMA}.chain_conditions(edge_id, condition_type);")

    # ── back-patch FK on chains.start_node_id (created after chain_nodes exists) ──
    op.execute(
        f"""
        ALTER TABLE {SCHEMA}.chains
            ADD CONSTRAINT fk_chains_start_node
            FOREIGN KEY (start_node_id) REFERENCES {SCHEMA}.chain_nodes(id) ON DELETE SET NULL;
        """
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade():
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
