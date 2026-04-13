/**
 * Sahibinden Özetleyici — Content Script
 * 
 * Sayfadaki ilan verilerini toplar ve popup.js'ye geri döndürür.
 * Bu script chrome.scripting.executeScript ile inject edilir.
 */

(function () {
  "use strict";

  try {
    // Sayfanın tüm HTML'ini al
    const html = document.documentElement.outerHTML;

    // Sayfa URL'sini al
    const url = window.location.href;

    // Sonuç olarak döndür
    return {
      html: html,
      url: url,
      timestamp: new Date().toISOString(),
    };
  } catch (err) {
    return {
      html: "",
      url: window.location.href,
      error: err.message,
      timestamp: new Date().toISOString(),
    };
  }
})();
