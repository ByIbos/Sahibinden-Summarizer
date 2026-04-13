/**
 * Sahibinden Ozetleyici — Popup Script
 *
 * Popup acildiginda:
 * 1. Aktif sekmeyi kontrol eder
 * 2. sahibinden.com degilse bilgi gosterir
 * 3. sahibinden.com ise cache'ten ozeti okur (background zaten cekti)
 * 4. Henuz hazir degilse loading gosterir ve bekler
 */

const API_URL = "http://localhost:5000/ozetle";

// ─── DOM Elements ───────────────────────────────────────────────────────────────

const tagline = document.getElementById("tagline");
const statusBar = document.getElementById("statusBar");
const statusText = document.getElementById("statusText");
const notSahibinden = document.getElementById("notSahibinden");
const loadingEl = document.getElementById("loading");
const loadingText = document.getElementById("loadingText");
const errorBox = document.getElementById("errorBox");
const errorText = document.getElementById("errorText");
const btnRetry = document.getElementById("btnRetry");
const resultsEl = document.getElementById("results");
const btnDownload = document.getElementById("btnDownload");
const btnCopy = document.getElementById("btnCopy");
const btnToggleDesc = document.getElementById("btnToggleDesc");

const resBaslik = document.getElementById("resBaslik");
const resFiyat = document.getElementById("resFiyat");
const resIlanNo = document.getElementById("resIlanNo");
const resKonum = document.getElementById("resKonum");
const resOzellikler = document.getElementById("resOzellikler");
const resAciklama = document.getElementById("resAciklama");
const propCount = document.getElementById("propCount");

let lastOzet = null;
let currentTabId = null;
let currentTabUrl = null;

// ─── Yardimci ───────────────────────────────────────────────────────────────────

function setStatus(type, text) {
  statusBar.className = "status-bar " + type;
  statusText.textContent = text;
}

function showError(msg) {
  errorText.textContent = msg;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.classList.add("hidden");
}

function isSahibindenIlan(url) {
  return url && /sahibinden\.com\/ilan\//.test(url);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ─── Sonuclari Goster ───────────────────────────────────────────────────────────

function displayResults(data) {
  lastOzet = data;

  // Baslik
  resBaslik.textContent = data.baslik || "Baslik bulunamadi";

  // Fiyat
  resFiyat.textContent = data.fiyat || "—";

  // Ilan No
  resIlanNo.textContent = data.ilan_no || "—";

  // Konum
  const cardKonum = document.getElementById("cardKonum");
  if (data.konum) {
    resKonum.textContent = data.konum;
    cardKonum.classList.remove("hidden");
  } else {
    cardKonum.classList.add("hidden");
  }

  // Ozellikler
  resOzellikler.innerHTML = "";
  const ozellikler = data.ozellikler || {};
  const keys = Object.keys(ozellikler);

  if (keys.length > 0) {
    propCount.textContent = keys.length;
    keys.forEach((key) => {
      const item = document.createElement("div");
      item.className = "prop-item";
      item.innerHTML = `
        <span class="prop-key">${escapeHtml(key)}</span>
        <span class="prop-value">${escapeHtml(ozellikler[key])}</span>
      `;
      resOzellikler.appendChild(item);
    });
    document.getElementById("cardOzellikler").classList.remove("hidden");
  } else {
    document.getElementById("cardOzellikler").classList.add("hidden");
  }

  // Aciklama
  if (data.aciklama) {
    resAciklama.textContent = data.aciklama;
    document.getElementById("cardAciklama").classList.remove("hidden");
  } else {
    document.getElementById("cardAciklama").classList.add("hidden");
  }

  // Goster
  loadingEl.classList.add("hidden");
  notSahibinden.classList.add("hidden");
  resultsEl.classList.remove("hidden");
  tagline.textContent = "Ozet hazir";
  setStatus("", "Ozet hazir");
}

// ─── Ana Akis: Popup Acildiginda ────────────────────────────────────────────────

async function init() {
  // Aktif sekmeyi al
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab) {
    setStatus("error", "Sekme bulunamadi");
    return;
  }

  currentTabId = tab.id;
  currentTabUrl = tab.url;

  // Sahibinden degil mi?
  if (!isSahibindenIlan(tab.url)) {
    tagline.textContent = "Sahibinden.com bekleniyor";
    setStatus("", "Hazir");
    notSahibinden.classList.remove("hidden");
    loadingEl.classList.add("hidden");
    return;
  }

  // Sahibinden ilan sayfasi — cache kontrol et
  tagline.textContent = "Ozet kontrol ediliyor...";
  setStatus("loading", "Ozet kontrol ediliyor...");
  loadingEl.classList.remove("hidden");

  await checkAndDisplay(tab.id, tab.url);
}

