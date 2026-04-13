"use client";

import { useState, useRef, useEffect } from "react";
import { sendChatMessage, type ChatMessage } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const SUGGESTION_KEYS = [
  "chat.suggestBtc",
  "chat.suggestUnusual",
  "chat.suggestRegime",
  "chat.suggestMica",
  "chat.suggestFearGreed",
  "chat.suggestDefi",
  "chat.suggestFunding",
  "chat.suggestOverview",
] as const;

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-[85%] ${isUser ? "order-2" : "order-1"}`}>
        {/* Avatar */}
        <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
          <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center text-xs font-bold ${
            isUser ? "bg-blue-600 text-white" : "bg-gradient-to-br from-purple-600 to-blue-600 text-white"
          }`}>
            {isUser ? "U" : "AI"}
          </div>
          <div>
            <div className={`rounded-2xl px-4 py-3 ${
              isUser
                ? "bg-blue-600 text-white rounded-br-md"
                : "bg-slate-800 text-slate-200 rounded-bl-md border border-slate-700"
            }`}>
              {/* Render markdown-like content (safe, no dangerouslySetInnerHTML) */}
              <div className="text-sm leading-relaxed whitespace-pre-wrap">
                {message.content.split("\n").map((line, i) => {
                  // Parse bold (**text**) into React elements safely
                  const parts = line.replace(/^- /, "").split(/(\*\*[^*]+\*\*)/g);
                  const rendered = parts.map((part, j) => {
                    if (part.startsWith("**") && part.endsWith("**")) {
                      return <strong key={j}>{part.slice(2, -2)}</strong>;
                    }
                    return <span key={j}>{part}</span>;
                  });

                  if (line.startsWith("- ")) {
                    return (
                      <div key={i} className="flex gap-2 ml-1">
                        <span className="text-slate-500">-</span>
                        <span>{rendered}</span>
                      </div>
                    );
                  }
                  return <div key={i}>{rendered}</div>;
                })}
              </div>
            </div>

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {message.sources.map((s, i) => (
                  <span key={i} className="px-2 py-0.5 bg-slate-800/50 rounded text-[10px] text-slate-500 border border-slate-700/50">
                    {s}
                  </span>
                ))}
              </div>
            )}

            {/* Suggested Actions */}
            {message.suggested_actions && message.suggested_actions.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {message.suggested_actions.map((action, i) => (
                  <button
                    key={i}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors"
                  >
                    {action}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const message = text || input.trim();
    if (!message || loading) return;

    const userMsg: ChatMessage = { role: "user", content: message };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await sendChatMessage(message);
      const aiMsg: ChatMessage = {
        role: "assistant",
        content: response.reply,
        data: response.data,
        sources: response.sources,
        suggested_actions: response.suggested_actions,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: t("chat.errorMessage") },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex-shrink-0 pb-4">
        <h1 className="text-2xl font-bold text-white">{t("chat.title")}</h1>
        <p className="text-slate-400 text-sm mt-1">{t("chat.subtitle")}</p>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto pr-2 pb-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">{t("chat.welcomeHeading")}</h2>
            <p className="text-sm text-slate-400 mb-8 text-center max-w-md">
              {t("chat.welcomeBody")}
            </p>
            <div className="grid grid-cols-2 gap-2 max-w-lg">
              {SUGGESTION_KEYS.map((key) => {
                const label = t(key);
                return (
                  <button
                    key={key}
                    onClick={() => handleSend(label)}
                    className="px-4 py-3 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-xl text-xs text-slate-300 text-left transition-colors"
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            {loading && (
              <div className="flex justify-start mb-4">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-xs font-bold text-white">
                    AI
                  </div>
                  <div className="bg-slate-800 rounded-2xl rounded-bl-md px-4 py-3 border border-slate-700">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 pt-4 border-t border-slate-800">
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={t("chat.placeholder")}
            className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-colors"
            disabled={loading}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl text-sm font-medium transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
