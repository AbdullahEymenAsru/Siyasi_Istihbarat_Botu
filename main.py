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
# 3. VERİ TOPLAMA (LİNKLERİ YAKALAMA)
# ==========================================
def fetch_news():
    print("📡 Veri ve Linkler toplanıyor...")
    buffer = ""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for entry in feed.entries[:3]:
                    title = entry.title
                    link = entry.link # <--- LİNKİ BURADA YAKALIYORUZ
                    
                    # AI'ya veriyi şu formatta vereceğiz:
                    # [BBC World] Başlık | URL: http://...
                    buffer += f"[{source}] {title} | URL: {link}\n"
        except:
            continue
    return buffer

# ==========================================
# 4. YAPAY ZEKA ANALİZİ (HTML LİNK FORMATI)
# ==========================================
def query_ai(text_data):
    print("🧠 Yapay Zeka Linkleri İşliyor...")
    
    if len(text_data) > 8000: # Context window geniş
        text_data = text_data[:8000]

    system_prompt = """Sen uzman bir İstihbarat Analistisin. 
    Görevin: Haberleri analiz etmek ve stratejik bir özet çıkarmak.
    
    ÇOK ÖNEMLİ KURAL (LİNK VERME):
    Analizinde bahsettiğin her kritik olayın kaynağına LİNK vermek zorundasın.
    HTML formatı kullanmalısın.
    Örnek: "İsrail saldırıları arttırdı (<a href='http://...'>Al Jazeera</a>)."
    veya
    "SETA'nın <a href='http://...'>son raporuna göre</a> Türkiye..."
    
    Asla uydurma link verme. Sana verilen "URL:" kısmındaki linki kullan."""
    
    user_prompt = f"""
    HAM VERİLER VE LİNKLER:
    {text_data}
    
    GÖREV:
    Bu verileri kullanarak "Tıklanabilir Kaynaklı Durum Raporu" yaz.
    Raporun dili Türkçe olsun.
    
    RAPOR FORMATI (HTML KULLAN):
    <h3>🚨 GÜNÜN MANŞETİ</h3>
    <p>...</p>
    
    <h3>🌍 KÜRESEL DENGELER</h3>
    <p>...</p>
    
    <h3>🇹🇷 TÜRKİYE PERSPEKTİFİ</h3>
    <p>...</p>
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,
            max_tokens=2000,
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
    msg['Subject'] = f"🔗 TIKLANABİLİR İSTİHBARAT RAPORU - {datetime.date.today()}"
    
    # Mail gövdesini güzelleştiriyoruz
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #2c3e50; text-align: center;">🌍 GÜNLÜK SİYASİ ANALİZ</h2>
            <hr style="border: 0; border-top: 1px solid #eee;">
            
            <div>{report_body}</div>
            
            <br>
            <hr style="border: 0; border-top: 1px solid #eee;">
            <p style="font-size: 11px; text-align: center; color: #999;">
                <i>Bu rapor Groq (Llama 3.3) kullanılarak oluşturulmuştur. Kaynaklara tıklayarak orijinallerini okuyabilirsiniz.</i>
            </p>
        </div>
    </body>
    </html>
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