async function checkAndDisplay(tabId, url) {
  const storageKey = "ozet_" + tabId;
  const statusKey = "status_" + tabId;

  const stored = await chrome.storage.local.get([storageKey, statusKey]);
  const ozet = stored[storageKey];
  const status = stored[statusKey];

  // Ozet hazir mi?
  if (ozet && ozet.url === url) {
    displayResults(ozet);
    return;
  }

  // Status kontrol
  if (status && status.state === "error") {
    loadingEl.classList.add("hidden");
    setStatus("error", "Hata olustu");
    showError(status.error || "Bilinmeyen hata");
    tagline.textContent = "Hata olustu";
    return;
  }

  if (status && status.state === "loading") {
    // Henuz yukleniyor, bekle ve tekrar dene
    loadingText.textContent = "Ilan ozetleniyor...";
    tagline.textContent = "Ozetleniyor...";
    setStatus("loading", "Arka planda ozetleniyor...");
    loadingEl.classList.remove("hidden");

    // Poll: her 500ms'de kontrol et
    setTimeout(() => checkAndDisplay(tabId, url), 500);
    return;
  }

  // Hic status yok — background henuz baslatmamis olabilir, biz manuel tetikleyelim
  loadingText.textContent = "Ilan ozetleniyor...";
  tagline.textContent = "Ozetleniyor...";
  setStatus("loading", "Ozetleniyor...");
  loadingEl.classList.remove("hidden");

  // Background'a mesaj gonder
  chrome.runtime.sendMessage({ action: "retry", tabId, url });

  // Poll
  setTimeout(() => checkAndDisplay(tabId, url), 800);
}

// ─── Tekrar Dene ────────────────────────────────────────────────────────────────

btnRetry.addEventListener("click", async () => {
  if (!currentTabId || !currentTabUrl) return;

  hideError();
  loadingEl.classList.remove("hidden");
  loadingText.textContent = "Tekrar deneniyor...";
  setStatus("loading", "Tekrar deneniyor...");
  tagline.textContent = "Tekrar deneniyor...";

  // Eski cache'i temizle
  await chrome.storage.local.remove([
    "ozet_" + currentTabId,
    "status_" + currentTabId,
  ]);

  // Background'a tekrar dene mesaji gonder
  chrome.runtime.sendMessage({
    action: "retry",
    tabId: currentTabId,
    url: currentTabUrl,
  });

  // Poll
  setTimeout(() => checkAndDisplay(currentTabId, currentTabUrl), 800);
});

// ─── JSON Indir ─────────────────────────────────────────────────────────────────

btnDownload.addEventListener("click", () => {
  if (!lastOzet) return;

  const blob = new Blob([JSON.stringify(lastOzet, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = lastOzet.ilan_no
    ? `sahibinden_${lastOzet.ilan_no}.json`
    : `sahibinden_ozet_${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

// ─── Panoya Kopyala ─────────────────────────────────────────────────────────────

btnCopy.addEventListener("click", async () => {
  if (!lastOzet) return;

  try {
    await navigator.clipboard.writeText(JSON.stringify(lastOzet, null, 2));

    const btnSpan = btnCopy.querySelector("span");
    const originalText = btnSpan.textContent;
    btnSpan.textContent = "Kopyalandi!";
    btnCopy.style.borderColor = "rgba(61, 214, 140, 0.4)";
    btnCopy.style.color = "#3dd68c";

    setTimeout(() => {
      btnSpan.textContent = originalText;
      btnCopy.style.borderColor = "";
      btnCopy.style.color = "";
    }, 2000);
  } catch (err) {
    showError("Panoya kopyalanamadi.");
  }
});

// ─── Aciklama Toggle ────────────────────────────────────────────────────────────

btnToggleDesc.addEventListener("click", () => {
  resAciklama.classList.toggle("collapsed");
  btnToggleDesc.classList.toggle("active");
});

// ─── Storage degisikliklerini dinle (canli guncelleme) ───────────────────────────

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !currentTabId) return;

  const ozetKey = "ozet_" + currentTabId;
  const statusKey = "status_" + currentTabId;

  if (changes[ozetKey] && changes[ozetKey].newValue) {
    const ozet = changes[ozetKey].newValue;
    if (ozet.url === currentTabUrl) {
      displayResults(ozet);
    }
  }

  if (changes[statusKey] && changes[statusKey].newValue) {
    const status = changes[statusKey].newValue;
    if (status.state === "error") {
      loadingEl.classList.add("hidden");
      setStatus("error", "Hata olustu");
      showError(status.error || "Bilinmeyen hata");
      tagline.textContent = "Hata olustu";
    }
  }
});

// ─── Baslat ─────────────────────────────────────────────────────────────────────

init();
