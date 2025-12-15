import feedparser
import requests
import smtplib
import os
import datetime
import time # Bekleme yapmak için gerekli
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. GİRDİLER
# ==========================================
HF_API_KEY = os.environ["HF_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
ALICI_MAIL = os.environ["ALICI_MAIL"]

# Model: Mistral-7B (Daha kararlı versiyonu)
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}

# ==========================================
# 2. KAYNAKLAR
# ==========================================
rss_sources = {
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'EuroNews': 'https://www.euronews.com/rss?format=mrss&level=theme&name=news',
    'SETA Vakfi': 'https://www.setav.org/feed/',
    'ORSAM': 'https://orsam.org.tr/rss'
}

# ==========================================
# 3. VERİ TOPLAMA
# ==========================================
def fetch_news():
    print("📡 Veri toplanıyor...")
    buffer = ""
    # Bot engeline takılmamak için tarayıcı kimliği
    chrome_agent = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=chrome_agent, timeout=10)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                buffer += f"\n--- {source} ---\n"
                # Her kaynaktan 2 haber al
                for entry in feed.entries[:2]:
                    title = entry.title
                    buffer += f"- {title}\n"
        except:
            continue
    return buffer

# ==========================================
# 4. YAPAY ZEKA ANALİZİ (GÜÇLENDİRİLMİŞ)
# ==========================================
def query_ai(text_data):
    print("🧠 Yapay Zeka uyanıyor ve analiz yapıyor...")
    
    prompt = f"""[INST] Sen uzman bir siyaset bilimcisin. Aşağıdaki haber başlıklarını analiz et ve Türkçe bir özet rapor yaz.
    
    HABERLER:
    {text_data}
    
    GÖREV:
    Bu haberlere dayanarak kısa bir "Durum Raporu" oluştur.
    1. GÜNÜN OLAYI
    2. BÖLGESEL DURUM
    3. TÜRKİYE ANALİZİ
    [/INST]"""
    
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 1000, "return_full_text": False},
        "options": {"wait_for_model": True} # <--- ÖNEMLİ: Modelin uyanmasını bekle
    }
    
    # 3 KERE DENEME MEKANİZMASI (RETRY LOGIC)
    for i in range(3):
        try:
            response = requests.post(API_URL, headers=HEADERS, json=payload)
            response_json = response.json()
            
            # Eğer başarılıysa metni döndür
            if isinstance(response_json, list) and 'generated_text' in response_json[0]:
                return response_json[0]['generated_text']
            
            # Eğer model yükleniyorsa bekle
            if 'error' in response_json and 'loading' in response_json['error']:
                print(f"⚠️ Model yükleniyor... Bekleniyor ({i+1}/3)")
                time.sleep(20) # 20 saniye bekle tekrar dene
                continue
                
            # Başka bir hata varsa yazdır
            print(f"⚠️ API Hatası: {response_json}")
            
        except Exception as e:
            print(f"⚠️ Bağlantı Hatası: {e}")
            time.sleep(5)
            
    return "Yapay Zeka şu an aşırı yoğun veya yanıt vermedi. (Ham veriler yukarıdadır)"

# ==========================================
# 5. MAİL GÖNDERME
# ==========================================
def send_email(report_body):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL
    msg['Subject'] = f"🛡️ GÜNLÜK İSTİHBARAT RAPORU - {datetime.date.today()}"
    
    # HTML Formatı (Daha güzel görünüm için)
    html_content = f"""
    <div style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #2c3e50;">🌍 GÜNLÜK SİYASİ ANALİZ</h2>
        <hr>
        <pre style="white-space: pre-wrap; font-family: inherit; font-size: 14px;">{report_body}</pre>
        <br>
        <p style="font-size: 12px; color: #777;"><i>Bu rapor GitHub Actions tarafından otomatik üretilmiştir.</i></p>
    </div>
    """
    
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, ALICI_MAIL, msg.as_string())
        server.quit()
        print("✅ E-posta başarıyla gönderildi!")
    except Exception as e:
        print(f"❌ Mail Gönderme Hatası: {e}")

# ==========================================
# ÇALIŞTIR
# ==========================================
if __name__ == "__main__":
    raw_data = fetch_news()
    if len(raw_data) > 20:
        report = query_ai(raw_data)
        send_email(report)
        print("İşlem Tamam.")
    else:
        print("Veri toplanamadı.")
