import { useState, useEffect, useRef, useCallback } from "react";
import "./App.css";

// ── Communication constants ────────────────────────────────────────────────────
const API_KEY = "cryguard-secret-key-2024";
const WS_URL  = `ws://localhost:8080/ws?api_key=${API_KEY}`;
const API_URL = "http://localhost:8080";

// ── Alert logic constants ──────────────────────────────────────────────────────
// An alert fires when enough crying detections occur within a time window
// (prevents false positives from a single misclassified chunk)
const CRY_WINDOW   = 6;   // look at the last 6 seconds
const CRY_MIN_HITS = 3;   // 3 out of 6 detections triggers the alert

// Alert clears when enough silence occurs within a time window
const CALM_WINDOW   = 20; // look at the last 20 seconds
const CALM_MIN_HITS = 18; // 18 out of 20 seconds of silence = truly calm

export default function App() {
  // ── State ──────────────────────────────────────────────────────────────────
  const [isListening, setIsListening] = useState(false);          // whether the mic is active
  const [wsConnected, setWsConnected] = useState(false);          // whether WebSocket is connected
  const [result,      setResult]      = useState(null);           // latest classification result from server
  const [alertState,  setAlertState]  = useState(null);           // null | "crying" | "calm"
  const [alertTime,   setAlertTime]   = useState("");             // time of the last alert
  const [events,      setEvents]      = useState([]);             // event history list
  const [smsEnabled,  setSmsEnabled]  = useState(false);          // whether SMS is enabled
  const [phone,       setPhone]       = useState("");             // phone number for SMS
  const [phoneSaved,  setPhoneSaved]  = useState(false);          // whether the number was saved

  // ── Refs ────────────────────────────────────────────────────────────────────
  const ws           = useRef(null);                              // WebSocket connection
  const canvasRef    = useRef(null);                              // canvas element for waveform
  const barsRef      = useRef(Array(55).fill(0.04));              // waveform bar values (55 columns)
  const animRef      = useRef(null);                              // animation frame ID
  const scaledRef    = useRef(false);                             // whether canvas is scaled for DPI
  const cryWindowRef  = useRef([]);                               // crying time window (true/false per second)
  const calmWindowRef = useRef([]);                               // calm time window
  const lastVolRef   = useRef(0.04);                              // last received volume value
  const inAlertRef   = useRef(false);                             // whether an alert is currently active

  // ── WebSocket ──────────────────────────────────────────────────────────────
  // Connects to the server and auto-reconnects every 3 seconds if the connection drops.
  // The `destroyed` flag prevents reconnection after the component unmounts.
  useEffect(() => {
    let destroyed = false;

    const connect = () => {
      if (destroyed) return;
      const socket = new WebSocket(WS_URL);
      ws.current = socket;
      socket.onopen  = () => { if (!destroyed) setWsConnected(true); };
      socket.onclose = () => {
        if (destroyed) return;
        setWsConnected(false);
        setTimeout(connect, 3000);
      };
      socket.onerror = () => {};
      socket.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          setResult(data);

          // עדכון גרף — volume מהבאקנד (אותו מיקרופון שהמודל שומע)
          const level = typeof data.volume === "number"
            ? Math.max(0.02, data.volume)
            : 0.02;
          lastVolRef.current = level;
          barsRef.current = [...barsRef.current.slice(1), level];

          // לוגיקת התראה — חלון זמן במקום consecutive
          const isCry = data.label === "crying" && data.confidence >= 40;
          cryWindowRef.current  = [...cryWindowRef.current,  isCry].slice(-CRY_WINDOW);
          calmWindowRef.current = [...calmWindowRef.current, !isCry].slice(-CALM_WINDOW);

          const cryHits  = cryWindowRef.current.filter(Boolean).length;
          const calmHits = calmWindowRef.current.filter(Boolean).length;

          if (!inAlertRef.current && cryHits >= CRY_MIN_HITS) {
            inAlertRef.current = true;
            calmWindowRef.current = [];  // אפס — מתחילים לספור שקט רק מעכשיו
            const t = new Date().toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });
            setAlertState("crying");
            setAlertTime(t);
            setEvents(prev => [
              { type: "cry", text: "בכי זוהה", time: t },
              ...prev.slice(0, 9),
            ]);
          }

          if (inAlertRef.current && calmHits >= CALM_MIN_HITS) {
            inAlertRef.current = false;
            cryWindowRef.current  = [];
            calmWindowRef.current = [];
            const t = new Date().toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });
            setAlertState("calm");   // מציג "נרגע"
            setEvents(prev => [
              { type: "calm", text: "התינוק נרגע", time: t },
              ...prev.slice(0, 9),
            ]);
            // "נרגע" נעלם אחרי 8 שניות — "בוכה" נשאר עד שמגיע "נרגע"
            setTimeout(() => setAlertState(null), 8000);
          }        } catch (_) {}
      };
    };
    connect();
    return () => {
      destroyed = true;
      ws.current?.close();
    };
  }, []);

  // ── Waveform canvas ────────────────────────────────────────────────────────
  // Draws 55 rounded green bars according to volume data received from the server.
  // Runs on requestAnimationFrame and scales for devicePixelRatio (sharp on retina).
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const cssW = canvas.clientWidth;
    const cssH = canvas.clientHeight;

    if (!scaledRef.current || canvas.width !== cssW * window.devicePixelRatio) {
      canvas.width  = cssW * window.devicePixelRatio;
      canvas.height = cssH * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
      scaledRef.current = true;
    }

    const w = cssW;
    const h = cssH;
    ctx.clearRect(0, 0, w, h);

    const drawRoundedBar = (x, y, width, height, radius) => {
      const r = Math.min(radius, width / 2, height / 2);
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + width, y, x + width, y + height, r);
      ctx.arcTo(x + width, y + height, x, y + height, r);
      ctx.arcTo(x, y + height, x, y, r);
      ctx.arcTo(x, y, x + width, y, r);
      ctx.closePath();
      ctx.fill();
    };

    const bars = barsRef.current;
    const bw   = w / bars.length;

    bars.forEach((p, i) => {
      const bh    = Math.max(4, p * h * 0.82);
      const alpha = 0.28 + (i / bars.length) * 0.72;
      const fresh = i > bars.length - 4;
      const x = i * bw + 1.6;
      const y = (h - bh) / 2;
      const barW = Math.max(2.2, bw - 3.6);

      ctx.fillStyle = fresh
        ? `rgba(29,185,116,${alpha})`
        : `rgba(29,185,116,${alpha * 0.55})`;

      drawRoundedBar(x, y, barW, bh, 3.2);
    });
  }, []);

  const isListeningRef = useRef(false);
  useEffect(() => { isListeningRef.current = isListening; }, [isListening]);

  // ── Animation loop ─────────────────────────────────────────────────────────
  // Runs continuously on requestAnimationFrame.
  // Every 8 frames (~120ms) adds a small jitter to the bars for a natural live feel.
  useEffect(() => {
    let frameCount = 0;
    const loop = () => {
      frameCount++;
      // jitter around the last known volume — keeps the waveform alive
      if (isListeningRef.current && frameCount % 8 === 0) {
        const base  = lastVolRef.current;
        const jitter = (Math.random() - 0.5) * base * 0.4;
        const val   = Math.max(0.02, Math.min(1, base + jitter));
        barsRef.current = [...barsRef.current.slice(1), val];
      }
      drawCanvas();
      animRef.current = requestAnimationFrame(loop);
    };
    animRef.current = requestAnimationFrame(loop);
    const onResize = () => { scaledRef.current = false; };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", onResize);
    };
  }, [drawCanvas]);

  // ── Start / Stop ───────────────────────────────────────────────────────────
  // Sends POST to /start or /stop, and resets all local state on stop.
  const toggle = () => {
    const next = !isListening;
    setIsListening(next);
    if (!next) {
      barsRef.current = Array(55).fill(0.02);
      lastVolRef.current = 0.02;
      setResult(null);
      setAlertState(null);
      cryWindowRef.current  = [];
      calmWindowRef.current = [];
      inAlertRef.current    = false;
    }
    fetch(`${API_URL}/${next ? "start" : "stop"}`, {
      method: "POST",
      headers: { "X-API-Key": API_KEY },
    }).catch(() => {});
  };

  // ── SMS preferences ────────────────────────────────────────────────────────
  // Any change to smsEnabled is immediately sent to the server.
  useEffect(() => {
    fetch(`${API_URL}/prefs`, {
      method: "POST",
      headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ crying: smsEnabled }),
    }).catch(() => {});
  }, [smsEnabled]);

  const savePhone = async () => {
    try {
      await fetch(`${API_URL}/phone`, {
        method: "POST",
        headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      setPhoneSaved(true);
    } catch (_) {}
  };

  const isCrying = alertState === "crying";

  return (
    <div className="shell">

      {/* ── HEADER ── */}
      <header className="hdr">
        <div className="hdr-title">
          <h1>שומר הבית</h1>
          <span>Guardian Aura</span>
        </div>
        <div className="hdr-right">
          <div className="conn-pill">
            <span className={`conn-dot ${wsConnected ? "on" : "off"}`} />
            {wsConnected ? "מחובר" : "מנסה להתחבר..."}
          </div>
        </div>
      </header>

      {/* ── TOP ROW ── */}
      <div className="top-row">

        {/* גרף גלים */}
        <div className="panel">
          <p className="panel-title">פעילות קולית בזמן אמת</p>
          <div className="wave-wrap">
            <canvas ref={canvasRef} style={{ width: "100%", height: "110px" }} />
          </div>
        </div>

        {/* כפתור + סטטוס */}
        <div className="panel status-panel">
          <div className="orb-wrap">
            {isListening && <div className={`orb-ring ${isCrying ? "danger-ring" : ""}`} />}
            {isListening && <div className={`orb-ring d2 ${isCrying ? "danger-ring" : ""}`} />}
            <button
              className={`orb-btn ${isListening ? (isCrying ? "alert-state" : "active") : ""}`}
              onClick={toggle}
              aria-label={isListening ? "עצור" : "הפעל"}
            >
              {isListening
                ? <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                : <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
              }
            </button>
          </div>

          <div className="status-label">
            {!isListening && (
              <>
                <strong>כבוי</strong>
                <span className="sub">לחץ להפעלה</span>
              </>
            )}
            {isListening && !isCrying && (
              <>
                <strong style={{ color: "var(--accent)" }}>מאזין</strong>
                <span className="sub">סביבה תקינה</span>
              </>
            )}
            {isListening && isCrying && (
              <>
                <strong style={{ color: "var(--danger)" }}>התראה!</strong>
                <span className="sub">בכי זוהה</span>
              </>
            )}
          </div>

          {/* probabilities removed — not useful for end users */}
        </div>
      </div>

      {/* ── BOTTOM ROW ── */}
      <div className="bottom-row">

        {/* הגדרות SMS */}
        <div className="panel">
          <p className="panel-title">הגדרות התראה</p>

          <div className="toggle-row">
            <div>
              <span className="toggle-label">קבלת SMS על בכי</span>
              <span className="toggle-sub">שליחת הודעה לטלפון</span>
            </div>
            <button
              className={`switch ${smsEnabled ? "on" : ""}`}
              onClick={() => { setSmsEnabled(v => !v); setPhoneSaved(false); }}
              aria-label="הפעלת SMS"
            />
          </div>

          {smsEnabled && (
            <>
              <div className="divider" />
              <p style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 4 }}>מספר טלפון לשליחת SMS</p>
              <div className="phone-row">
                <input
                  type="tel"
                  placeholder="+972501234567"
                  value={phone}
                  onChange={e => { setPhone(e.target.value); setPhoneSaved(false); }}
                />
                <button className="btn-save" onClick={savePhone} disabled={!phone}>
                  {phoneSaved ? "✓ נשמר" : "שמור"}
                </button>
              </div>
            </>
          )}
        </div>

        {/* אירועים אחרונים */}
        <div className="panel">
          <p className="panel-title">אירועים אחרונים</p>
          {events.length === 0 ? (
            <p className="no-events">אין אירועים עדיין</p>
          ) : (
            <div className="events-list">
              {events.map((ev, i) => (
                <div key={i} className="event-item">
                  <div className={`event-dot ${ev.type === "calm" ? "calm" : ""}`} />
                  <div className="event-body">
                    <p className="event-title">{ev.text}</p>
                    <p className="event-time">{ev.time}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── ALERT BANNER ── */}
      {alertState && (
        <div className={`alert-banner ${alertState === "calm" ? "calm" : ""}`}>
          <div className="banner-icon-wrap">
            {isCrying
              ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width:16, height:16, color:"var(--danger)" }}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width:16, height:16, color:"var(--accent)" }}><polyline points="20 6 9 17 4 12"/></svg>
            }
          </div>
          <div className="banner-text">
            <strong>{isCrying ? "בכי זוהה" : "התינוק נרגע"}</strong>
            <span>{isCrying ? "זוהה בכי רציף — יש להיגש לתינוק" : "לא זוהה בכי זמן מה"}</span>
          </div>
          {alertTime && <span className="banner-time">{alertTime}</span>}
        </div>
      )}

      {/* ── FOOTER ── */}
      <footer className="ftr">
        <div className="ftr-mic">
          <span className={`mic-dot ${isListening ? "active" : ""}`} />
          {isListening ? "מיקרופון פעיל" : "מיקרופון כבוי"}
        </div>
        <span>v2.0</span>
      </footer>

    </div>
  );
}
