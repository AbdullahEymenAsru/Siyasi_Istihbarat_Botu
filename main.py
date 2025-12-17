import feedparser
import smtplib
import os
import datetime
import subprocess
import asyncio
import re
import edge_tts
import trafilatura
from groq import Groq
from supabase import create_client, Client
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ==========================================
# 1. AYARLAR & GÜVENLİK
# ==========================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SES_MODELI = "tr-TR-AhmetNeural"

def get_email_list():
    try:
        response = supabase.table("abone_listesi").select("email").execute()
        return [row['email'] for row in response.data] if response.data else []
    except: return []

ALICI_LISTESI = get_email_list()

# ==========================================
# 2. İSTİHBARAT KAYNAKLARI (BATI - DOĞU - SAHA)
# ==========================================

RSS_SOURCES = {
    "STRATEJIK": [
        "https://foreignpolicy.com/feed/",
        "https://www.csis.org/rss/analysis",
        "https://carnegieendowment.org/rss/solr/get/all",
        "https://warontherocks.com/feed/",
        "https://www.cfr.org/rss/newsletters/daily-brief",
        "https://www.setav.org/feed/"
    ],
    "GLOBAL_HABER": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "http://rss.cnn.com/rss/edition_world.rss",
        "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
        "http://www.xinhuanet.com/english/rss/worldrss.xml", # Çin
        "https://tass.com/rss/v2.xml",                       # Rusya
        "https://www.aljazeera.com/xml/rss/all.xml",         # Orta Doğu
        "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms" # Hindistan
    ],
    "TELEGRAM_SAHA": [
        "https://rsshub.app/telegram/channel/geopolitics_live",
        "https://rsshub.app/telegram/channel/intelslava"
    ]
}

# ==========================================
# 3. VERİ TOPLAMA VE FİLTRELEME (12 SAAT KONTROLÜ)
# ==========================================

def get_full_text(url):
    if "t.me" in url or ".pdf" in url: return None
    try:
        downloaded = trafilatura.fetch_url(url)
        return trafilatura.extract(downloaded)[:2000] if downloaded else None
    except: return None

def fetch_news():
    print("🕵️‍♂️ KÜRESEL İSTİHBARAT AĞI TARANIYOR (SON 12-24 SAAT)...")
    
    ai_input_data = []
    reference_html_list = []
    
    # --- TEKRAR ÖNLEME MEKANİZMASI ---
    # Supabase'e bakıyoruz: Son 24 saatte bu linki zaten raporladık mı?
    # Eğer sistem 12 saatte bir çalışırsa, bu kontrol sayesinde
    # sadece "yeni düşen" haberleri alır.
    try:
        past_24h = datetime.datetime.now() - datetime.timedelta(hours=24)
        response = supabase.table("reports").select("content").gte("created_at", past_24h.isoformat()).execute()
        past_content = str(response.data)
    except: past_content = ""

    all_urls = []
    for cat in RSS_SOURCES.values(): all_urls.extend(cat)
    
    counter = 1
    # Her kaynaktan en taze 1 haberi al (Hız ve verimlilik için)
    for url in all_urls:
        try:
            feed = feedparser.parse(url)
            if not feed.entries: continue

            for entry in feed.entries[:1]: 
                # KRİTİK FİLTRE: Link daha önce işlendi mi?
                if entry.link not in past_content:
                    full = get_full_text(entry.link)
                    summary = full if full else entry.get('summary', '')[:600]
                    title = entry.title
                    source = feed.feed.get('title', 'Kaynak')
                    
                    # AI'ya gidecek ham veri
                    ai_input_data.append(f"[{counter}] SOURCE: {source} | TITLE: {title} | CONTENT: {summary}")
                    
                    # E-postanın altındaki kaynakça listesi (Temiz Link Yapısı)
                    reference_html_list.append(
                        f"<li style='margin-bottom:6px; font-size:12px;'>"
                        f"<b>[{counter}]</b> <a href='{entry.link}' target='_blank' style='color:#3498db; text-decoration:none;'>{title}</a> "
                        f"<span style='color:#95a5a6;'> — {source}</span></li>"
                    )
                    counter += 1
        except: continue

    return "\n\n".join(ai_input_data), "".join(reference_html_list)

