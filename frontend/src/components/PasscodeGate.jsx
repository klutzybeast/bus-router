import React, { useState, useEffect, useRef, useCallback } from "react";
import { Lock, Eye, EyeOff, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

const PASSCODE_HASH = "b7065804da716830f45517bd6fcb311b75edabc58375df300cb584063cc0bc81";
const AUTH_TOKEN_KEY = "rrdc_auth_token";
const AUTH_TIMESTAMP_KEY = "rrdc_auth_ts";
const MAX_ATTEMPTS = 5;
const LOCKOUT_SECONDS = 60;
const INACTIVITY_TIMEOUT_MS = 45 * 60 * 1000;
const INACTIVITY_WARNING_MS = 40 * 60 * 1000;

async function sha256(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

function CampLogo() {
  return (
    <div className="flex flex-col items-center" data-testid="camp-logo">
      <svg width="120" height="120" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
        <circle cx="60" cy="60" r="58" fill="#1e3a5f" stroke="#f0c040" strokeWidth="3" />
        <path d="M25 78 Q40 55 60 70 Q80 85 95 60" stroke="#4da6e8" strokeWidth="4" fill="none" strokeLinecap="round" />
        <path d="M20 82 Q38 62 60 74 Q82 86 100 65" stroke="#3b82f6" strokeWidth="3" fill="none" opacity="0.5" strokeLinecap="round" />
        <polygon points="45,52 50,38 55,52" fill="#2d6a4f" />
        <polygon points="50,55 55,35 60,55" fill="#40916c" />
        <polygon points="62,50 67,32 72,50" fill="#2d6a4f" />
        <polygon points="67,53 72,36 77,53" fill="#40916c" />
        <rect x="49" y="52" width="2" height="6" fill="#6b4423" />
        <rect x="54" y="55" width="2" height="5" fill="#6b4423" />
        <rect x="66" y="50" width="2" height="6" fill="#6b4423" />
        <rect x="71" y="53" width="2" height="5" fill="#6b4423" />
        <circle cx="85" cy="30" r="10" fill="#f0c040" opacity="0.9" />
      </svg>
    </div>
  );
}

function MaskedPasscodeInput({ value, onChange, onSubmit, disabled }) {
  const [displayValue, setDisplayValue] = useState("");
  const timerRef = useRef(null);
  const inputRef = useRef(null);
  const realValueRef = useRef(value);

  useEffect(() => {
    realValueRef.current = value;
  }, [value]);

  useEffect(() => {
    if (value.length === 0) {
      setDisplayValue("");
    }
  }, [value]);

  const handleKeyDown = (e) => {
    if (disabled) return;
    if (e.key === "Enter") {
      e.preventDefault();
      onSubmit();
      return;
    }
    if (e.key === "Backspace") {
      e.preventDefault();
      const newVal = realValueRef.current.slice(0, -1);
      onChange(newVal);
      setDisplayValue("\u2022".repeat(newVal.length));
      return;
    }
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      const newVal = realValueRef.current + e.key;
      onChange(newVal);

      const masked = "\u2022".repeat(Math.max(0, newVal.length - 1));
      setDisplayValue(masked + e.key);

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setDisplayValue("\u2022".repeat(newVal.length));
      }, 500);
    }
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled]);

  return (
    <div className="relative w-full">
      <input
        ref={inputRef}
        type="text"
        value={displayValue}
        readOnly
        onKeyDown={handleKeyDown}
        disabled={disabled}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck="false"
        placeholder="Enter passcode"
        className="w-full px-4 py-3 rounded-lg border-2 border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none text-lg tracking-widest text-center disabled:opacity-50 disabled:cursor-not-allowed"
        style={{ color: "#000", fontFamily: "monospace", fontSize: "1.25rem", letterSpacing: "0.3em", caretColor: "transparent" }}
        data-testid="passcode-input"
      />
    </div>
  );
}

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const activityTimerRef = useRef(null);
  const warningTimerRef = useRef(null);
  const warningShownRef = useRef(false);

  const checkSession = useCallback(() => {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
    const ts = sessionStorage.getItem(AUTH_TIMESTAMP_KEY);
    if (token && ts) {
      const elapsed = Date.now() - parseInt(ts, 10);
      if (elapsed < INACTIVITY_TIMEOUT_MS) {
        return true;
      }
      sessionStorage.removeItem(AUTH_TOKEN_KEY);
      sessionStorage.removeItem(AUTH_TIMESTAMP_KEY);
    }
    return false;
  }, []);

  const resetActivityTimer = useCallback(() => {
    if (!isAuthenticated) return;
    warningShownRef.current = false;
    sessionStorage.setItem(AUTH_TIMESTAMP_KEY, String(Date.now()));

    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (activityTimerRef.current) clearTimeout(activityTimerRef.current);

    warningTimerRef.current = setTimeout(() => {
      if (isAuthenticated && !warningShownRef.current) {
        warningShownRef.current = true;
        toast.warning("Session will lock in 5 minutes due to inactivity", { duration: 10000 });
      }
    }, INACTIVITY_WARNING_MS);

    activityTimerRef.current = setTimeout(() => {
      lock();
      toast.error("Session locked due to inactivity");
    }, INACTIVITY_TIMEOUT_MS);
  }, [isAuthenticated]);

  const authenticate = useCallback(() => {
    const token = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    sessionStorage.setItem(AUTH_TOKEN_KEY, token);
    sessionStorage.setItem(AUTH_TIMESTAMP_KEY, String(Date.now()));
    setIsAuthenticated(true);
  }, []);

  const lock = useCallback(() => {
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_TIMESTAMP_KEY);
    setIsAuthenticated(false);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
  }, []);

  useEffect(() => {
    const valid = checkSession();
    setIsAuthenticated(valid);
    setInitialized(true);
  }, [checkSession]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const events = ["mousedown", "keydown", "touchstart", "scroll", "mousemove"];
    const handler = () => resetActivityTimer();

    events.forEach((ev) => window.addEventListener(ev, handler, { passive: true }));
    resetActivityTimer();

    return () => {
      events.forEach((ev) => window.removeEventListener(ev, handler));
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
    };
  }, [isAuthenticated, resetActivityTimer]);

  return { isAuthenticated, initialized, authenticate, lock };
}

