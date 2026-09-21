import React, { useState, useMemo } from "react";
import {
  Plus,
  Trash2,
  MessageSquare,
  Search,
  X,
  Clock,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { StoredSession } from "../lib/api";

interface ChatHistorySidebarProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: StoredSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
  onClearAll: () => void;
  userId: string;
}

export const ChatHistorySidebar: React.FC<ChatHistorySidebarProps> = ({
  isOpen,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onClearAll,
  userId,
}) => {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSessions = useMemo(() => {
    if (!searchTerm.trim()) return sessions;
    const term = searchTerm.toLowerCase();
    return sessions.filter((s) => {
      const matchTitle = s.title.toLowerCase().includes(term);
      const matchMsg = s.messages.some(
        (m: any) => typeof m.text === "string" && m.text.toLowerCase().includes(term)
      );
      return matchTitle || matchMsg;
    });
  }, [sessions, searchTerm]);

  // Group sessions by date
  const groupedSessions = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 24 * 60 * 60 * 1000;
    const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000;

    const groups: { [key: string]: StoredSession[] } = {
      Today: [],
      Yesterday: [],
      "Previous 7 Days": [],
      Older: [],
    };

    filteredSessions.forEach((s) => {
      const time = s.updatedAt || s.createdAt || 0;
      if (time >= todayStart) {
        groups.Today.push(s);
      } else if (time >= yesterdayStart) {
        groups.Yesterday.push(s);
      } else if (time >= weekStart) {
        groups["Previous 7 Days"].push(s);
      } else {
        groups.Older.push(s);
      }
    });

    return groups;
  }, [filteredSessions]);

  const formatTime = (timestamp: number) => {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex animate-fadeIn">
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sidebar Drawer Container */}
      <aside className="relative z-10 w-full max-w-xs sm:max-w-sm bg-white border-r border-octo-border flex flex-col h-full shadow-2xl animate-slideInLeft">
        {/* Header */}
        <div className="p-4 border-b border-octo-border flex items-center justify-between bg-octo-surface-warm/40">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-octo-orange" />
            <h2 className="text-base font-bold tracking-tight text-octo-charcoal">
              Chat History
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-octo-muted hover:text-octo-charcoal hover:bg-octo-surface-warm transition-colors"
            title="Close history drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Action Button: New Chat */}
        <div className="p-4 pb-2 space-y-3">
          <button
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="w-full h-11 px-4 rounded-btn bg-octo-orange hover:bg-octo-orange-hover text-white font-semibold text-sm transition-all duration-200 flex items-center justify-center gap-2 shadow-sm active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" />
            <span>New Chat</span>
          </button>

          {/* Search Box */}
          <div className="relative">
            <Search className="h-4 w-4 absolute left-3 top-3 text-octo-muted pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search conversations..."
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg bg-octo-bg border border-octo-border text-octo-charcoal placeholder-octo-muted focus:outline-none focus:border-octo-orange transition-colors"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute right-2.5 top-2.5 text-octo-muted hover:text-octo-charcoal"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-4">
          {sessions.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-octo-muted space-y-2">
              <Clock className="h-8 w-8 text-octo-border" />
              <p className="text-sm font-medium">No saved conversations</p>
              <p className="text-xs text-octo-muted">
                Your diagnostic queries and repair sessions will be preserved here.
              </p>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="text-center py-8 text-octo-muted text-xs">
              No conversations matching &quot;{searchTerm}&quot;
            </div>
          ) : (
            Object.entries(groupedSessions).map(([groupTitle, groupItems]) => {
              if (groupItems.length === 0) return null;
              return (
                <div key={groupTitle} className="space-y-1.5">
                  <div className="px-2 py-1 text-[11px] font-bold uppercase tracking-wider text-octo-muted">
                    {groupTitle}
                  </div>
                  {groupItems.map((session) => {
                    const isActive = session.id === activeSessionId;
                    return (
                      <div
                        key={session.id}
                        onClick={() => {
                          onSelectSession(session.id);
                          onClose();
                        }}
                        className={`group relative flex items-center justify-between p-2.5 rounded-xl cursor-pointer transition-all duration-150 border ${
                          isActive
                            ? "bg-octo-orange-light border-octo-orange text-octo-orange shadow-sm font-medium"
                            : "bg-white border-transparent hover:bg-octo-surface-warm/60 hover:border-octo-border text-octo-charcoal"
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0 pr-2">
                          <MessageSquare
                            className={`h-4 w-4 shrink-0 ${
                              isActive ? "text-octo-orange" : "text-octo-muted group-hover:text-octo-charcoal"
                            }`}
                          />
                          <div className="min-w-0">
                            <p className="text-xs font-semibold truncate leading-snug">
                              {session.title || "Technical inquiry"}
                            </p>
                            <p className="text-[10px] text-octo-muted truncate flex items-center gap-1.5 mt-0.5">
                              <span>{session.messages.length} messages</span>
                              {session.updatedAt && (
                                <>
                                  <span>•</span>
                                  <span>{formatTime(session.updatedAt)}</span>
                                </>
                              )}
                            </p>
                          </div>
                        </div>

                        {/* Right Actions: Delete on hover */}
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            onClick={(e) => onDeleteSession(session.id, e)}
                            title="Delete conversation"
                            className="p-1 rounded text-octo-muted hover:text-red-600 hover:bg-red-50 transition-colors sm:opacity-0 sm:group-hover:opacity-100"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                          <ChevronRight
                            className={`h-3.5 w-3.5 transition-transform ${
                              isActive ? "text-octo-orange" : "text-octo-border group-hover:text-octo-muted"
                            }`}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>

        {/* Footer info & Clear All */}
        <div className="p-3 border-t border-octo-border bg-octo-surface-warm/30 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-octo-muted px-1">
            <span className="truncate max-w-[170px]" title={`User ID: ${userId}`}>
              User: <span className="font-mono text-[10px] font-semibold">{userId.slice(0, 10)}...</span>
            </span>
            <span>{sessions.length} threads</span>
          </div>

          {sessions.length > 0 && (
            <button
              onClick={onClearAll}
              className="w-full py-1.5 px-3 rounded-lg text-xs font-medium text-red-700 hover:bg-red-50 transition-colors flex items-center justify-center gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Clear all history</span>
            </button>
          )}
        </div>
      </aside>
    </div>
  );
};
