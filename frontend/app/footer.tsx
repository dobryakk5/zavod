"use client";

import { motion } from "framer-motion";

export default function LandingFooter() {
  return (
    <motion.footer
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="w-full mt-12 border-t"
    >
      <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col md:flex-row justify-between items-start gap-6">
        <div>
          <div className="text-lg font-semibold">Fibonatty</div>
          <div className="text-sm text-gray-600 mt-1">Marketing · AI Lab</div>
          <div className="text-sm text-gray-500 mt-1">AI‑система для роста, а не генерации текстов</div>
          <div className="text-sm text-gray-600 mt-1">ИНН: 772305668632</div>
        </div>
        <div className="flex gap-8 text-sm text-gray-600">
          <div>
            <div className="font-semibold">Услуги</div>
            <div className="mt-2">AI-контент<br />Маркетинг<br />Аналитика</div>
          </div>
          <div>
            <div className="font-semibold">Контакты</div>
            <div className="mt-2">hello@Fibonatty.ru<br />Telegram: @Fibonatty_bot</div>
          </div>
        </div>
      </div>
    </motion.footer>
  );
}
