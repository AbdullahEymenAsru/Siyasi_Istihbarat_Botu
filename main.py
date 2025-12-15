import feedparser
import requests
import smtplib
import os
import datetime
import subprocess
from groq import Groq
from gtts import gTTS  # Seslendirme kütüphanesi
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

# İlgi Alanı Filtreleri (Bunlar geçerse uyarı verir)
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
# 2. AKILLI VERİ TOPLAMA (FİLTRELİ)
# ==========================================
def fetch_news():
    print("📡 Veri toplanıyor ve Kritik Kelimeler taranıyor...")
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
                    
                    # Kritik kelime kontrolü
                    if any(word.lower() in title.lower() for word in KRITIK_KELIMELER):
                        prefix = "🚨 [KRİTİK]"
                    else:
                        prefix = ""

                    buffer += f"[{source}] {prefix} {title} | URL: {link}\n"
        except:
            continue
    return buffer

# ==========================================
# 3. YAPAY ZEKA ANALİZİ (GERİLİM METRELİ)
# ==========================================
def query_ai(text_data):
    print("🧠 Yapay Zeka Stratejik Analiz ve Puanlama Yapıyor...")
    
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
      <p><b>🔥 Sıcak Bölge:</b> (Örn: Gazze veya Ukrayna)</p>
    </div>
    
    <h3>🚨 GÜNÜN STRATEJİK ÖZETİ</h3>
    (Burada olayları anlat, kaynaklara <a href='URL'>Link</a> ver.)
    
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
# 4. SESLİ ASİSTAN (PODCAST MODU) 🎧
# ==========================================
def create_audio_briefing(text_content):
    print("🎙️ Sesli Brifing Hazırlanıyor...")
    try:
        # HTML taglerini temizle ki robot onları okumasın
        clean_text = text_content.replace("<h3>", "").replace("</h3>", ". ").replace("<p>", "").replace("</p>", ". ").replace("<div>", "").replace("</div>", "")
        # Sadece ilk 500 karakteri oku (Çok uzun olmasın)
        speech_text = "Sayın Eymen, Günlük İstihbarat Raporunuz Hazır. " + clean_text[:600] + "... Detaylar raporda."
        
        tts = gTTS(text=speech_text, lang='tr')
        filename = "Gunluk_Brifing.mp3"
        tts.save(filename)
        return filename
    except Exception as e:
        print(f"Ses Hatası: {e}")
        return None

# ==========================================
# 5. TARİHSEL HAFIZA (GITHUB ARŞİVLEME) 📚
# ==========================================
def archive_report(report_body):
    print("💾 Rapor Arşivleniyor...")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    folder = "ARSIV"
    filename = f"{folder}/Rapor_{date_str}.md"
    
    # 1. Klasör yoksa oluştur
    if not os.path.exists(folder):
        os.makedirs(folder)
        
    # 2. Dosyayı yaz
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_body)
    
    # 3. Git komutları ile GitHub'a geri yükle (Push)
    try:
        subprocess.run(["git", "config", "--global", "user.name", "Istihbarat Botu"])
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "add", filename])
        subprocess.run(["git", "commit", "-m", f"Arşiv eklendi: {date_str}"])
        subprocess.run(["git", "push"])
        print("✅ Arşiv başarıyla GitHub'a yüklendi.")
    except Exception as e:
        print(f"⚠️ Arşivleme Hatası (Localde çalışıyorsan normaldir): {e}")

# ==========================================
# 6. MAİL GÖNDERME (MP3 EKLENTİLİ)
# ==========================================
def send_email(report_body, audio_file):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL
    msg['Subject'] = f"🛡️ GÜNLÜK İSTİHBARAT + SESLİ BRİFİNG - {datetime.date.today()}"
    
    html_content = f"""
    <html><body>
        <h2 style="color:#2c3e50;">Kişiselleştirilmiş İstihbarat Raporu</h2>
        {report_body}
        <br><p><i>Sesli özet ektedir.</i></p>
    </body></html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    # MP3 Dosyasını Ekle
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
        print("✅ E-posta ve Ses Dosyası gönderildi!")
    except Exception as e:
        print(f"❌ Mail Hatası: {e}")

# ==========================================
# ÇALIŞTIR
# ==========================================
if __name__ == "__main__":
    raw_data = fetch_news()
    if len(raw_data) > 20:
        # 1. Analiz Et
        report = query_ai(raw_data)
        
        # 2. Arşivle
        archive_report(report)
        
        # 3. Seslendir
        audio_file = create_audio_briefing(report)
        
        # 4. Gönder
        send_email(report, audio_file)
    else:
        print("Veri yok.")
