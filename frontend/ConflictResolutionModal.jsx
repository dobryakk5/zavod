'use client';

import { useState } from "react";

// ─── Иконки провайдеров ──────────────────────────────────────────────────────

const VKIcon = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
    <path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.744c-.66 0-.862-.525-2.049-1.714-1.033-1.01-1.49-1.135-1.744-1.135-.356 0-.458.102-.458.593v1.575c0 .424-.135.677-1.253.677-1.846 0-3.896-1.118-5.335-3.202C4.624 10.857 4 8.983 4 8.558c0-.254.102-.491.593-.491h1.744c.44 0 .61.203.78.678.864 2.49 2.303 4.675 2.896 4.675.22 0 .322-.102.322-.66V9.995c-.068-1.186-.695-1.287-.695-1.71 0-.204.17-.407.44-.407h2.744c.373 0 .508.203.508.643v3.473c0 .372.17.508.271.508.22 0 .407-.136.814-.542 1.253-1.406 2.151-3.574 2.151-3.574.119-.254.322-.491.763-.491h1.744c.525 0 .643.27.525.643-.22 1.017-2.354 4.031-2.354 4.031-.186.305-.254.44 0 .78.186.254.796.78 1.203 1.253.745.847 1.32 1.558 1.473 2.049.17.491-.085.745-.576.745z"/>
  </svg>
);

const TGIcon = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
    <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
  </svg>
);

const PROVIDER_META = {
  vk: {
    label: "ВКонтакте",
    Icon: VKIcon,
    color: "#0077FF",
    bg: "#EBF4FF",
    darkBg: "#1a3a5c",
  },
  telegram: {
    label: "Telegram",
    Icon: TGIcon,
    color: "#26A5E4",
    bg: "#E8F6FD",
    darkBg: "#1a3a4a",
  },
};

function getProviderMeta(provider = "") {
  return PROVIDER_META[provider.toLowerCase()] ?? {
    label: provider,
    Icon: () => <span style={{ fontSize: 16 }}>🔗</span>,
    color: "#888",
    bg: "#f5f5f5",
    darkBg: "#2a2a2a",
  };
}

// ─── ProfileCard ─────────────────────────────────────────────────────────────

function ProfileCard({ profile, chosen, onChoose, roleLabel, willBeDeleted }) {
  const socials = profile.social_accounts ?? [];
  const clients = profile.clients ?? [];
  const hasContent = clients.some((c) => !c.is_empty);

  return (
    <button
      onClick={onChoose}
      style={{
        all: "unset",
        display: "block",
        cursor: "pointer",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          position: "relative",
          borderRadius: 16,
          border: chosen
            ? "2px solid #1a1a2e"
            : "2px solid #e5e5e5",
          background: chosen ? "#f7f6f3" : "#fff",
          padding: "20px 20px 16px",
          transition: "border-color 0.18s, background 0.18s, box-shadow 0.18s",
          boxShadow: chosen
            ? "0 4px 24px rgba(0,0,0,0.10)"
            : "0 1px 4px rgba(0,0,0,0.05)",
        }}
      >
        {/* Radio dot */}
        <div
          style={{
            position: "absolute",
            top: 20,
            right: 20,
            width: 20,
            height: 20,
            borderRadius: "50%",
            border: chosen ? "6px solid #1a1a2e" : "2px solid #ccc",
            background: "#fff",
            transition: "border 0.18s",
            flexShrink: 0,
          }}
        />

        {/* Role badge */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: willBeDeleted ? "#fff0f0" : "#f0fdf4",
            color: willBeDeleted ? "#c0392b" : "#16a34a",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.07em",
            textTransform: "uppercase",
            borderRadius: 6,
            padding: "3px 10px",
            marginBottom: 12,
            fontFamily: "'Courier New', monospace",
          }}
        >
          {willBeDeleted ? "✕ будет удалён" : "✓ " + roleLabel}
        </div>

        {/* Name */}
        <div style={{ fontWeight: 700, fontSize: 17, color: "#111", marginBottom: 4, fontFamily: "Georgia, serif" }}>
          {profile.first_name || profile.last_name
            ? `${profile.first_name} ${profile.last_name}`.trim()
            : profile.username}
        </div>
        {profile.email && (
          <div style={{ fontSize: 13, color: "#888", marginBottom: 14 }}>
            {profile.email}
          </div>
        )}

        {/* Socials */}
        {socials.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
            {socials.map((s) => {
              const meta = getProviderMeta(s.provider);
              const name =
                s.extra_data?.screen_name ||
                s.extra_data?.username ||
                `${s.extra_data?.first_name || ""} ${s.extra_data?.last_name || ""}`.trim() ||
                s.provider;
              return (
                <div
                  key={s.provider}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    background: meta.bg,
                    color: meta.color,
                    borderRadius: 8,
                    padding: "5px 12px",
                    fontSize: 13,
                    fontWeight: 600,
                  }}
                >
                  <meta.Icon size={15} />
                  {name}
                </div>
              );
            })}
          </div>
        )}

        {/* Clients */}
        {clients.length > 0 && (
          <div style={{ marginTop: 4 }}>
            {clients.map((c) => (
              <div
                key={c.slug}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "#fafafa",
                  border: "1px solid #ebebeb",
                  borderRadius: 8,
                  padding: "7px 12px",
                  marginBottom: 6,
                  fontSize: 13,
                }}
              >
                <span style={{ color: "#333", fontWeight: 500 }}>{c.name}</span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: c.is_empty ? "#aaa" : "#e67e22",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    fontFamily: "'Courier New', monospace",
                  }}
                >
                  {c.is_empty ? "пусто" : "есть данные"}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Content warning */}
        {willBeDeleted && hasContent && (
          <div
            style={{
              marginTop: 10,
              background: "#fff5f5",
              border: "1px solid #fecaca",
              borderRadius: 8,
              padding: "8px 12px",
              fontSize: 12,
              color: "#c0392b",
              lineHeight: 1.5,
            }}
          >
            ⚠️ Этот профиль содержит данные. После удаления восстановить невозможно.
          </div>
        )}

        {/* Date */}
        <div style={{ marginTop: 10, fontSize: 11, color: "#bbb", fontFamily: "'Courier New', monospace" }}>
          создан {new Date(profile.date_joined).toLocaleDateString("ru-RU")}
        </div>
      </div>
    </button>
  );
}

