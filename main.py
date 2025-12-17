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
# 1. AYARLAR & GÜVENLİK PROTOKOLLERİ
# ==========================================

# Çevresel Değişkenler
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# İstemci Kurulumları
client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SES_MODELI = "tr-TR-AhmetNeural"

# Dinamik Alıcı Listesi
def get_email_list():
    try:
        response = supabase.table("abone_listesi").select("email").execute()
        return [row['email'] for row in response.data] if response.data else []
    except Exception as e:
        print(f"⚠️ Alıcı listesi hatası: {e}")
        return []

ALICI_LISTESI = get_email_list()

# ==========================================
# 2. GENİŞLETİLMİŞ KÜRESEL İSTİHBARAT AĞI
# ==========================================

RSS_SOURCES = {
    # --- STRATEJİK DÜŞÜNCE KURULUŞLARI ---
    "THINK_TANK": [
        "https://foreignpolicy.com/feed/",
        "https://www.csis.org/rss/analysis",          # CSIS
        "https://www.setav.org/feed/",                # SETA
        "https://carnegieendowment.org/rss/solr/get/all",
        "https://www.understandingwar.org/feeds.xml", # ISW
        "https://warontherocks.com/feed/",
        "https://www.cfr.org/rss/newsletters/daily-brief"
    ],

    # --- BATI VE DOĞU MEDYA KANALLARI ---
    "GLOBAL_MEDIA": [
        "http://feeds.bbci.co.uk/news/world/rss.xml", # BBC
        "http://rss.cnn.com/rss/edition_world.rss",   # CNN
        "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
        "https://www.voanews.com/api/z$omeovuro",     # VOA
        "http://www.xinhuanet.com/english/rss/worldrss.xml", # Çin (Xinhua)
        "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", # Hindistan
        "https://www.dawn.com/feeds/home",            # Pakistan
        "https://tass.com/rss/v2.xml",                # Rusya (TASS)
        "https://www.aljazeera.com/xml/rss/all.xml"   # Katar
    ],

    # --- SAHA VE TELEGRAM ---
    "TELEGRAM": [
        "https://rsshub.app/telegram/channel/geopolitics_live",
        "https://rsshub.app/telegram/channel/intelslava"
    ]
}

# ==========================================
# 3. VERİ TOPLAMA VE İŞLEME
# ==========================================

def get_full_text(url):
    if "t.me" in url or ".pdf" in url: return None
    try:
        downloaded = trafilatura.fetch_url(url)
        return trafilatura.extract(downloaded)[:2500] if downloaded else None
    except: return None

def fetch_news():
    print("🕵️‍♂️ KÜRESEL İSTİHBARAT AĞI VE AKADEMİK VERİLER TARANIYOR...")
    
    ai_input_data = []
    reference_html_list = []
    
    try:
        past_24h = datetime.datetime.now() - datetime.timedelta(hours=24)
        response = supabase.table("reports").select("content").gte("created_at", past_24h.isoformat()).execute()
        past_content = str(response.data)
    except: past_content = ""

    all_urls = []
    for category in RSS_SOURCES.values():
        all_urls.extend(category)
    
    counter = 1
    for url in all_urls:
        try:
            feed = feedparser.parse(url)
            if not feed.entries: continue

            for entry in feed.entries[:1]: 
                if entry.link not in past_content:
                    full = get_full_text(entry.link)
                    summary = full if full else entry.get('summary', '')[:600]
                    title = entry.title
                    source = feed.feed.get('title', 'Kaynak')
                    
                    ai_input_data.append(f"[{counter}] SOURCE: {source} | TITLE: {title} | CONTENT: {summary}")
                    
                    reference_html_list.append(
                        f"<li style='margin-bottom: 8px; border-bottom: 1px dashed #eee; padding-bottom: 5px;'>"
                        f"<b>[{counter}]</b> <a href='{entry.link}' style='color:#2980b9; text-decoration:none; font-weight:600;'>{title}</a> "
                        f"<span style='color:#7f8c8d; font-size:11px;'>— {source}</span>"
                        f"</li>"
                    )
                    
                    counter += 1
        except: continue

    return "\n\n".join(ai_input_data), "".join(reference_html_list)

# ==========================================
# 4. DOKTRİNER ANALİZ VE KAVRAM ÖNERİCİ (AI)
# ==========================================

