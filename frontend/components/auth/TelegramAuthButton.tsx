"use client";

import { useEffect, useMemo, useRef } from "react";

interface TelegramAuthButtonProps {
  botUsername: string;
  onAuthCallback: (user: any) => void;
  buttonSize?: "large" | "medium" | "small";
  cornerRadius?: number;
  showAvatar?: boolean;
  lang?: string;
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
}: TelegramAuthButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const normalizedBotUsername = useMemo(() => sanitizeBotUsername(botUsername), [botUsername]);

  useEffect(() => {
    if (!containerRef.current || !normalizedBotUsername) return;

    // Create global callback function
    const callbackName = `onTelegramAuth_${Date.now()}`;
    (window as any)[callbackName] = (user: any) => {
      onAuthCallback(user);
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
    script.setAttribute("data-request-access", "write");
    script.async = true;

    // Clear container and append script
    containerRef.current.innerHTML = "";
    containerRef.current.appendChild(script);

    return () => {
      // Cleanup
      delete (window as any)[callbackName];
    };
  }, [normalizedBotUsername, onAuthCallback, buttonSize, cornerRadius, showAvatar, lang]);

  if (!normalizedBotUsername) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-900">
        Некорректное имя Telegram-бота. Укажите username без ссылок и символа @ (например, solarlab_bot).
      </div>
    );
  }

  return <div ref={containerRef} />;
}
