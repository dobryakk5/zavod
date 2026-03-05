"use client";

import { useEffect, useMemo, useRef, useState } from "react";

interface TelegramAuthButtonProps {
  botUsername: string;
  onAuthCallback: (user: any) => void;
  buttonSize?: "large" | "medium" | "small";
  cornerRadius?: number;
  showAvatar?: boolean;
  lang?: string;
  requestAccess?: "read" | "write";
}

const sanitizeBotUsername = (username: string) => {
  if (!username) {
    return "";
  }

  // Allow passing full t.me links or @username while keeping only the raw username
  const trimmed = username.trim();
  const withoutLink = trimmed
    .replace(/^https?:\/\/t\.me\//i, "")
    .replace(/^t\.me\//i, "");
  const normalized = withoutLink.replace(/^@+/, "").split(/[/?#]/)[0];

  return /^[a-zA-Z0-9_]+$/.test(normalized) ? normalized : "";
};

export function TelegramAuthButton({
  botUsername,
  onAuthCallback,
  buttonSize = "large",
  cornerRadius = 8,
  showAvatar = true,
  lang = "en",
  requestAccess = "read",
}: TelegramAuthButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const normalizedBotUsername = useMemo(() => sanitizeBotUsername(botUsername), [botUsername]);
  const [widgetError, setWidgetError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!containerRef.current || !normalizedBotUsername) return;
    setWidgetError(null);

    // Create global callback function
    const callbackName = `onTelegramAuth_${Date.now()}`;
    (window as any)[callbackName] = (user: any) => {
      onAuthCallback(user);
    };

    const container = containerRef.current;
    let cancelled = false;
    let probeInterval: number | null = null;
    let probeTimeout: number | null = null;

    const cleanupProbes = () => {
      if (probeInterval !== null) {
        window.clearInterval(probeInterval);
        probeInterval = null;
      }
      if (probeTimeout !== null) {
        window.clearTimeout(probeTimeout);
        probeTimeout = null;
      }
    };

    const widgetRendered = () => {
      if (!container.isConnected) return false;
      return Boolean(container.querySelector("iframe")) || container.childElementCount > 1;
    };

    const startRenderProbe = () => {
      cleanupProbes();
      probeInterval = window.setInterval(() => {
        if (cancelled) return;
        if (widgetRendered()) {
          cleanupProbes();
          setWidgetError(null);
        }
      }, 250);
      probeTimeout = window.setTimeout(() => {
        if (cancelled) return;
        if (!widgetRendered()) {
          setWidgetError(
            "Виджет Telegram не загрузился. Проверьте блокировщик рекламы, VPN/сеть и доступ к telegram.org."
          );
        }
        cleanupProbes();
      }, 4000);
    };

    // Create script element for Telegram widget
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", normalizedBotUsername);
    script.setAttribute("data-size", buttonSize);
    script.setAttribute("data-radius", cornerRadius.toString());
    script.setAttribute("data-userpic", showAvatar ? "true" : "false");
    script.setAttribute("data-lang", lang);
    script.setAttribute("data-onauth", `${callbackName}(user)`);
    script.setAttribute("data-request-access", requestAccess);
    script.async = true;
    script.onerror = () => {
      if (!cancelled) {
        cleanupProbes();
        setWidgetError("Не удалось загрузить скрипт Telegram. Проверьте доступ к telegram.org.");
      }
    };
    script.onload = () => {
      if (!cancelled) {
        startRenderProbe();
      }
    };

    // Clear container and append script
    container.innerHTML = "";
    container.appendChild(script);

    return () => {
      // Cleanup
      cancelled = true;
      cleanupProbes();
      delete (window as any)[callbackName];
    };
  }, [normalizedBotUsername, onAuthCallback, buttonSize, cornerRadius, showAvatar, lang, requestAccess, reloadKey]);

  if (!normalizedBotUsername) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-900">
        Некорректное имя Telegram-бота. Укажите username без ссылок и символа @ (например, solarlab_bot).
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div ref={containerRef} className="flex justify-center" />
      {widgetError && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-900">
          <div>{widgetError}</div>
          <button
            type="button"
            className="mt-2 underline underline-offset-2"
            onClick={() => setReloadKey((prev) => prev + 1)}
          >
            Попробовать снова
          </button>
        </div>
      )}
    </div>
  );
}
