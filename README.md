English:

# 🛡️ WAR ROOM: Global Intelligence & Strategic Network

![AI](https://img.shields.io/badge/AI-Llama%203.3-purple) 
![Status](https://img.shields.io/badge/Status-Operational-green) 
![Security](https://img.shields.io/badge/Security-E2EE-blue)

**War Room** is an advanced intelligence simulation that autonomously gathers Open Source Intelligence (OSINT) data, performs strategic analysis via AI (Llama 3.3), and presents findings through an interactive encrypted dashboard.

---

## 🚀 Core Capabilities

### 1. 🕵️‍♂️ Autonomous Researcher (Agent Network)
* **Global Resource Pool:** Scans BBC, Reuters, Al Jazeera, TASS, and strategic Think-Tanks (Foreign Policy, Carnegie, ISW) 24/7.
* **Prioritization:** Filters news based on "Strategic Significance" and "Conflict Intensity" scoring.

### 2. 🧠 Strategic Analysis Engine
* **Deep Analysis:** Goes beyond summaries; analyzes events using International Relations (IR) theories such as Realism and Liberalism.
* **Contextual Learning:** Scans all historical reports in the archive to synthesize the evolution of ongoing geopolitical trends.
* **Academic Citations:** Automatically generates bibliographies and DOI links for the theories and articles utilized.

### 3. 📡 Distribution & Dashboard
* **E2EE Dashboard:** Provides an end-to-end encrypted interactive command center via Streamlit.
* **Audio Briefing:** Narrates daily reports using AI voice synthesis and attaches them to intelligence emails.
* **Geopolitical Map:** Visualizes tensions and alliances between global actors as a dynamic network graph.

---

## 🛠️ Installation and Setup

To deploy the system on your local machine:

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt

   streamlit run dashboard.py
---
Key	|       Description

GROQ_API_KEY => Access key for the Llama 3.3 AI analysis engine.

SUPABASE_URL => Connection URL for the cloud intelligence database.

SUPABASE_KEY => Access key for database read/write operations.

GMAIL_USER => The Gmail address used to dispatch intelligence reports.

GMAIL_PASSWORD => 16-digit Google App Password (not your standard password).


Note: !!!Ensure you create a .streamlit/secrets.toml file for local execution and populate it with your keys as shown below:!!!

Sample representation:

GROQ_API_KEY = "your_key"

SUPABASE_URL = "your_url"

SUPABASE_KEY = "your_key"

GMAIL_USER = "sender_email"

GMAIL_PASSWORD = "app_password"

---
🏗️ System Architecture
Collection: Raw data ingestion via RSS feeds and Web Scraping.

Memory: Contextual retrieval from archived .md analysis files.

Analysis: Strategic interpretation via Llama 3.3 on Groq Cloud.

Output: Generation of Markdown reports, Network Graphs, and MP3 audio briefings.

Dispatch: Automated distribution to Council Members via SMTP.



Disclaimer: This software is an OSINT tool developed for strategic analysis and academic research purposes.



Türkçe:

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


---
🔐 Güvenlik ve Anahtarlar (Secrets)
Sistemin tam kapasite çalışması için aşağıdaki anahtarların GitHub Secrets ve Streamlit Secrets bölümlerine tanımlanması ZORUNLUDUR:

Anahtar          |            Açıklama

GROQ_API_KEY => Llama 3.3 modelini çalıştıran yapay zeka motoru.

SUPABASE_URL => Veritabanı bağlantı adresi.

SUPABASE_KEY => Veritabanı erişim anahtarı.

GMAIL_USER => Raporların gönderileceği Gmail adresi.

GMAIL_PASSWORD => Google Uygulama Şifresi.


NOT: !!!Sistemi başlatmadan önce .streamlit/secrets.toml dosyasını oluşturduğunuzdan ve anahtarlarınızı eklediğinizden emin olun.!!!

Örnek gösterim:

GROQ_API_KEY = "kendi_anahtarı"

SUPABASE_URL = "kendi_urlsi"

SUPABASE_KEY = "kendi_keyi"

GMAIL_USER = "gönderim_yapılacak_mail"

GMAIL_PASSWORD = "gmail_api"

---
🏗️ Sistem Mimarisi

Toplama: RSS ve Web Scrapping ile ham veri girişi.

Hafıza: Arşivdeki .md dosyalarından tarihsel bağlam çekimi.

Analiz: Groq üzerinden Llama 3.3 ile stratejik yorumlama.

Çıktı: Markdown rapor, Network Graph ve MP3 ses dosyası.

Dağıtım: SMTP üzerinden Konsey Üyelerine iletim.


Uyarı: Bu yazılım stratejik analiz ve eğitim amaçlı geliştirilmiş bir OSINT aracıdır.
