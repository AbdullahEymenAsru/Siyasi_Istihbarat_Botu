import feedparser
import requests
import smtplib
import os
import datetime
import subprocess
import asyncio
import re
import edge_tts # YENİ MOTOR
from groq import Groq
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ==========================================
# 1. AYARLAR VE ANAHTARLAR
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
ALICI_MAIL = os.environ["ALICI_MAIL"]

client = Groq(api_key=GROQ_API_KEY)

# SES AYARI:
# Erkek sesi için: "tr-TR-AhmetNeural"
# Kadın sesi için: "tr-TR-EmelNeural"
SES_MODELI = "tr-TR-AhmetNeural"

KRITIK_KELIMELER = ["Turkey", "Türkiye", "Erdoğan", "NATO", "F-16", "Missile", "Nuclear", "Gaza", "Syria", "Cyprus"]

rss_sources = {
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'EuroNews': 'https://www.euronews.com/rss?format=mrss&level=theme&name=news',
    'SETA Vakfi': 'https://www.setav.org/feed/',
    'ORSAM': 'https://orsam.org.tr/rss'
}

# ==========================================
# 2. VERİ TOPLAMA
# ==========================================
def fetch_news():
    print("📡 Veri toplanıyor...")
    buffer = ""
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for entry in feed.entries[:3]:
                    title = entry.title
                    link = entry.link
                    
                    if any(word.lower() in title.lower() for word in KRITIK_KELIMELER):
                        prefix = "🚨 [KRİTİK]"
                    else:
                        prefix = ""

                    buffer += f"[{source}] {prefix} {title} | URL: {link}\n"
        except:
            continue
    return buffer

# ==========================================
# 3. YAPAY ZEKA ANALİZİ
# ==========================================
def query_ai(text_data):
    print("🧠 Yapay Zeka Analiz Ediyor...")
    if len(text_data) > 8000: text_data = text_data[:8000]

    system_prompt = """Sen Kıdemli Devlet Danışmanısın.
    Görevin:
    1. Haberleri analiz et.
    2. Küresel gerilimi 1-10 arası puanla.
    3. HTML formatında, kaynak linkleri vererek rapor yaz.
    
    ÖNEMLİ: Raporun en başında bir "DURUM TABLOSU" (Gerilim Metresi) olmalı."""
    
    user_prompt = f"""
    VERİLER:
    {text_data}
    
    ÇIKTI FORMATI (HTML):
    <div style='background:#eee; padding:10px; border-radius:5px;'>
      <h3>📊 GÜNLÜK GERİLİM METRESİ</h3>
      <p><b>🌍 Küresel Risk:</b> ?/10</p>
      <p><b>🇹🇷 Türkiye Jeopolitik Risk:</b> ?/10</p>
      <p><b>🔥 Sıcak Bölge:</b> (Örn: Gazze)</p>
    </div>
    
    <h3>🚨 GÜNÜN STRATEJİK ÖZETİ</h3>
    (Olayları anlat, kaynaklara <a href='URL'>Link</a> ver.)
    
    <h3>🔮 GELECEK PROJEKSİYONU</h3>
    (Analist Notu)
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.5,
            max_tokens=2000,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Hata: {e}"

# ==========================================
# 4. MICROSOFT NEURAL SES MOTORU (GÜÇLÜ) 🎧
# ==========================================
async def generate_neural_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio_briefing(text_content):
    print("🎙️ Neural Ses (Spiker) Hazırlanıyor...")
    
    # TEMİZLİK: HTML taglerini ve Linkleri siliyoruz ki spiker "http slash slash" diye okumasın.
    clean_text = re.sub('<[^<]+?>', '', text_content) # HTML sil
    clean_text = re.sub(r'http\S+', '', clean_text)    # Linkleri sil
    clean_text = clean_text.replace("📊", "").replace("🚨", "").replace("🇹🇷", "Türkiye ") # Emojileri temizle
    
    # Giriş metni ekle
    final_script = "Sayın Abdullah Eymen, Günaydın. İşte bugünün stratejik istihbarat özeti. " + clean_text[:800] + "... Raporun tamamı için maili inceleyiniz."
    
    filename = "Gunluk_Brifing.mp3"
    
    try:
        # Async fonksiyonu burada çalıştırıyoruz
        asyncio.run(generate_neural_voice(final_script, filename))
        return filename
    except Exception as e:
        print(f"Ses Hatası: {e}")
        return None

# ==========================================
# 5. TARİHSEL HAFIZA (ARŞİV)
# ==========================================
def archive_report(report_body):
    print("💾 Rapor Arşivleniyor...")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    folder = "ARSIV"
    filename = f"{folder}/Rapor_{date_str}.md"
    
    if not os.path.exists(folder):
        os.makedirs(folder)
        
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_body)
    
    try:
        subprocess.run(["git", "config", "--global", "user.name", "Istihbarat Botu"])
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "add", filename])
        subprocess.run(["git", "commit", "-m", f"Arşiv: {date_str}"])
        subprocess.run(["git", "push"])
        print("✅ Arşivlendi.")
    except:
        pass

# ==========================================
# 6. MAİL GÖNDERME
# ==========================================
def send_email(report_body, audio_file):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL
    msg['Subject'] = f"🛡️ GÜNLÜK BRİFİNG + PODCAST - {datetime.date.today()}"
    
    html_content = f"""
    <html><body style='font-family: Arial, sans-serif;'>
        <h2 style="color:#2c3e50;">Kişiselleştirilmiş İstihbarat Raporu</h2>
        {report_body}
        <br><p style='color:green;'><b>🎧 Sesli özet ektedir. (Neural Voice Technology)</b></p>
    </body></html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    if audio_file and os.path.exists(audio_file):
        with open(audio_file, "rb") as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{audio_file}"')
        msg.attach(part)

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
        archive_report(report)
        audio_file = create_audio_briefing(report)
        send_email(report, audio_file)
    else:
        print("Veri yok.")
