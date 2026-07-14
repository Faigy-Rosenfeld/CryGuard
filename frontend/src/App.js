import { useState, useEffect, useRef } from "react";
import "./App.css";

const API_KEY = "sos-secret-key-2024";
const WS_URL = `ws://localhost:8080/ws?api_key=${API_KEY}`;
const API_URL = "http://localhost:8080";

const LABELS = {
  scream:     { text: "צרחה",  color: "#e74c3c" },
  crying:     { text: "בכי",   color: "#e67e22" },
  explosion:  { text: "פיצוץ", color: "#c0392b" },
  background: { text: "רקע",   color: "#1D9E75" },
};

const ICONS = {
  scream: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>,
  crying: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 010 7"/></svg>,
  explosion: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
  background: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.8A9 9 0 1111.2 3 7 7 0 0021 12.8z"/></svg>,
};

export default function App() {
  const [isListening, setIsListening] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [result, setResult] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [phone, setPhone] = useState("");
  const [phoneSaved, setPhoneSaved] = useState(false);
  const [alertPrefs, setAlertPrefs] = useState({ crying: true, scream: true, explosion: true });
  const ws = useRef(null);
  const canvasRef = useRef(null);
  const pointsRef = useRef(Array.from({ length: 90 }, () => 0.05));
  const scaledRef = useRef(false);
  const animRef = useRef(null);

  // WebSocket
  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket(WS_URL);
      ws.current.onopen = () => setWsConnected(true);
      ws.current.onclose = () => { setWsConnected(false); setTimeout(connect, 3000); };
      ws.current.onmessage = (e) => {
        const data = JSON.parse(e.data);
        setResult(data);
        const level = data.probs ? (100 - (data.probs.background ?? 100)) / 100 : 0.05;
        pointsRef.current.shift();
        pointsRef.current.push(Math.max(0.05, level + Math.random() * 0.04));
        if (data.alert) {
          setAlerts((prev) => [
            { ...data, time: new Date().toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" }) },
            ...prev.slice(0, 9),
          ]);
        }
      };
    };
    connect();
    return () => ws.current?.close();
  }, []);

  // Canvas — רץ רק כשמאזינים
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const draw = () => {
      if (!scaledRef.current) {
        canvas.width = canvas.clientWidth * 2;
        canvas.height = canvas.clientHeight * 2;
        ctx.scale(2, 2);
        scaledRef.current = true;
      }
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const pts = pointsRef.current;
      const bw = w / pts.length;
      pts.forEach((p, i) => {
        const bh = p * h * 0.9;
        ctx.fillStyle = i > pts.length - 5 ? "#0F6E56" : "rgba(29,158,117,0.35)";
        ctx.fillRect(i * bw, (h - bh) / 2, bw * 0.55, bh);
      });
    };

    if (isListening) {
      const tick = () => {
        pointsRef.current.shift();
        pointsRef.current.push(0.08 + Math.random() * 0.15);
        draw();
        animRef.current = requestAnimationFrame(tick);
      };
      // עצור אנימציה ישנה
      cancelAnimationFrame(animRef.current);
      // התחל אנימציה חדשה בקצב איטי
      let last = 0;
      const throttled = (ts) => {
        if (ts - last > 300) { tick(); last = ts; }
        else animRef.current = requestAnimationFrame(throttled);
      };
      animRef.current = requestAnimationFrame(throttled);
    } else {
      cancelAnimationFrame(animRef.current);
      draw(); // ציור סטטי
    }

    const onResize = () => { scaledRef.current = false; draw(); };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", onResize);
    };
  }, [isListening]);

  // סנכרן העדפות SMS לbackend בכל שינוי
  useEffect(() => {
    fetch(`${API_URL}/prefs`, {
      method: "POST",
      headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify(alertPrefs),
    }).catch(() => {});
  }, [alertPrefs]);

  const toggle = () => {
    const endpoint = isListening ? "stop" : "start";
    // עדכן UI מיד — לא מחכים לתשובת השרת
    const next = !isListening;
    setIsListening(next);
    if (!next) setResult(null);
    fetch(`${API_URL}/${endpoint}`, { method: "POST", headers: { "X-API-Key": API_KEY } }).catch(() => {});
  };

  const savePhone = async () => {
    try {
      await fetch(`${API_URL}/phone`, {
        method: "POST",
        headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
    } catch {}
    setPhoneSaved(true);
  };

  const isAlert = result?.alert && isListening;
  const currentLabel = result?.label ?? "background";

  return (
    <div className="card">

      {/* HEADER */}
      <div className="header">
        <div>
          <h1>שומר הבית</h1>
          <p className="subtitle">Guardian Aura</p>
        </div>
        <span className={`conn-dot ${wsConnected ? "on" : "off"}`} title={wsConnected ? "מחובר" : "לא מחובר"} />
      </div>

      {/* TOP ROW */}
      <div className="top-row">

        {/* גרף */}
        <div className="panel">
          <p className="panel-label">פעילות קולית בזמן אמת</p>
          <canvas ref={canvasRef} height="90" style={{ width: "100%", display: "block" }} />
          <div className="wave-axis">
            <span>36ש</span><span>24ש</span><span>12ש</span><span className="now">now</span>
          </div>
        </div>

        {/* סטטוס + כפתור */}
        <div className="panel status-panel">
          <div className="pulse-wrap">
            {isListening && <div className={`ring${isAlert ? " alert-ring" : ""}`} />}
            {isListening && <div className={`ring delay${isAlert ? " alert-ring" : ""}`} />}
            <button
              className={`main-btn ${isListening ? (isAlert ? "btn-alert" : "btn-active") : "btn-idle"}`}
              onClick={toggle}
              aria-label={isListening ? "עצור האזנה" : "התחל האזנה"}
            >
              {isListening ? (
                <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
              )}
            </button>
          </div>

          <p className="status-text">
            {!isListening && <><strong>כבוי</strong><br /><span className="sub">לחץ להפעלה</span></>}
            {isListening && !isAlert && <><strong style={{ color: "var(--accent-dark)" }}>מאזין...</strong><br /><span className="sub">סביבה תקינה</span></>}
            {isListening && isAlert && <><strong style={{ color: LABELS[currentLabel]?.color }}>⚠ {LABELS[currentLabel]?.text}</strong><br /><span className="sub">התרעה פעילה</span></>}
          </p>

          {/* הסתברויות — מוצגות רק כשמאזינים */}
          {isListening && result && (
            <div className="probs-mini">
              {Object.entries(result.probs).map(([cat, prob]) => (
                <div key={cat} className="prob-row">
                  <span className="prob-label">{LABELS[cat]?.text}</span>
                  <div className="bar-bg">
                    <div className="bar" style={{ width: `${prob}%`, background: LABELS[cat]?.color }} />
                  </div>
                  <span className="prob-pct">{prob}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* BOTTOM ROW */}
      <div className="bottom-row">

        {/* הגדרות */}
        <div className="panel">
          <p className="settings-label">הגדרות SMS</p>
          {[["crying", "בכי"], ["scream", "צרחה"], ["explosion", "פיצוץ"]].map(([key, label]) => (
            <div className="toggle-row" key={key}>
              <span className="label">SMS על {label}</span>
              <button
                className={`switch${alertPrefs[key] ? "" : " off"}`}
                onClick={() => setAlertPrefs(p => ({ ...p, [key]: !p[key] }))}
                aria-label={`התרעת ${label}`}
              />
            </div>
          ))}
          <div className="divider" />
          <p className="settings-label" style={{ marginBottom: 8 }}>מספר לשליחת SMS</p>
          <div className="phone-section">
            <input
              type="tel"
              placeholder="+972501234567"
              value={phone}
              onChange={(e) => { setPhone(e.target.value); setPhoneSaved(false); }}
            />
            <button className="btn-save" onClick={savePhone} disabled={!phone}>
              {phoneSaved ? "✓" : "שמור"}
            </button>
          </div>
        </div>

        {/* אירועים */}
        <div className="panel">
          <p className="alerts-label">אירועים אחרונים</p>
          {alerts.length === 0 ? (
            <p className="no-alerts">אין אירועים עדיין</p>
          ) : (
            alerts.slice(0, 5).map((a, i) => (
              <div key={i} className="alert-item">
                <span className={`alert-icon ${a.label !== "background" ? "danger" : ""}`}>
                  {ICONS[a.label] ?? ICONS.crying}
                </span>
                <div>
                  <p className="alert-title">{LABELS[a.label]?.text} זוהה</p>
                  <p className="alert-time">{a.time} · {a.confidence}%</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* FOOTER */}
      <div className="footer">
        <span>
          <span className={`conn-dot ${wsConnected ? "on" : "off"}`} style={{ marginLeft: 4 }} />
          {wsConnected ? "מחובר לשרת" : "מנסה להתחבר..."}
        </span>
        <span>v2.0</span>
      </div>
    </div>
  );
}
