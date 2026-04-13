# Sahibinden Özetleyici 🚀

Sahibinden.com üzerindeki emlak ve vasıta ilanlarını saniyeler içinde analiz eden ve yapılandırılmış bir özet sunan akıllı bir sistemdir. Bir Chrome uzantısı ve Flask tabanlı bir backend'den oluşur.

## ✨ Özellikler

- **Otomatik Algılama:** Bir ilan sayfasına girdiğinizde uzantı bunu otomatik olarak algılar ve arkaplanda özetleme işlemini başlatır.
- **Canlı Dashboard:** `localhost:5000` adresindeki modern web arayüzü, uzantının bulduğu ilanları anlık (SSE ile) canlı olarak listeler.
- **Detaylı Analiz:** Başlık, fiyat, ilan numarası, konum ve tüm teknik özellikleri (m2, oda sayısı, yakıt tipi vb.) tablo halinde çıkarır.
- **JSON Desteği:** Özetlenen verileri tek tıkla JSON formatında indirebilir veya panoya kopyalayabilirsiniz.
- **Modern Arayüz:** Premium karanlık tema (Glassmorphism) ve akıcı animasyonlar.

## 🛠️ Kurulum

### 1. Backend (Python)
Gerekli kütüphaneleri yükleyin ve sunucuyu başlatın:
```bash
pip install -r requirements.txt
python backend/app.py
```
Sunucu varsayılan olarak `http://localhost:5000` adresinde çalışacaktır.

### 2. Chrome Uzantısı
- Chrome'da `chrome://extensions/` adresine gidin.
- Sağ üstteki **Geliştirici Modu**'nu aktif edin.
- **Paketlenmemiş öğe yükle** butonuna tıklayın ve projedeki `extension` klasörünü seçin.

## 🚀 Kullanım
1. `localhost:5000` adresini tarayıcınızda açın (Dashboard).
2. Sahibinden.com'da rastgele bir ilan sayfasına gidin.
3. Uzantı simgesindeki yeşil tik (**✓**) yandığında özet hazır demektir.
4. İster uzantı popup'ından ister web dashboard'undan özeti inceleyebilirsiniz.

## 📦 Proje Yapısı
- `backend/`: Flask API servisi ve BeautifulSoup parser mantığı.
- `extension/`: Otomatik veri toplama yapan Manifest V3 Chrome uzantısı.

## 📜 License
MIT License — use it anywhere.

Built with ❤️ by [ByIbos](https://github.com/ByIbos)
