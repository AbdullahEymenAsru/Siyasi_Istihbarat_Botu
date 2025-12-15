import feedparser
import requests
import smtplib
import os
import datetime
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. AYARLAR
# ==========================================
HF_API_KEY = os.environ["HF_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
ALICI_MAIL = os.environ["ALICI_MAIL"]

# MODEL DEĞİŞİKLİĞİ: Zephyr-7B (Mistral tabanlıdır ama daha hızlı tepki verir)
API_URL = "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta"
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
    print("🧠 Yapay Zeka (Zephyr) analiz yapıyor...")

    # ÖNLEM: Eğer metin çok uzunsa API hata verir (503 veya 400).
    # Metni son 3000 karakterle sınırlayalım.
    if len(text_data) > 3000:
        text_data = text_data[:3000] + "..."

    prompt = f"""<|system|>
Sen uzman bir siyaset bilimcisin. Aşağıdaki haber başlıklarını analiz et ve Türkçe bir özet rapor yaz.
</s>
<|user|>
HABERLER:
{text_data}

GÖREV:
Bu haberlere dayanarak kısa bir "Durum Raporu" oluştur.
1. GÜNÜN OLAYI
2. BÖLGESEL DURUM
3. TÜRKİYE ANALİZİ
</s>
<|assistant|>"""
    
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 800, "return_full_text": False},
        "options": {"wait_for_model": True}
    }
    
    # 5 KERE DENEME MEKANİZMASI (Daha İnatçı)
    for i in range(5):
        try:
            response = requests.post(API_URL, headers=HEADERS, json=payload)
            result = response.json()
            
            # Başarılı cevap kontrolü
            if isinstance(result, list) and 'generated_text' in result[0]:
                return result[0]['generated_text']
            
            # Model yükleniyorsa bekle
            if isinstance(result, dict) and 'error' in result:
                print(f"⚠️ Deneme {i+1}/5: {result['error']}")
                time.sleep(30) # 30 saniye bekle (Daha uzun)
            else:
                print(f"⚠️ Bilinmeyen Yanıt: {result}")
                time.sleep(5)
                
        except Exception as e:
            print(f"⚠️ Bağlantı Hatası: {e}")
            time.sleep(10)
            
    return "Yapay Zeka 5 denemeye rağmen yanıt veremedi. Hugging Face sunucuları şu an aşırı yoğun."

# ==========================================
# 5. MAİL GÖNDERME
# ==========================================
def send_email(report_body):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL
    msg['Subject'] = f"🛡️ GÜNLÜK İSTİHBARAT RAPORU - {datetime.date.today()}"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #d35400;">🌍 GÜNLÜK SİYASİ ANALİZ (Zephyr AI)</h2>
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
        print("✅ E-posta gönderildi!")
    except Exception as e:
        print(f"❌ Mail Hatası: {e}")

# ==========================================
# ÇALIŞTIR
# ==========================================
if __name__ == "__main__":
    raw_data = fetch_news()
    if len(raw_data) > 20:
        report = query_ai(raw_data)
        send_email(report)
    else:
        print("Veri yok.")
