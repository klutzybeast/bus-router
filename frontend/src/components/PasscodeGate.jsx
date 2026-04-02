import React, { useState, useEffect, useRef, useCallback } from "react";
import { Lock, ShieldAlert } from "lucide-react";
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

function MaskedPasscodeInput({ value, onChange, onSubmit, disabled }) {
  const [displayChars, setDisplayChars] = useState([]);
  const hiddenInputRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (value.length === 0) {
      setDisplayChars([]);
    }
  }, [value]);

  const focusInput = () => {
    if (hiddenInputRef.current && !disabled) {
      hiddenInputRef.current.focus();
    }
  };

  useEffect(() => {
    focusInput();
  }, [disabled]);

  const handleInput = (e) => {
    if (disabled) return;
    const newVal = e.target.value;

    if (newVal.length > value.length) {
      const newChar = newVal[newVal.length - 1];
      const newChars = Array(Math.max(0, newVal.length - 1)).fill("\u2022");
      newChars.push(newChar);
      setDisplayChars(newChars);

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setDisplayChars(Array(newVal.length).fill("\u2022"));
      }, 500);
    } else {
      setDisplayChars(Array(newVal.length).fill("\u2022"));
    }

    onChange(newVal);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !disabled) {
      e.preventDefault();
      onSubmit();
    }
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const displayText = displayChars.join("");

  return (
    <div className="relative w-full" onClick={focusInput}>
      {/* Hidden real input that triggers mobile keyboard */}
      <input
        ref={hiddenInputRef}
        type="text"
        inputMode="text"
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck="false"
        className="absolute inset-0 w-full h-full opacity-0 z-10 cursor-text"
        style={{ fontSize: "16px" }}
        data-testid="passcode-input"
      />
      {/* Visible display */}
      <div
        className={`w-full px-4 py-3 rounded-lg border-2 bg-white text-lg text-center min-h-[52px] flex items-center justify-center ${
          disabled
            ? "border-gray-300 opacity-50 cursor-not-allowed"
            : "border-[#2b579a] cursor-text"
        }`}
        style={{ fontFamily: "monospace", fontSize: "1.25rem", letterSpacing: "0.3em", color: "#000" }}
      >
        {displayText || <span className="text-gray-400" style={{ letterSpacing: "0.1em" }}>Enter passcode</span>}
      </div>
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

  const lock = useCallback(() => {
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_TIMESTAMP_KEY);
    setIsAuthenticated(false);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
  }, []);

  const resetActivityTimer = useCallback(() => {
    warningShownRef.current = false;
    sessionStorage.setItem(AUTH_TIMESTAMP_KEY, String(Date.now()));

    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (activityTimerRef.current) clearTimeout(activityTimerRef.current);

    warningTimerRef.current = setTimeout(() => {
      if (!warningShownRef.current) {
        warningShownRef.current = true;
        toast.warning("Session will lock in 5 minutes due to inactivity", { duration: 10000 });
      }
    }, INACTIVITY_WARNING_MS);

    activityTimerRef.current = setTimeout(() => {
      lock();
      toast.error("Session locked due to inactivity");
    }, INACTIVITY_TIMEOUT_MS);
  }, [lock]);

  const authenticate = useCallback(() => {
    const token = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    sessionStorage.setItem(AUTH_TOKEN_KEY, token);
    sessionStorage.setItem(AUTH_TIMESTAMP_KEY, String(Date.now()));
    setIsAuthenticated(true);
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
      style={{ background: "#ffffff" }}
      data-testid="passcode-gate"
    >
      {/* Subtle background pattern */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none" style={{ background: "linear-gradient(180deg, #f0f4fa 0%, #ffffff 50%, #f0f4fa 100%)" }} />

      <div className="relative w-full max-w-sm mx-4">
        <div className="bg-white rounded-2xl border-2 border-[#2b579a]/20 p-8 shadow-xl">
          {/* Camp Logo */}
          <div className="flex flex-col items-center mb-6">
            <img
              src="/camp-logo.png"
              alt="Rolling River Day Camp"
              className="w-32 h-32 object-contain"
              data-testid="camp-logo"
            />
            <p className="text-[#2b579a]/60 text-sm mt-3 text-center font-medium">
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
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2" data-testid="passcode-error">
                <ShieldAlert className="w-4 h-4 text-red-500 flex-shrink-0" />
                <span className="text-red-600 text-sm">{error}</span>
              </div>
            )}

            {locked && lockCountdown > 0 && (
              <div className="text-center" data-testid="lockout-timer">
                <div className="inline-flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-lg px-4 py-2">
                  <Lock className="w-4 h-4 text-orange-500" />
                  <span className="text-orange-600 text-sm font-mono">
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
                  ? "#b0bec5"
                  : "#2b579a",
                boxShadow: locked || checking || !passcode.trim()
                  ? "none"
                  : "0 4px 12px rgba(43,87,154,0.3)",
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

        <p className="text-center text-[#2b579a]/30 text-xs mt-6">
          Bus Route Management System
        </p>
      </div>
    </div>
  );
}
