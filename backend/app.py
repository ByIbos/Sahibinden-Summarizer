"""
Sahibinden.com Ilan Ozetleyici - Flask Backend
SSE (Server-Sent Events) ile canli guncelleme destegi
"""

from flask import Flask, request, jsonify, render_template_string, Response
from flask_cors import CORS
from bs4 import BeautifulSoup
import re
import json
import queue
import threading
import requests as http_requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ─── SSE: Canli stream icin kuyruk sistemi ───────────────────────────────────────

# Bagli web istemcilerinin kuyruk listesi
sse_clients = []
sse_lock = threading.Lock()

# Son 20 ozeti sakla (yeni baglananlar icin)
ozet_gecmisi = []
MAX_GECMIS = 20


def sse_bildir(ozet_data):
    """Tum bagli web istemcilerine yeni ozet bildir."""
    msg = f"data: {json.dumps(ozet_data, ensure_ascii=False)}\n\n"
    dead = []
    with sse_lock:
        for q in sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)

    # Gecmise ekle
    ozet_gecmisi.insert(0, ozet_data)
    if len(ozet_gecmisi) > MAX_GECMIS:
        ozet_gecmisi.pop()


# ─── Web Arayuzu ────────────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sahibinden Ozetleyici</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg: #08080e;
            --bg-surface: #0f0f1a;
            --bg-card: #141425;
            --bg-card-alt: #181832;
            --bg-hover: #1c1c3a;
            --bg-input: #111120;

            --border: rgba(255,255,255,0.05);
            --border-focus: rgba(120,80,255,0.4);

            --text-1: #f0f0f8;
            --text-2: #a0a0b8;
            --text-3: #606078;

            --accent: #7c5cff;
            --accent-2: #a07cff;
            --accent-bg: rgba(120,80,255,0.08);
            --accent-glow: rgba(120,80,255,0.15);

            --green: #3dd68c;
            --green-bg: rgba(61,214,140,0.08);
            --orange: #ff9f43;
            --red: #ff5c6c;
            --red-bg: rgba(255,92,108,0.06);
            --gold: #ffd369;

            --radius: 16px;
            --radius-sm: 10px;
            --radius-xs: 6px;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text-1);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* ── BG Orbs ──────────────────────────────────── */
        .bg-orbs { position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none; }
        .bg-orbs span { position: absolute; border-radius: 50%; filter: blur(100px); opacity: 0.5; animation: orbFloat 20s ease-in-out infinite; }
        .bg-orbs span:nth-child(1) { width: 600px; height: 600px; background: rgba(120,80,255,0.07); top: -10%; left: -5%; animation-duration: 22s; }
        .bg-orbs span:nth-child(2) { width: 500px; height: 500px; background: rgba(255,100,80,0.05); top: 30%; right: -10%; animation-duration: 18s; animation-delay: -5s; }
        .bg-orbs span:nth-child(3) { width: 400px; height: 400px; background: rgba(60,200,255,0.05); bottom: -5%; left: 30%; animation-duration: 25s; animation-delay: -10s; }
        @keyframes orbFloat {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(30px, -20px) scale(1.05); }
            50% { transform: translate(-20px, 30px) scale(0.95); }
            75% { transform: translate(15px, 15px) scale(1.02); }
        }

        /* ── Layout ──────────────────────────────────── */
        .shell { position: relative; z-index: 1; max-width: 760px; margin: 0 auto; padding: 40px 24px 60px; }

        /* ── Header ──────────────────────────────────── */
        .header { text-align: center; margin-bottom: 32px; }
        .header-icon {
            width: 56px; height: 56px;
            background: linear-gradient(135deg, var(--accent) 0%, #a06cff 100%);
            border-radius: 18px;
            display: inline-flex; align-items: center; justify-content: center;
            margin-bottom: 20px;
            box-shadow: 0 8px 30px var(--accent-glow);
        }
        .header-icon svg { color: #fff; }
        .header h1 {
            font-size: 28px; font-weight: 800;
            background: linear-gradient(135deg, #fff 0%, #b0b0c8 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        .header p { font-size: 14px; color: var(--text-3); line-height: 1.5; }

        /* ── Live Connection Bar ──────────────────────── */
        .live-bar {
            display: flex; align-items: center; justify-content: center; gap: 10px;
            padding: 10px 20px;
            background: var(--green-bg);
            border: 1px solid rgba(61,214,140,0.15);
            border-radius: var(--radius-sm);
            margin-bottom: 28px;
            font-size: 12px; font-weight: 600; color: var(--green);
            transition: all 0.3s;
        }
        .live-bar.disconnected {
            background: var(--red-bg);
            border-color: rgba(255,92,108,0.15);
            color: var(--red);
        }
        .live-bar.disconnected .live-dot { background: var(--red); animation: none; }
        .live-dot {
            width: 8px; height: 8px;
            background: var(--green);
            border-radius: 50%;
            animation: livePulse 2s ease-in-out infinite;
        }
        @keyframes livePulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(61,214,140,0.4); }
            50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(61,214,140,0); }
        }

        /* ── Empty State ─────────────────────────────── */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
        }
        .empty-icon {
            width: 80px; height: 80px;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 24px;
            display: inline-flex; align-items: center; justify-content: center;
            margin-bottom: 24px;
            color: var(--text-3);
        }
        .empty-title { font-size: 16px; font-weight: 600; color: var(--text-2); margin-bottom: 8px; }
        .empty-desc { font-size: 13px; color: var(--text-3); line-height: 1.6; max-width: 340px; margin: 0 auto; }

        .steps {
            margin-top: 28px;
            display: flex; flex-direction: column; gap: 12px;
            max-width: 360px; margin-left: auto; margin-right: auto;
        }
        .step {
            display: flex; align-items: center; gap: 14px;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 14px 18px;
            text-align: left;
        }
        .step-num {
            width: 28px; height: 28px; flex-shrink: 0;
            background: var(--accent-bg);
            color: var(--accent-2);
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 12px; font-weight: 800;
        }
        .step-text { font-size: 12px; color: var(--text-2); line-height: 1.4; }

        /* ── Feed Counter ─────────────────────────────── */
        .feed-header {
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 20px;
        }
        .feed-title {
            font-size: 14px; font-weight: 700; color: var(--text-2);
            display: flex; align-items: center; gap: 8px;
        }
        .feed-count {
            background: var(--accent-bg);
            color: var(--accent-2);
            font-size: 11px; font-weight: 700;
            padding: 3px 10px;
            border-radius: 100px;
        }
        .btn-clear {
            background: none; border: 1px solid var(--border);
            color: var(--text-3); font-family: inherit; font-size: 11px;
            padding: 6px 14px; border-radius: 6px;
            cursor: pointer; transition: all 0.2s;
        }
        .btn-clear:hover { color: var(--text-2); border-color: rgba(255,255,255,0.1); }

        /* ── Cards ────────────────────────────────────── */
        .feed { display: flex; flex-direction: column; gap: 16px; }

        .ilan-card {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
            transition: border-color 0.3s, transform 0.3s;
            animation: cardIn 0.5s cubic-bezier(0.16,1,0.3,1);
        }
        .ilan-card:hover { border-color: rgba(120,80,255,0.2); }
        .ilan-card.new-card { border-color: rgba(61,214,140,0.3); }

        @keyframes cardIn {
            from { opacity: 0; transform: translateY(20px) scale(0.98); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .card-accent { height: 3px; background: linear-gradient(90deg, var(--accent), var(--accent-2), var(--orange)); }

        .card-body { padding: 24px; }

        .card-top {
            display: flex; justify-content: space-between; align-items: flex-start;
            gap: 16px; margin-bottom: 16px;
        }
        .card-title {
            font-size: 16px; font-weight: 700; color: var(--text-1);
            line-height: 1.4; flex: 1;
        }
        .card-price {
            font-size: 20px; font-weight: 800; color: var(--gold);
            white-space: nowrap; letter-spacing: -0.5px;
        }

        .card-meta {
            display: flex; flex-wrap: wrap; gap: 12px;
            margin-bottom: 16px;
        }
        .meta-chip {
            display: inline-flex; align-items: center; gap: 5px;
            font-size: 11px; color: var(--text-3);
            background: rgba(255,255,255,0.03);
            padding: 4px 10px;
            border-radius: 6px;
        }
        .meta-chip svg { opacity: 0.5; }

        .card-props {
            display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
            margin-bottom: 16px;
        }
        @media (max-width: 500px) { .card-props { grid-template-columns: 1fr; } }
        .cprop {
            display: flex; justify-content: space-between; align-items: baseline;
            padding: 6px 10px;
            background: rgba(255,255,255,0.02);
            border-radius: 4px; font-size: 11px;
        }
        .cprop-k { color: var(--text-3); }
        .cprop-v { color: var(--text-1); font-weight: 600; }

        .card-desc {
            font-size: 12px; line-height: 1.6; color: var(--text-3);
            max-height: 48px; overflow: hidden; position: relative;
            transition: max-height 0.4s ease;
        }
        .card-desc.exp { max-height: 600px; }
        .card-desc:not(.exp)::after {
            content: ''; position: absolute; bottom: 0; left: 0; right: 0;
            height: 28px; background: linear-gradient(transparent, var(--bg-surface));
        }

        .card-actions {
            display: flex; gap: 8px;
            margin-top: 16px; padding-top: 16px;
            border-top: 1px solid var(--border);
        }
        .card-btn {
            display: flex; align-items: center; justify-content: center; gap: 6px;
            padding: 8px 14px;
            background: var(--bg-card);
            color: var(--text-2);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-family: inherit; font-size: 11px; font-weight: 500;
            cursor: pointer; transition: all 0.2s;
            text-decoration: none;
        }
        .card-btn:hover { background: var(--bg-hover); color: var(--text-1); border-color: rgba(255,255,255,0.1); }
        .card-btn.primary {
            background: linear-gradient(135deg, var(--accent), #6040e0);
            color: #fff; border-color: transparent;
        }
        .card-time {
            margin-left: auto;
            font-size: 10px; color: var(--text-3);
            display: flex; align-items: center; gap: 4px;
        }

        /* ── Notification Toast ───────────────────────── */
        .toast {
            position: fixed; top: 20px; right: 20px;
            background: var(--bg-card); border: 1px solid rgba(61,214,140,0.3);
            border-radius: var(--radius-sm);
            padding: 14px 20px;
            display: flex; align-items: center; gap: 10px;
            font-size: 13px; color: var(--green); font-weight: 500;
            z-index: 1000;
            transform: translateX(120%);
            transition: transform 0.4s cubic-bezier(0.16,1,0.3,1);
            box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        }
        .toast.show { transform: translateX(0); }
        .toast-dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; }

        /* ── Footer ──────────────────────────────────── */
        .footer { text-align: center; margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--border); }
        .footer p { font-size: 11px; color: var(--text-3); }
        .footer .ver { display: inline-block; background: var(--accent-bg); color: var(--accent-2); padding: 3px 10px; border-radius: 100px; font-size: 10px; font-weight: 700; margin-left: 8px; }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(120,80,255,0.2); border-radius: 10px; }
    </style>