def run_agent_workflow(current_data):
    print("🧠 STRATEJİK ANALİZ VE KAVRAM TARAMASI YAPILIYOR...")
    today = datetime.datetime.now().strftime("%d %B %Y")

    system_prompt = f"""
    Sen 'Küresel Savaş Odası'nın Baş Stratejisti ve Akademik Danışmanısın.
    GÖREVİN: İstihbaratı analiz etmek ve okuyucuya bir "Jeopolitik Ders" niteliğinde rapor sunmak.

    **ANALİZ KURALLARI:**
    1. **GELECEK ODAKLI:** Olayların *sonuçlarını* yaz. (Örn: "Bu hamle 6 ay içinde Tayvan Boğazı'nda ablukaya yol açabilir").
    2. **KÜRESEL PERSPEKTİF:** Batı ve Doğu kaynaklarını sentezle.
    3. **DOKTRİNER DİL:** Realizm, Güç Dengesi, Hibrit Savaş gibi kavramları kullan.
    4. **ATIF:** Mutlaka `` formatını kullan.

    **ÖZEL GÖREV (KAVRAM & MAKALE):**
    Raporun en sonuna, bugünkü olayları (Örn: Ambargo, Vekalet Savaşı) en iyi açıklayan bir **"Uluslararası İlişkiler Kavramı"** seç. Bu kavramı kısaca tanımla ve bu konuda okunması gereken **gerçek bir akademik makale veya kitap** öner (Yazar Adı ve Eser Adı ile).

    **RAPOR FORMATI (HTML):**
    <div style="font-family: 'Georgia', serif; color: #222; line-height: 1.6;">
        
        <h2 style="color:#c0392b; border-bottom: 2px solid #c0392b; padding-bottom: 5px;">I. KÜRESEL GÜÇ DENGESİ (ANALİZ)</h2>
        <p>(Kritik gelişmelerin stratejik analizi.)</p>

        <h2 style="color:#2980b9; border-bottom: 2px solid #2980b9; padding-bottom: 5px; margin-top:30px;">II. BÖLGESEL RİSKLER & SENARYOLAR</h2>
        <h3 style="color:#2c3e50; margin-bottom: 5px;">🌏 Asya-Pasifik & Hint Altıtası</h3>
        <p>(Çin, Hindistan, Pakistan analizi. kullan.)</p>
        <h3 style="color:#2c3e50; margin-bottom: 5px;">🌍 Avrupa & Orta Doğu Hattı</h3>
        <p>(Rusya, Ukrayna, Orta Doğu analizi. kullan.)</p>

        <div style="background-color:#f4f6f7; border: 1px solid #d5dbdb; padding: 20px; margin-top: 40px; border-radius: 5px;">
            <h3 style="color:#2c3e50; margin-top: 0; text-transform: uppercase; font-size: 16px;">🧠 GÜNÜN KAVRAMI VE OKUMA ÖNERİSİ</h3>
            <p><b>🔎 Kavram:</b> (Bugünkü olayları açıklayan kavram, örn: "Security Dilemma")</p>
            <p><b>📖 Tanım:</b> (Kavramın kısa, akademik tanımı)</p>
            <p><b>📚 Makale/Kitap Önerisi:</b> (Yazar Adı - Eser Adı. Örn: "Robert Jervis - Cooperation Under the Security Dilemma")</p>
        </div>

    </div>
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"GÜNCEL İSTİHBARAT:\n{current_data}"}
            ],
            temperature=0.5
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
    if not ALICI_LISTESI: 
        print("⚠️ Alıcı listesi boş.")
        return
    
    print(f"📧 {len(ALICI_LISTESI)} kişiye gönderiliyor...")
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    
    email_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 8px; border-top: 6px solid #2c3e50; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            
            <div style="text-align: center; margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px;">
                <h1 style="color: #2c3e50; margin: 0; font-family: 'Times New Roman', serif; letter-spacing: 1px;">JEOPOLİTİK DURUM DEĞERLENDİRMESİ</h1>
                <p style="color: #7f8c8d; font-size: 14px; margin-top: 5px;">Doktriner Analiz Birimi | Tarih: {today}</p>
                <a href="https://siyasi-istihbarat-botu.streamlit.app/" style="display: inline-block; margin-top: 10px; background-color: #34495e; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold;">
                    🚀 SAVAŞ ODASI PANELİNE GİT
                </a>
            </div>

            {report_body}

            <div style="margin-top: 50px; padding-top: 20px; border-top: 2px solid #ecf0f1;">
                <h3 style="color: #2c3e50; font-size: 16px; text-transform: uppercase;">📚 KÜRESEL İSTİHBARAT AKIŞI (DOĞRULANMIŞ)</h3>
                <p style="font-size: 11px; color: #7f8c8d; margin-bottom: 10px;">Aşağıdaki kaynaklar raporda atıf yapılan () verilerin orijinalleridir:</p>
                <ol style="font-size: 13px; color: #555; padding-left: 20px; line-height: 1.8;">
                    {references_html}
                </ol>
            </div>

            <div style="text-align: center; margin-top: 30px; font-size: 11px; color: #aaa;">
                Bu rapor, Batı ve Doğu kaynaklı açık istihbarat verilerinin (OSINT) yapay zeka ile sentezlenmesiyle oluşturulmuştur.
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
            msg['Subject'] = f"🛡️ SAVAŞ ODASI: Stratejik Analiz ({today})"
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
        print("✅ Operasyon Başarıyla Tamamlandı.")
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
                f.write(report_html + "\n\n<h3>KAYNAKÇA</h3>\n<ul>" + ref_html_list + "</ul>")
            
            subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"], capture_output=True)
            subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"], capture_output=True)
            subprocess.run(["git", "add", file_name], capture_output=True)
            subprocess.run(["git", "commit", "-m", "Otomatik Rapor"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
        except Exception as e: 
            print(f"⚠️ Arşivleme uyarısı: {e}")

        send_email(report_html, ref_html_list, audio)
    else:
        print("⚠️ Yeterli yeni veri bulunamadı.")
