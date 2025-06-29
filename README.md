# Sprint Analyzer & Planning Dashboard

Sprint Analyzer, Trello board'larınızdan takım performansını analiz eden ve akıllı kapasite önerileri sunan bir web uygulamasıdır. Geçmiş sprint verilerinizi analiz ederek gelecek sprintler için optimal task dağılımı ve kapasite planlaması yapmanızı sağlar.

## 🎯 Özellikler

### 📊 Sprint Analizi
- **Trello Integration** - OAuth ile güvenli bağlantı
- **Performance Analytics** - Son 3 sprintin detaylı analizi
- **Capacity Calculation** - 21 SP hedefi ile akıllı kapasite hesaplama
- **Team Statistics** - Sprinter bazlı tamamlama oranları ve ortalamalar

### 🎮 Sprint Planning Dashboard
- **Interactive Task Management** - Drag & drop ile task atama
- **Real-time Capacity Tracking** - Anlık doluluk oranları
- **Priority Management** - High/Medium/Low öncelik sistemi
- **Auto Assignment** - Akıllı task dağıtım algoritması

### 🚀 Exception Management
- **Customer Delegate** - Minimum SP ataması (default: 2 SP)
- **Vacation Days** - Gün bazlı kapasite azaltımı
- **On-call Duties** - Nöbetçi için sabit SP azaltımı (default: -3 SP)

### 📈 Export & Reporting
- **JSON Export** - Detaylı sprint verileri
- **CSV Export** - Excel uyumlu task listesi ve kapasite raporu
- **PNG Export** - Görsel sprint planı

## 🛠️ Kurulum

### Gereksinimler
```bash
Python 3.8+
Flask
requests-oauthlib
```

### Adımlar
1. **Repository'yi klonlayın**
```bash
git clone <repository-url>
cd sprint-analyzer
```

2. **Virtual environment oluşturun**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

3. **Bağımlılıkları yükleyin**
```bash
pip install Flask requests requests-oauthlib
```

4. **Uygulamayı başlatın**
```bash
python app.py
```

5. **Browser'da açın**
```
http://localhost:8080
```

## 🔧 Trello Kurulumu

### 1. Trello API Credentials
1. [Trello Developer Page](https://trello.com/app-key) adresine gidin
2. **API Key**'inizi kopyalayın
3. **"Show OAuth Secret"** butonuna tıklayıp **OAuth Secret**'ı alın

### 2. Board Hazırlığı
Trello board'unuzda şu custom field'ları oluşturun:

- **SprintNo** (Number) - Sprint numarası için
- **StoryPoint** (Number) - Story point değeri için  
- **Sprinter** (Dropdown) - Takım üyesi seçimi için

### 3. Board ID Bulma
Board URL'nizden ID'yi alın:
```
https://trello.com/b/BOARD_ID/board-name
                    ^^^^^^^^
```

## 📋 Kullanım Rehberi

### 1. Setup & Authentication
1. Ana sayfadan Trello API bilgilerinizi girin
2. OAuth authentication yapın
3. Board ID'nizi girin ve bağlantıyı test edin

### 2. Sprint Analysis
1. **ArchiveNew** listesini seçin (tamamlanmış tasklar)
2. Mevcut sprint numarasını girin
3. **"Performans Analizini Başlat"** butonuna tıklayın

### 3. Exception Management
1. Exception sprint numarasını belirleyin
2. Sprinter'ları yükleyin
3. Exception'ları işaretleyin:
   - ☑️ Müşteri Dedikesi
   - ☑️ Nöbetçi  
   - 📅 İzin günü sayısı
4. Exception'ları kaydedin

### 4. Capacity Planning
1. Mevcut sprint toplam SP'sini girin
2. **"Kapasite Önerisi Al"** butonuna tıklayın
3. **"Sprint Planning Dashboard"** butonuna tıklayın

### 5. Dashboard Kullanımı
1. **Task Ekleme** - Sol sidebar'dan yeni task oluşturun
2. **Drag & Drop** - Taskları sprinter'lara sürükleyin
3. **Capacity Monitoring** - Anlık doluluk oranlarını takip edin
4. **Export** - Sprint planını istediğiniz formatta dışa aktarın

## 🔍 Algoritma Detayları

### Kapasite Hesaplama
```
1. Geçmiş sprint totalleri hesaplanır
2. Her sprinter'ın aldığı pay oranı bulunur
3. Hedef (21 SP) ile mevcut kapasite karşılaştırılır
4. Exception'lar uygulanır:
   - Müşteri Dedikesi: Min 2 SP
   - İzin: Gün başına %20 azaltım  
   - Nöbetçi: -3 SP sabit azaltım
```

### Auto Assignment
```
1. Tasklar öncelik sırasına göre sıralanır (High → Medium → Low)
2. Her task için en düşük yüklü sprinter bulunur
3. Sprinter kapasitesi aşılmayacak şekilde atama yapılır
```

## 📁 Dosya Yapısı

```
sprint-analyzer/
├── app.py                      # Ana Flask uygulaması
├── token_storage.py            # OAuth token yönetimi
├── sprinter_exceptions.py      # Exception yönetimi
├── templates/
│   ├── index.html              # Setup wizard
│   └── dashboard.html          # Sprint planning dashboard
├── static/js/
│   ├── dashboard.js            # Dashboard işlevselliği
│   └── drag-drop.js           # Drag & drop sistemi
├── .trello_tokens.json        # OAuth token'ları (otomatik)
├── .sprinter_exceptions.json  # Exception verileri (otomatik)
└── README.md
```

## 🔒 Güvenlik

- **OAuth Authentication** - Güvenli Trello bağlantısı
- **Local Storage** - Token'lar local olarak saklanır
- **No External Dependencies** - Hassas veriler dışarı gönderilmez
- **Session Management** - Güvenli session yönetimi

## 🐛 Troubleshooting

### Trello Bağlantı Sorunları
```
❌ "OAuth authentication başarısız"
✅ API Key ve OAuth Secret'ı kontrol edin
✅ Callback URL'in doğru olduğundan emin olun
```

### Custom Field Sorunları  
```
❌ "Board'da custom field bulunamadı"
✅ SprintNo, StoryPoint, Sprinter field'larını oluşturun
✅ Field isimlerinin tam olarak eşleştiğinden emin olun
```

### Dashboard Erişim Sorunları
```
❌ "Setup Required" mesajı
✅ Önce setup wizard'ı tamamlayın
✅ Browser cache'ini temizleyin
```

## 🤝 Katkıda Bulunma

1. Repository'yi fork edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 🆘 Destek

Sorunlarınız için:
- Issue açın
- Dokumentasyonu kontrol edin
- Trello API dokümantasyonunu inceleyin

---

**Sprint Analyzer ile takımınızın performansını optimize edin! 🚀**