# ==========================================
# 4. DOKTRİNER ANALİZ (PROFESYONEL HTML)
# ==========================================

def run_agent_workflow(current_data):
    print("🧠 STRATEJİK ANALİZ VE TASARIM OLUŞTURULUYOR...")
    
    system_prompt = f"""
    Sen 'Küresel Savaş Odası'nın Baş Stratejistisin.
    GÖREVİN: İstihbarat verilerini analiz etmek ve **görsel olarak ferah, okunabilir bir HTML rapor** hazırlamak.

    **TASARIM VE İÇERİK KURALLARI:**
    1. **ANALİZ YÖNTEMİ:** Olayları özetleme, *sonuçlarını ve geleceğini* yaz. (Realizm, Güç Dengesi).
    2. **ATIF:** Bilgi verdiğin her yerde `` kullan.
    3. **TÜRKÇE:** Dil resmi, akıcı ve terminolojik olsun.

    **HTML ÇIKTI FORMATI (BUNU KULLAN):**
    
    <div style="background-color: #fff0f0; border-left: 5px solid #e74c3c; padding: 20px; margin-bottom: 30px; border-radius: 4px;">
        <h2 style="color: #c0392b; margin-top: 0; font-family: 'Georgia', serif; font-size: 20px;">🚨 KIRMIZI ALARM (Sıcak Çatışma & Riskler)</h2>
        <p style="color: #2c3e50; line-height: 1.6; margin-bottom: 0;">
            (Buraya en acil 1-2 çatışma veya kriz haberini ve gelecek analizini yaz. kullan.)
        </p>
    </div>

    <div style="margin-bottom: 30px;">
        <h2 style="color: #2980b9; border-bottom: 2px solid #eee; padding-bottom: 10px; font-family: 'Georgia', serif; font-size: 18px;">🌍 KÜRESEL UFUK TURU</h2>
        
        <div style="margin-bottom: 15px;">
            <strong style="color: #34495e;">📍 Asya-Pasifik & Doğu:</strong>
            <span style="color: #555; line-height: 1.6;">(Çin, Hindistan, Rusya gelişmeleri.)</span>
        </div>
        
        <div style="margin-bottom: 15px;">
            <strong style="color: #34495e;">📍 Avrupa & Batı Bloku:</strong>
            <span style="color: #555; line-height: 1.6;">(ABD, AB, Ukrayna gelişmeleri.)</span>
        </div>

        <div>
            <strong style="color: #34495e;">📍 Orta Doğu Hattı:</strong>
            <span style="color: #555; line-height: 1.6;">(İsrail, Filistin, İran, Türkiye ekseni.)</span>
        </div>
    </div>

    <div style="background-color: #f8f9fa; border: 1px solid #e1e4e8; padding: 20px; border-radius: 6px; margin-bottom: 30px;">
        <h2 style="color: #2c3e50; margin-top: 0; font-family: 'Georgia', serif; font-size: 18px;">🧠 THINK-TANK & AKADEMİK DERİNLİK</h2>
        <p style="color: #555; line-height: 1.6;">
            (Buraya Foreign Policy, SETA gibi kaynaklardan derin bir analiz yaz.)
        </p>
        
        <hr style="border: 0; border-top: 1px dashed #ccc; margin: 15px 0;">
        
        <p style="font-size: 14px; color: #2c3e50;">
            <b>🎓 Günün Kavramı:</b> (Olayları açıklayan bir Uluslararası İlişkiler kavramı - Örn: Security Dilemma)<br>
            <b>📚 Okuma Önerisi:</b> (Yazar Adı - Makale/Kitap Başlığı)
        </p>
    </div>

    <div style="border-left: 5px solid #27ae60; padding-left: 15px;">
        <h2 style="color: #27ae60; margin-top: 0; font-family: 'Georgia', serif; font-size: 18px;">🔮 GELECEK SENARYOLARI & POLİTİKA</h2>
        <p style="color: #2c3e50; line-height: 1.6;">
            (Önümüzdeki 30 gün için öngörülerin ve Türkiye için kısa bir stratejik tavsiye.)
        </p>
    </div>
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"İSTİHBARAT VERİLERİ:\n{current_data}"}
            ],
            temperature=0.4
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"<p>Analiz hatası: {e}</p>"

# ==========================================
# 5. SES & ARŞİV & DAĞITIM
# ==========================================

async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio_summary(report_html):
    print("🎙️ Sesli özet hazırlanıyor...")
    clean = re.sub('<[^<]+?>', '', report_html)[:1500]
    filename = "Gunluk_Ozet.mp3"
    try:
        asyncio.run(generate_voice(clean, filename))
        return filename
    except: return None

def send_email(report_body, references_html, audio_file):
    if not ALICI_LISTESI: return
    print(f"📧 {len(ALICI_LISTESI)} kişiye gönderiliyor...")
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    
    # NİHAİ E-POSTA ŞABLONU (FERAH TASARIM)
    email_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f4f4; }}
        .container {{ max-width: 700px; margin: 20px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        .header {{ background-color: #2c3e50; color: #ffffff; padding: 30px 20px; text-align: center; }}
        .header h1 {{ margin: 0; font-family: 'Georgia', serif; letter-spacing: 1px; font-size: 24px; text-transform: uppercase; }}
        .header p {{ margin: 5px 0 0; font-size: 13px; color: #bdc3c7; font-style: italic; }}
        .content {{ padding: 40px 30px; color: #333333; }}
        .footer {{ background-color: #ecf0f1; padding: 20px; text-align: center; font-size: 12px; color: #7f8c8d; }}
        .btn {{ display: inline-block; background-color: #e74c3c; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 10px; font-size: 12px; }}
        .ref-section {{ margin-top: 40px; padding-top: 20px; border-top: 2px solid #f0f0f0; }}
        .ref-title {{ color: #95a5a6; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; font-weight: bold; }}
        ul {{ padding-left: 20px; margin: 0; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>KÜRESEL SAVAŞ ODASI</h1>
                <p>"Doktriner Analiz & Stratejik İstihbarat" | {today}</p>
                <a href="https://siyasi-istihbarat-botu.streamlit.app/" class="btn" style="color:white;">🚀 CANLI SAVAŞ ODASI PANELİ</a>
            </div>

            <div class="content">
                {report_body}

                <div class="ref-section">
                    <div class="ref-title">📚 DOĞRULANMIŞ İSTİHBARAT AKIŞI & LİNKLER</div>
                    <ul>
                        {references_html}
                    </ul>
                </div>
            </div>

            <div class="footer">
                Bu rapor, açık kaynak istihbarat (OSINT) verilerinin yapay zeka destekli stratejik analizidir.<br>
                &copy; 2025 Savaş Odası | Gizli değildir, dağıtılabilir.
            </div>
        </div>
    </body>
    </html>
    """

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)

        for email in ALICI_LISTESI:
            msg = MIMEMultipart()
            msg['From'] = GMAIL_USER
            msg['To'] = email
            msg['Subject'] = f"🛡️ SAVAŞ ODASI: Stratejik Durum - {today}"
            msg.attach(MIMEText(email_html, 'html'))

            if audio_file and os.path.exists(audio_file):
                with open(audio_file, "rb") as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{audio_file}"')
                    msg.attach(part)

            server.sendmail(GMAIL_USER, email, msg.as_string())
        
        server.quit()
        print("✅ Operasyon Tamamlandı.")
    except Exception as e:
        print(f"❌ Mail Hatası: {e}")

# ==========================================
# 6. ÇALIŞTIRMA
# ==========================================

if __name__ == "__main__":
    news_data, ref_html_list = fetch_news()
    
    if news_data:
        report_html = run_agent_workflow(news_data)
        audio = create_audio_summary(report_html)
        
        try:
            supabase.table("reports").insert({"content": report_html}).execute()
            
            file_name = f"ARSIV/Rapor_{datetime.datetime.now().strftime('%Y-%m-%d')}.md"
            if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(report_html + "\n\n<h3>REFERANSLAR</h3>\n<ul>" + ref_html_list + "</ul>")
            
            subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"], capture_output=True)
            subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"], capture_output=True)
            subprocess.run(["git", "add", file_name], capture_output=True)
            subprocess.run(["git", "commit", "-m", "Rapor"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
        except: pass

        send_email(report_html, ref_html_list, audio)
    else:
        print("⚠️ Yeterli yeni veri bulunamadı.")