</head>
<body>
    <div class="bg-orbs"><span></span><span></span><span></span></div>

    <!-- Notification Toast -->
    <div class="toast" id="toast">
        <div class="toast-dot"></div>
        <span id="toastText">Yeni ilan ozeti geldi!</span>
    </div>

    <div class="shell">
        <!-- Header -->
        <div class="header">
            <div class="header-icon">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
            </div>
            <h1>Sahibinden Ozetleyici</h1>
            <p>Uzantidan gelen ilan ozetleri burada canli olarak goruntulenir.</p>
        </div>

        <!-- Live Connection -->
        <div class="live-bar" id="liveBar">
            <div class="live-dot"></div>
            <span id="liveText">Canli baglanti kuruluyor...</span>
        </div>

        <!-- Empty State -->
        <div id="emptyState" class="empty-state">
            <div class="empty-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2"/>
                    <line x1="8" y1="21" x2="16" y2="21"/>
                    <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
            </div>
            <p class="empty-title">Henuz ilan ozeti yok</p>
            <p class="empty-desc">Chrome uzantisi sahibinden.com ilanlarini otomatik ozetler ve buraya gonderir.</p>

            <div class="steps">
                <div class="step">
                    <div class="step-num">1</div>
                    <div class="step-text">Chrome'da uzantiyi yukleyin (extension/ klasoru)</div>
                </div>
                <div class="step">
                    <div class="step-num">2</div>
                    <div class="step-text">Sahibinden.com'da bir ilan sayfasina gidin</div>
                </div>
                <div class="step">
                    <div class="step-num">3</div>
                    <div class="step-text">Ozet otomatik olarak burada gorunecek</div>
                </div>
            </div>
        </div>

        <!-- Feed -->
        <div id="feedSection" style="display:none">
            <div class="feed-header">
                <div class="feed-title">
                    Ilan Ozetleri
                    <span class="feed-count" id="feedCount">0</span>
                </div>
                <button class="btn-clear" onclick="clearFeed()">Temizle</button>
            </div>
            <div class="feed" id="feed"></div>
        </div>

        <div class="footer">
            <p>Sahibinden Ozetleyici API<span class="ver">v1.0.0</span></p>
        </div>
    </div>

    <script>
        let allData = [];
        let eventSource = null;

        // ── SSE Baglantisi ─────────────────────────────
        function connectSSE() {
            eventSource = new EventSource('/stream');

            eventSource.onopen = function() {
                document.getElementById('liveBar').classList.remove('disconnected');
                document.getElementById('liveText').textContent = 'Canli baglanti aktif - uzantidan veri bekleniyor';
            };

            eventSource.onmessage = function(e) {
                try {
                    const data = JSON.parse(e.data);
                    // Baglanti mesajlarini ve bos verileri atla
                    if (data.type === 'connected' || !data.baslik) return;
                    addCard(data, true);
                } catch(err) {
                    // JSON olmayan mesajlari (heartbeat) atla
                }
            };

            eventSource.onerror = function() {
                document.getElementById('liveBar').classList.add('disconnected');
                document.getElementById('liveText').textContent = 'Baglanti kesildi - yeniden deneniyor...';
                eventSource.close();
                setTimeout(connectSSE, 3000);
            };
        }

        // ── Kart Olustur ───────────────────────────────
        function addCard(data, isNew) {
            // Ayni ilan zaten var mi?
            const exists = allData.find(d => d.ilan_no && d.ilan_no === data.ilan_no);
            if (exists) return;

            allData.unshift(data);

            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('feedSection').style.display = 'block';
            document.getElementById('feedCount').textContent = allData.length;

            const feed = document.getElementById('feed');
            const card = document.createElement('div');
            card.className = 'ilan-card' + (isNew ? ' new-card' : '');
            if (isNew) setTimeout(() => card.classList.remove('new-card'), 3000);

            const idx = allData.length - 1;
            const ozellikler = data.ozellikler || {};
            const keys = Object.keys(ozellikler);

            let propsHtml = '';
            if (keys.length > 0) {
                propsHtml = '<div class="card-props">';
                keys.slice(0, 8).forEach(k => {
                    propsHtml += '<div class="cprop"><span class="cprop-k">' + esc(k) + '</span><span class="cprop-v">' + esc(ozellikler[k]) + '</span></div>';
                });
                if (keys.length > 8) propsHtml += '<div class="cprop"><span class="cprop-k">...</span><span class="cprop-v">+' + (keys.length - 8) + ' daha</span></div>';
                propsHtml += '</div>';
            }

            const zaman = data.ozetleme_zamani ? new Date(data.ozetleme_zamani).toLocaleTimeString('tr-TR') : '';

            card.innerHTML = `
                <div class="card-accent"></div>
                <div class="card-body">
                    <div class="card-top">
                        <div class="card-title">${esc(data.baslik || 'Baslik yok')}</div>
                        ${data.fiyat ? '<div class="card-price">' + esc(data.fiyat) + '</div>' : ''}
                    </div>
                    <div class="card-meta">
                        ${data.ilan_no ? '<span class="meta-chip"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>' + esc(data.ilan_no) + '</span>' : ''}
                        ${data.konum ? '<span class="meta-chip"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/></svg>' + esc(data.konum) + '</span>' : ''}
                        ${data.tarih ? '<span class="meta-chip"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/></svg>' + esc(data.tarih) + '</span>' : ''}
                    </div>
                    ${propsHtml}
                    ${data.aciklama ? '<div class="card-desc" onclick="this.classList.toggle(\'exp\')">' + esc(data.aciklama) + '</div>' : ''}
                    <div class="card-actions">
                        <button class="card-btn primary" onclick="dlJson(${allData.length - 1})">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                            JSON
                        </button>
                        <button class="card-btn" onclick="cpJson(${allData.length - 1})">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            Kopyala
                        </button>
                        ${data.url ? '<a class="card-btn" href="' + esc(data.url) + '" target="_blank"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Ilana Git</a>' : ''}
                        <span class="card-time">${zaman}</span>
                    </div>
                </div>
            `;

            feed.insertBefore(card, feed.firstChild);

            // Toast
            if (isNew) showToast(data.baslik ? data.baslik.substring(0, 50) + '...' : 'Yeni ilan ozeti geldi!');
        }

        // ── Toast ──────────────────────────────────────
        function showToast(text) {
            const t = document.getElementById('toast');
            document.getElementById('toastText').textContent = text;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 4000);
        }

        // ── JSON Indir ─────────────────────────────────
        function dlJson(idx) {
            const d = allData[idx];
            if (!d) return;
            const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = d.ilan_no ? 'sahibinden_' + d.ilan_no + '.json' : 'sahibinden_ozet.json';
            a.click(); URL.revokeObjectURL(a.href);
        }

        // ── JSON Kopyala ───────────────────────────────
        async function cpJson(idx) {
            const d = allData[idx];
            if (!d) return;
            try {
                await navigator.clipboard.writeText(JSON.stringify(d, null, 2));
                showToast('JSON panoya kopyalandi!');
            } catch(e) { showToast('Kopyalanamadi'); }
        }

        // ── Temizle ────────────────────────────────────
        function clearFeed() {
            allData = [];
            document.getElementById('feed').innerHTML = '';
            document.getElementById('feedCount').textContent = '0';
            document.getElementById('feedSection').style.display = 'none';
            document.getElementById('emptyState').style.display = 'block';
        }

        // ── Escape ─────────────────────────────────────
        function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

        // ── Gecmisi Yukle ──────────────────────────────
        async function loadHistory() {
            try {
                const resp = await fetch('/gecmis');
                const data = await resp.json();
                if (data.length > 0) {
                    data.reverse().forEach(d => { if (d.baslik) addCard(d, false); });
                }
            } catch(e) { console.log('Gecmis yuklenemedi'); }
        }

        // ── Baslat ─────────────────────────────────────
        loadHistory();
        connectSSE();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Web arayuzu ana sayfasi."""
    return render_template_string(DASHBOARD_HTML)


@app.route("/health")
def health():
    """Saglik kontrolu."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/gecmis")
