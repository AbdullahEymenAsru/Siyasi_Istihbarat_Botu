# Siyasi_Istihbarat_Botu

# 🛡️ SAVAŞ ODASI (War Room): Küresel İstihbarat & Strateji Ağı

![AI](https://img.shields.io/badge/AI-Llama%203.3-purple) 
![Status](https://img.shields.io/badge/Status-Operational-green) 
![Encryption](https://img.shields.io/badge/Security-E2EE-blue)

**Savaş Odası**, OSINT (Açık Kaynak İstihbaratı) verilerini otonom olarak toplayan, Yapay Zeka ile stratejik analiz yapan ve sonuçları interaktif bir dashboard üzerinden sunan gelişmiş bir istihbarat simülasyonudur.

---

## 🚀 Temel Kabiliyetler

### 1. 🕵️‍♂️ Otonom Researcher (Ajan Ağı)
* **Geniş Kaynak Havuzu:** BBC, Reuters, Al Jazeera, TASS ve stratejik Think-Tank (FP, Carnegie, ISW) raporlarını 7/24 tarar.
* **Önceliklendirme:** Haberleri "Stratejik Önem" ve "Sıcak Çatışma" puanlarına göre filtreler.

### 2. 🧠 Stratejik Analiz Motoru
* **Derin Analiz:** Olayları sadece özetlemez; Realizm ve Liberalizm gibi IR (Uluslararası İlişkiler) teorileriyle analiz eder.
* **Makine Öğrenimi:** Arşivdeki tüm geçmiş raporları tarayarak olayların tarihsel gelişimini sentezler.
* **Akademik Atıf:** Analizlerde kullanılan teoriler için otomatik DOI linkleri ve kaynakça oluşturur.

### 3. 📡 Dağıtım & Dashboard
* **E2EE Dashboard:** Streamlit üzerinden uçtan uca şifreli, interaktif bir harekat masası sunar.
* **Sesli Brifing:** Günlük raporları yapay zeka ile seslendirerek mail ekinde gönderir.
* **İlişki Ağı Haritası:** Aktörler arasındaki gerilim ve ittifakları görsel bir network grafiği olarak çizer.

---

## 🛠️ Kurulum ve Çalıştırma

Sistemi yerel makinenizde ayağa kaldırmak için:

1. **Bağımlılıkları Yükleyin:**
   ```bash
   pip install -r requirements.txt

   streamlit run dashboard.py

NOT: !!!Sistemi başlatmadan önce .streamlit/secrets.toml dosyasını oluşturduğunuzdan ve anahtarlarınızı eklediğinizden emin olun.!!!

---
🔐 Güvenlik ve Anahtarlar (Secrets)
Sistemin tam kapasite çalışması için aşağıdaki anahtarların GitHub Secrets ve Streamlit Secrets bölümlerine tanımlanması ZORUNLUDUR:

Anahtar                      Açıklama
GROQ_API_KEY => Llama 3.3 modelini çalıştıran yapay zeka motoru.

SUPABASE_URL => Veritabanı bağlantı adresi.

SUPABASE_KEY => Veritabanı erişim anahtarı.

GMAIL_USER => Raporların gönderileceği Gmail adresi.

GMAIL_PASSWORD => Google Uygulama Şifresi.

---
🏗️ Sistem Mimarisi

Toplama: RSS ve Web Scrapping ile ham veri girişi.

Hafıza: Arşivdeki .md dosyalarından tarihsel bağlam çekimi.

Analiz: Groq üzerinden Llama 3.3 ile stratejik yorumlama.

Çıktı: Markdown rapor, Network Graph ve MP3 ses dosyası.

Dağıtım: SMTP üzerinden Konsey Üyelerine iletim.


Uyarı: Bu yazılım stratejik analiz ve eğitim amaçlı geliştirilmiş bir OSINT aracıdır.
