import feedparser
import requests
import smtplib
import os
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. GİRDİLER (GITHUB SECRETS'TEN ALIR)
# ==========================================
HF_API_KEY = os.environ["HF_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
ALICI_MAIL = os.environ["ALICI_MAIL"]

# Model: Mistral-7B (Ücretsiz ve Zeki)
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}

# ==========================================
# 2. KAYNAKLAR (TWITTER YERİNE SAĞLAM RSS)
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
                for entry in feed.entries[:2]:
                    title = entry.title
                    buffer += f"- {title}\n"
        except:
            continue
    return buffer

# ==========================================
# 4. YAPAY ZEKA ANALİZİ
# ==========================================
def query_ai(text_data):
    prompt = f"""[INST] Sen bir strateji uzmanısın. Aşağıdaki haber başlıklarını kullanarak Türkçe bir "Günlük İstihbarat Özeti" yaz.
    
    HABERLER:
    {text_data}
    
    FORMAT:
    1. GÜNÜN OLAYI
    2. BÖLGESEL DURUM
    3. TÜRKİYE ANALİZİ
    [/INST]"""
    
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 600, "return_full_text": False}}
    response = requests.post(API_URL, headers=HEADERS, json=payload)
    try:
        return response.json()[0]['generated_text']
    except:
        return "Yapay Zeka Analizi Yapılamadı (API Yoğunluğu)."

# ==========================================
# 5. MAİL GÖNDERME
# ==========================================
def send_email(report_body):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL
    msg['Subject'] = f"🛡️ GÜNLÜK İSTİHBARAT RAPORU - {datetime.date.today()}"
    
    # Raporu HTML formatına çevirelim ki güzel görünsün
    html_content = f"""
    <h2>GÜNLÜK SİYASİ ANALİZ</h2>
    <pre style="font-family: Arial; font-size: 14px;">{report_body}</pre>
    <br>
    <p><i>Bu rapor GitHub Actions tarafından otomatik üretilmiştir.</i></p>
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
        print(report)
    else:
        print("Veri yok.")