export function LockButton({ onLock }) {
  return (
    <button
      onClick={onLock}
      className="fixed top-3 right-3 z-[9999] bg-white/90 hover:bg-red-50 border border-gray-300 hover:border-red-400 rounded-full p-2 shadow-md transition-all duration-200 group"
      title="Lock session"
      data-testid="lock-session-btn"
    >
      <Lock className="w-5 h-5 text-gray-500 group-hover:text-red-600 transition-colors" />
    </button>
  );
}

export default function PasscodeGate({ onAuthenticated }) {
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState(0);
  const [locked, setLocked] = useState(false);
  const [lockCountdown, setLockCountdown] = useState(0);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!locked) return;
    setLockCountdown(LOCKOUT_SECONDS);
    const interval = setInterval(() => {
      setLockCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setLocked(false);
          setAttempts(0);
          setError("");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [locked]);

  const handleSubmit = async () => {
    if (checking || locked || !passcode.trim()) return;
    setChecking(true);
    setError("");

    try {
      const hash = await sha256(passcode);
      if (hash === PASSCODE_HASH) {
        onAuthenticated();
        setPasscode("");
        setAttempts(0);
      } else {
        const newAttempts = attempts + 1;
        setAttempts(newAttempts);
        setPasscode("");
        if (newAttempts >= MAX_ATTEMPTS) {
          setLocked(true);
          setError(`Too many failed attempts. Locked for ${LOCKOUT_SECONDS} seconds.`);
        } else {
          setError(`Invalid passcode (${MAX_ATTEMPTS - newAttempts} attempts remaining)`);
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
    } catch {
      setError("Authentication error");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[10000] flex items-center justify-center"
      style={{
        background: "linear-gradient(145deg, #0f2742 0%, #1a3a5c 40%, #1e4d6e 70%, #0d2137 100%)",
      }}
      data-testid="passcode-gate"
    >
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-10 left-10 w-72 h-72 bg-blue-400/5 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-yellow-400/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm mx-4">
        <div className="bg-white/10 backdrop-blur-xl rounded-2xl border border-white/20 p-8 shadow-2xl">
          <div className="flex flex-col items-center mb-8">
            <CampLogo />
            <h1 className="text-xl font-bold text-white mt-4 text-center tracking-wide">
              Rolling River Day Camp
            </h1>
            <p className="text-blue-200/70 text-sm mt-1 text-center">
              Authorized Access Only
            </p>
          </div>

          <div className="space-y-4">
            <MaskedPasscodeInput
              value={passcode}
              onChange={setPasscode}
              onSubmit={handleSubmit}
              disabled={locked || checking}
            />

            {error && (
              <div className="flex items-center gap-2 bg-red-500/20 border border-red-400/30 rounded-lg px-3 py-2" data-testid="passcode-error">
                <ShieldAlert className="w-4 h-4 text-red-300 flex-shrink-0" />
                <span className="text-red-200 text-sm">{error}</span>
              </div>
            )}

            {locked && lockCountdown > 0 && (
              <div className="text-center" data-testid="lockout-timer">
                <div className="inline-flex items-center gap-2 bg-orange-500/20 border border-orange-400/30 rounded-lg px-4 py-2">
                  <Lock className="w-4 h-4 text-orange-300" />
                  <span className="text-orange-200 text-sm font-mono">
                    Retry in {lockCountdown}s
                  </span>
                </div>
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={locked || checking || !passcode.trim()}
              className="w-full py-3 rounded-lg font-semibold text-white transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: locked || checking || !passcode.trim()
                  ? "rgba(255,255,255,0.1)"
                  : "linear-gradient(135deg, #3b82f6, #2563eb)",
                boxShadow: locked || checking || !passcode.trim()
                  ? "none"
                  : "0 4px 15px rgba(59,130,246,0.4)",
              }}
              data-testid="passcode-submit-btn"
            >
              {checking ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round" />
                  </svg>
                  Verifying...
                </span>
              ) : (
                "Enter"
              )}
            </button>
          </div>
        </div>

        <p className="text-center text-blue-300/30 text-xs mt-6">
          Bus Route Management System
        </p>
      </div>
    </div>
  );
}