def gecmis():
    """Son ozetlenen ilanlarin gecmisini dondurur."""
    return jsonify(ozet_gecmisi)


@app.route("/stream")
def stream():
    """SSE endpoint - canli ozet akisi."""
    def event_stream():
        q = queue.Queue(maxsize=50)
        with sse_lock:
            sse_clients.append(q)
        try:
            # Heartbeat: baglanti acik kalmasi icin
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    # Heartbeat
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            with sse_lock:
                if q in sse_clients:
                    sse_clients.remove(q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


# ─── Yardimci Fonksiyonlar ───────────────────────────────────────────────────────

def temizle(text: str) -> str:
    """Gereksiz bosluklari ve satir sonlarini temizle."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def parse_ilan(html: str, url: str = "") -> dict:
    """
    Sahibinden.com ilan sayfasinin HTML'ini parse edip ozet dict dondurur.
    """
    soup = BeautifulSoup(html, "html.parser")

    # ── Baslik
    baslik = ""
    baslik_div = soup.find("div", class_="classifiedDetailTitle")
    if baslik_div:
        h1 = baslik_div.find("h1")
        if h1:
            baslik = temizle(h1.get_text())
    if not baslik:
        h1 = soup.find("h1")
        if h1:
            baslik = temizle(h1.get_text())

    # ── Fiyat
    fiyat = ""
    fiyat_div = soup.find("div", class_="classifiedInfo")
    if fiyat_div:
        fiyat_el = fiyat_div.find("h3")
        if fiyat_el:
            fiyat = temizle(fiyat_el.get_text())
    if not fiyat:
        for el in soup.find_all("span", class_=re.compile(r"price", re.I)):
            t = temizle(el.get_text())
            if t:
                fiyat = t
                break

    # ── Ilan No
    ilan_no = ""
    breadcrumb = soup.find("div", class_="classifiedInfo")
    if breadcrumb:
        spans = breadcrumb.find_all("span")
        for sp in spans:
            t = temizle(sp.get_text())
            if re.match(r"^\d{5,}$", t):
                ilan_no = t
                break
    if not ilan_no:
        info_list = soup.find("ul", class_="classifiedInfoList")
        if info_list:
            for li in info_list.find_all("li"):
                label = li.find("strong")
                if label and "No" in label.get_text():
                    value = li.find("span")
                    if value:
                        ilan_no = temizle(value.get_text())

    # ── Ozellikler
    ozellikler = {}
    info_list = soup.find("ul", class_="classifiedInfoList")
    if info_list:
        for li in info_list.find_all("li"):
            strong = li.find("strong")
            span = li.find("span")
            if strong and span:
                key = temizle(strong.get_text())
                val = temizle(span.get_text())
                if key and val:
                    ozellikler[key] = val

    prop_table = soup.find("div", class_="classifiedProperties")
    if prop_table:
        rows = prop_table.find_all("li")
        for row in rows:
            spans = row.find_all("span")
            if len(spans) >= 2:
                key = temizle(spans[0].get_text())
                val = temizle(spans[1].get_text())
                if key and val:
                    ozellikler[key] = val

    # ── Aciklama
    aciklama = ""
    desc_div = soup.find("div", id="classified-detail")
    if desc_div:
        inner = desc_div.find("div")
        target = inner if inner else desc_div
        aciklama = temizle(target.get_text())
    if not aciklama:
        desc_div = soup.find("div", class_="classifiedDescription")
        if desc_div:
            aciklama = temizle(desc_div.get_text())

    # ── Konum
    konum = ""
    loc_div = soup.find("div", class_="classifiedInfo")
    if loc_div:
        loc_h2 = loc_div.find("h2")
        if loc_h2:
            konum = temizle(loc_h2.get_text())
    if not konum:
        loc_div = soup.find("div", class_="classifiedLocation")
        if loc_div:
            konum = temizle(loc_div.get_text())

    # ── Tarih
    tarih = ""
    date_spans = soup.find_all("span", class_=re.compile(r"date", re.I))
    for ds in date_spans:
        t = temizle(ds.get_text())
        if t:
            tarih = t
            break

    # ── Gorseller
    gorseller = []
    gallery = soup.find("div", class_="classifiedDetailPhotos")
    if gallery:
        for img in gallery.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if src and "placeholder" not in src:
                gorseller.append(src)

    return {
        "baslik": baslik,
        "fiyat": fiyat,
        "ilan_no": ilan_no,
        "konum": konum,
        "tarih": tarih,
        "ozellikler": ozellikler,
        "aciklama": aciklama[:2000] if aciklama else "",
        "gorsel_sayisi": len(gorseller),
        "gorseller": gorseller[:5],
        "url": url,
        "ozetleme_zamani": datetime.now().isoformat(),
    }


# ─── API Endpoint'leri ───────────────────────────────────────────────────────────

@app.route("/ozetle", methods=["POST"])
def ozetle():
    """Ilan HTML'ini alip ozetlenmis JSON dondurur + SSE ile web'e push eder."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Gecersiz JSON verisi"}), 400

    html = data.get("html", "")
    url = data.get("url", "")

    if not html:
        return jsonify({"error": "HTML icerigi bos"}), 400

    try:
        ozet = parse_ilan(html, url)
    except Exception as e:
        return jsonify({"error": f"Parse hatasi: {str(e)}"}), 500

    # SSE ile web arayuzune bildir
    sse_bildir(ozet)

    return jsonify(ozet)


@app.route("/ozetle-url", methods=["POST"])
def ozetle_url():
    """Ilan URL'sini alir, sayfayi indirir, parse edip ozet dondurur + SSE push."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Gecersiz JSON verisi"}), 400

    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL bos"}), 400

    if "sahibinden.com" not in url:
        return jsonify({"error": "Gecerli bir sahibinden.com linki girin"}), 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        resp = http_requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except http_requests.exceptions.Timeout:
        return jsonify({"error": "Sayfa yuklenirken zaman asimi."}), 504
    except http_requests.exceptions.RequestException as e:
        return jsonify({"error": f"Sayfa indirilemedi: {str(e)}"}), 502

    try:
        ozet = parse_ilan(html, url)
    except Exception as e:
        return jsonify({"error": f"Parse hatasi: {str(e)}"}), 500

    # SSE ile web arayuzune bildir
    sse_bildir(ozet)

    return jsonify(ozet)


# ─── Giris Noktasi ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  *  Sahibinden Ozetleyici API baslatiliyor...")
    print("  *  http://localhost:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
