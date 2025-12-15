import feedparser
import requests
import smtplib
import os
import datetime
from groq import Groq
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. AYARLAR
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
ALICI_MAIL = os.environ["ALICI_MAIL"]

# Groq İstemcisini Başlat
client = Groq(api_key=GROQ_API_KEY)

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
    # Bot korumalarını aşmak için User-Agent
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                buffer += f"\n--- KAYNAK: {source} ---\n"
                for entry in feed.entries[:2]:
                    title = entry.title
                    buffer += f"- {title}\n"
        except:
            continue
    return buffer

# ==========================================
# 4. YAPAY ZEKA ANALİZİ (GÜNCEL MODEL)
# ==========================================
def query_ai(text_data):
    print("🧠 Yapay Zeka Analiz Yapıyor (Llama 3.3)...")
    
    if len(text_data) > 5000:
        text_data = text_data[:5000]

    system_prompt = """Sen uzman bir Uluslararası İlişkiler analistisin. 
    Verilen haber başlıklarını sentezle ve Türkiye odaklı bir stratejik rapor yaz.
    Sadece haberleri çevirme, arkasındaki anlamı ve stratejik riski yorumla."""
    
    user_prompt = f"""
    HABERLER:
    {text_data}
    
    GÖREV:
    Kısa ve net bir "Günlük İstihbarat Özeti" oluştur.
    
    RAPOR ŞABLONU:
    1. 🚨 GÜNÜN KRİTİK GELİŞMESİ
    2. 🌍 KÜRESEL DENGELER (ABD/Rusya/Çin Hamleleri)
    3. 🇹🇷 TÜRKİYE İÇİN RİSK VE FIRSATLAR
    """

    try:
        completion = client.chat.completions.create(
            # --- DEĞİŞEN KISIM BURASI ---
            # 'llama3-8b-8192' yerine en yeni ve güçlü modeli kullanıyoruz:
            model="llama-3.3-70b-versatile", 
            
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6,
            max_tokens=1500,
        )
        return completion.choices[0].message.content
        
    except Exception as e:
        return f"Yapay Zeka Hatası: {e}"

# ==========================================
# 5. MAİL GÖNDERME
# ==========================================
def send_email(report_body):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL
    msg['Subject'] = f"⚡ GÜNLÜK İSTİHBARAT RAPORU - {datetime.date.today()}"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; color: #2c3e50; line-height: 1.6;">
        <h2 style="color: #c0392b;">🌍 GÜNLÜK SİYASİ ANALİZ</h2>
        <hr>
        <div style="white-space: pre-wrap; font-size: 14px;">{report_body}</div>
        <br>
        <p style="font-size: 11px; color: #95a5a6;"><i>Analiz Motoru: Llama 3.3 (70B) via Groq</i></p>
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
