"use client";

import { useEffect, useRef } from "react";

interface TelegramAuthButtonProps {
  botUsername: string;
  onAuthCallback: (user: any) => void;
  buttonSize?: "large" | "medium" | "small";
  cornerRadius?: number;
  showAvatar?: boolean;
  lang?: string;
}

export function TelegramAuthButton({
  botUsername,
  onAuthCallback,
  buttonSize = "large",
  cornerRadius = 8,
  showAvatar = true,
  lang = "en",
}: TelegramAuthButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create global callback function
    const callbackName = `onTelegramAuth_${Date.now()}`;
    (window as any)[callbackName] = (user: any) => {
      onAuthCallback(user);
    };

    // Create script element for Telegram widget
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", botUsername);
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
  }, [botUsername, onAuthCallback, buttonSize, cornerRadius, showAvatar, lang]);

  return <div ref={containerRef} />;
}
