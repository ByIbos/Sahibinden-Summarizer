/**
 * Sahibinden Ozetleyici — Background Service Worker
 *
 * Sahibinden.com ilan sayfasina girildiginde otomatik olarak:
 * 1. Content script inject eder
 * 2. HTML'i Flask backend'e gonderir
 * 3. Ozeti chrome.storage'a kaydeder
 * 4. Badge ile kullaniciya bildirir
 *
 * Popup acildiginda sonuc hazir bekliyor olur.
 */

const API_URL = "http://localhost:5000/ozetle";

// Sahibinden ilan URL'si mi kontrol et
function isSahibindenIlan(url) {
  if (!url) return false;
  return /sahibinden\.com\/ilan\//.test(url);
}

// Tab URL degistiginde kontrol et
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Sadece sayfa yuklendiginde (complete)
  if (changeInfo.status !== "complete") return;
  if (!tab.url || !isSahibindenIlan(tab.url)) {
    // Sahibinden degil, badge temizle
    chrome.action.setBadgeText({ text: "", tabId });
    return;
  }

  // Zaten bu URL icin ozet var mi?
  const stored = await chrome.storage.local.get(["ozet_" + tabId]);
  const existing = stored["ozet_" + tabId];
  if (existing && existing.url === tab.url) {
    // Ayni URL, zaten ozetlenmis
    chrome.action.setBadgeText({ text: "✓", tabId });
    chrome.action.setBadgeBackgroundColor({ color: "#3dd68c", tabId });
    return;
  }

  // Yeni ilan — otomatik ozetle
  await ozetleTab(tabId, tab.url);
});

// Sekme kapaninca storage temizle
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.remove(["ozet_" + tabId, "status_" + tabId]);
});

// Ana ozetleme fonksiyonu
async function ozetleTab(tabId, url) {
  try {
    // Badge: yukleniyor
    chrome.action.setBadgeText({ text: "...", tabId });
    chrome.action.setBadgeBackgroundColor({ color: "#7c5cff", tabId });

    // Status kaydet (popup icin)
    await chrome.storage.local.set({
      ["status_" + tabId]: { state: "loading", url }
    });

    // Content script inject et
    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId },
        files: ["content.js"],
      });
    } catch (e) {
      throw new Error("Sayfa verisi alinamadi: " + e.message);
    }

    if (!results || !results[0] || !results[0].result) {
      throw new Error("Sayfa verisi bos dondu.");
    }

    const pageData = results[0].result;

    // Flask'a POST
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        html: pageData.html,
        url: pageData.url || url,
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || "Sunucu hatasi: " + response.status);
    }

    const ozet = await response.json();

    if (ozet.error) {
      throw new Error(ozet.error);
    }

    // Basarili — kaydet
    await chrome.storage.local.set({
      ["ozet_" + tabId]: { ...ozet, url },
      ["status_" + tabId]: { state: "done", url }
    });

    // Badge: hazir
    chrome.action.setBadgeText({ text: "✓", tabId });
    chrome.action.setBadgeBackgroundColor({ color: "#3dd68c", tabId });

  } catch (err) {
    console.error("[Sahibinden Ozetleyici] Hata:", err);

    await chrome.storage.local.set({
      ["status_" + tabId]: { state: "error", url, error: err.message }
    });

    // Badge: hata
    chrome.action.setBadgeText({ text: "!", tabId });
    chrome.action.setBadgeBackgroundColor({ color: "#ff5c6c", tabId });
  }
}

// Popup'tan veya diger yerlerden tetikleme icin message listener
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "retry") {
    ozetleTab(msg.tabId, msg.url).then(() => sendResponse({ ok: true }));
    return true; // async response
  }
});