// ─── Main Modal ───────────────────────────────────────────────────────────────

export default function ConflictResolutionModal({
  // Данные от бэкенда (409-ответ)
  conflictData = null,
  resolveUrl = "/auth/social/conflict/resolve",
  onResolved = () => {},
  onCancel = () => {},
}) {
  // Demo-данные если не передали реальные
  const demo = {
    resolution_token: "demo_token_abc123",
    current_profile: {
      user_id: 1,
      username: "alex_tg",
      email: "alex@example.com",
      first_name: "Алексей",
      last_name: "Морозов",
      date_joined: "2024-03-10T10:00:00Z",
      clients: [{ name: "Мой магазин", slug: "my-shop", role: "owner", is_empty: false }],
      social_accounts: [{ provider: "telegram", extra_data: { username: "alex_tg" } }],
    },
    existing_profile: {
      user_id: 2,
      username: "vk_12345678",
      email: "alex@vk.local",
      first_name: "Алексей",
      last_name: "",
      date_joined: "2025-11-02T14:32:00Z",
      clients: [{ name: "vk_12345678", slug: "12345678", role: "owner", is_empty: true }],
      social_accounts: [{ provider: "vk", extra_data: { screen_name: "alex_morozov", first_name: "Алексей" } }],
    },
  };

  const data = conflictData ?? demo;
  const { resolution_token, current_profile, existing_profile } = data;

  const [choice, setChoice] = useState(null); // "current" | "existing"
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Определяем провайдер соцсети у каждого профиля для подписей
  const currentProvider = current_profile.social_accounts?.[0]?.provider ?? "текущий";
  const existingProvider = existing_profile.social_accounts?.[0]?.provider ?? "другой";
  const currentMeta = getProviderMeta(currentProvider);
  const existingMeta = getProviderMeta(existingProvider);

  const handleConfirm = async () => {
    if (!choice) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(resolveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ resolution_token, keep: choice }),
      });
      const json = await res.json();

      if (!res.ok) {
        setError(json.error ?? "Неизвестная ошибка");
        setLoading(false);
        return;
      }

      onResolved(json);
    } catch {
      setError("Ошибка сети. Попробуйте ещё раз.");
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(10,10,20,0.55)",
        backdropFilter: "blur(6px)",
        padding: 16,
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 24,
          width: "100%",
          maxWidth: 540,
          maxHeight: "90vh",
          overflowY: "auto",
          boxShadow: "0 32px 80px rgba(0,0,0,0.22)",
          fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "28px 28px 0",
            borderBottom: "1px solid #f0f0f0",
            paddingBottom: 20,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 10,
            }}
          >
            {/* Иконки обоих провайдеров */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                background: currentMeta.bg,
                color: currentMeta.color,
                borderRadius: 10,
                padding: "7px 12px",
                gap: 6,
                fontWeight: 700,
                fontSize: 14,
              }}
            >
              <currentMeta.Icon size={18} />
              {currentMeta.label}
            </div>
            <span style={{ color: "#aaa", fontWeight: 300, fontSize: 20 }}>↔</span>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                background: existingMeta.bg,
                color: existingMeta.color,
                borderRadius: 10,
                padding: "7px 12px",
                gap: 6,
                fontWeight: 700,
                fontSize: 14,
              }}
            >
              <existingMeta.Icon size={18} />
              {existingMeta.label}
            </div>
          </div>

          <h2
            style={{
              margin: 0,
              fontSize: 20,
              fontWeight: 800,
              color: "#111",
              fontFamily: "Georgia, serif",
              lineHeight: 1.3,
            }}
          >
            Уже есть профиль на этом аккаунте
          </h2>
          <p style={{ margin: "8px 0 0", fontSize: 14, color: "#666", lineHeight: 1.5 }}>
            Аккаунт {existingMeta.label} уже привязан к другому профилю.
            Выберите, какой профиль оставить — второй будет удалён.
          </p>
        </div>

        {/* Cards */}
        <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Вариант 1: оставить existing (аккаунт новой соцсети) */}
          <ProfileCard
            profile={existing_profile}
            chosen={choice === "existing"}
            onChoose={() => setChoice("existing")}
            roleLabel={`профиль ${existingMeta.label}`}
            willBeDeleted={choice === "current"}
          />

          {/* Вариант 2: оставить current */}
          <ProfileCard
            profile={current_profile}
            chosen={choice === "current"}
            onChoose={() => setChoice("current")}
            roleLabel={`профиль ${currentMeta.label}`}
            willBeDeleted={choice === "existing"}
          />
        </div>

        {/* Delete preview */}
        {choice && (
          <div
            style={{
              margin: "0 28px 16px",
              background: "#fff8f0",
              border: "1px solid #fde68a",
              borderRadius: 12,
              padding: "12px 16px",
              fontSize: 13,
              color: "#92400e",
              lineHeight: 1.5,
            }}
          >
            <strong>Будет удалён профиль:</strong>{" "}
            {choice === "current"
              ? `${current_profile.first_name || current_profile.username} (${currentMeta.label})`
              : `${existing_profile.first_name || existing_profile.username} (${existingMeta.label})`}
            . Это действие необратимо.
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            style={{
              margin: "0 28px 16px",
              background: "#fff5f5",
              border: "1px solid #fecaca",
              borderRadius: 12,
              padding: "12px 16px",
              fontSize: 13,
              color: "#c0392b",
            }}
          >
            {error}
          </div>
        )}

        {/* Actions */}
        <div
          style={{
            padding: "0 28px 28px",
            display: "flex",
            gap: 10,
          }}
        >
          <button
            onClick={onCancel}
            disabled={loading}
            style={{
              flex: 1,
              padding: "13px 0",
              borderRadius: 12,
              border: "2px solid #e5e5e5",
              background: "#fff",
              color: "#555",
              fontWeight: 600,
              fontSize: 15,
              cursor: loading ? "not-allowed" : "pointer",
              transition: "background 0.15s",
              fontFamily: "inherit",
            }}
          >
            Отмена
          </button>
          <button
            onClick={handleConfirm}
            disabled={!choice || loading}
            style={{
              flex: 2,
              padding: "13px 0",
              borderRadius: 12,
              border: "none",
              background: !choice || loading ? "#e5e5e5" : "#1a1a2e",
              color: !choice || loading ? "#999" : "#fff",
              fontWeight: 700,
              fontSize: 15,
              cursor: !choice || loading ? "not-allowed" : "pointer",
              transition: "background 0.15s, color 0.15s",
              fontFamily: "inherit",
              letterSpacing: "0.02em",
            }}
          >
            {loading ? "Применяем…" : "Подтвердить выбор"}
          </button>
        </div>
      </div>
    </div>
  );
}
