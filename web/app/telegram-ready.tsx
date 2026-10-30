"use client";

import { useEffect } from "react";

type TelegramWebApp = { ready: () => void; expand: () => void };

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function TelegramReady() {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    webApp?.ready();
    webApp?.expand();
  }, []);

  return null;
}
