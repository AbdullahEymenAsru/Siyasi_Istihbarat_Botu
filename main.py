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
# 2. İSTİHBARAT KAYNAKLARI (TAM LİSTE)
# ==========================================

RSS_SOURCES = {
    "STRATEJIK": [
        "https://foreignpolicy.com/feed/",
        "https://www.csis.org/rss/analysis",          # CSIS
        "https://www.setav.org/feed/",                # SETA
        "https://carnegieendowment.org/rss/solr/get/all",
        "https://www.understandingwar.org/feeds.xml", # ISW
        "https://warontherocks.com/feed/",
        "https://www.cfr.org/rss/newsletters/daily-brief"
    ],
    "BATI_MEDYASI": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "http://rss.cnn.com/rss/edition_world.rss",
        "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
        "https://www.voanews.com/api/z$omeovuro",
        "https://www.dw.com/xml/rss-tur-dunya",
        "https://www.france24.com/en/rss"
    ],
    "DOGU_MEDYASI": [
        "http://www.xinhuanet.com/english/rss/worldrss.xml", # Çin
        "http://www.chinadaily.com.cn/rss/world_rss.xml",
        "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", # Hindistan
        "https://www.dawn.com/feeds/home",            # Pakistan
        "https://tass.com/rss/v2.xml",                # Rusya
        "https://www.aljazeera.com/xml/rss/all.xml"   # Katar
    ],
    "TELEGRAM": [
        "https://rsshub.app/telegram/channel/geopolitics_live",
        "https://rsshub.app/telegram/channel/intelslava"
    ]
}

# ==========================================
# 3. VERİ TOPLAMA
# ==========================================

def get_full_text(url):
    if "t.me" in url or ".pdf" in url: return None
    try:
        downloaded = trafilatura.fetch_url(url)
        return trafilatura.extract(downloaded)[:2500] if downloaded else None
    except: return None

def fetch_news():
    print("🕵️‍♂️ İSTİHBARAT TOPLANIYOR...")
    ai_input_data = []
    reference_html_list = []
    
    try:
        past_24h = datetime.datetime.now() - datetime.timedelta(hours=24)
        response = supabase.table("reports").select("content").gte("created_at", past_24h.isoformat()).execute()
        past_content = str(response.data)
    except: past_content = ""

    all_urls = []
    for cat in RSS_SOURCES.values(): all_urls.extend(cat)
    
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
                    
                    # Eski tarza uygun sade referans listesi
                    reference_html_list.append(
                        f"<li><a href='{entry.link}' style='color:#0000EE; text-decoration:none;'>{source} - {title}</a></li>"
                    )
                    counter += 1
        except: continue

    return "\n\n".join(ai_input_data), "".join(reference_html_list)

# ==========================================
# 4. ANALİZ (ESKİ FORMAT MODU)
# ==========================================

def run_agent_workflow(current_data):
    print("🧠 ESKİ FORMATTA ANALİZ DERLENİYOR...")
    
    system_prompt = f"""
    Sen 'Küresel Savaş Odası'nın İstihbarat Analistisin.
    GÖREVİN: Aşağıdaki ham verileri kullanarak, **eski ve net formatta** bir bülten hazırlamak.

    **FORMAT KURALLARI (HTML KULLAN):**
    
    1. **🚨 KIRMIZI ALARM (Sıcak Çatışma & Riskler):**
       - Sadece en acil, savaş veya çatışma riski taşıyan 1-2 olayı anlat.
       - Paragraf şeklinde yaz. kullan.

    2. **🌍 KÜRESEL UFUK TURU:**
       - Bölgelere ayır: **Orta Doğu:** ..., **Asya-Pasifik:** ..., **Avrupa:** ...
       - Her bölge için kısa ve öz haber özetleri geç. kullan.

    3. **🧠 THINK-TANK KÖŞESİ (Derin Okuma):**
       - Foreign Policy, War on the Rocks, SETA gibi kaynaklardan gelen teorik veya derin analizleri buraya al.
       - Bu bölümde ayrıca, olayları açıklayan bir **"Kavram"** (Örn: Security Dilemma) ve **"Makale Önerisi"** de sun.

    4. **🔮 GELECEK SENARYOLARI & POLİTİKA ÖNERİSİ:**
       - Önümüzdeki 1 ay içinde ne bekleniyor?
       - Türkiye ne yapmalı? (Kısa ve net tavsiye).

    **STİL:**
    - Font: Georgia veya Arial.
    - Başlıklar renkli ve büyük olsun.
    - Dil: Akıcı, ciddi ama anlaşılır (News-Digest tarzı).
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"VERİLER:\n{current_data}"}
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
    
    # ESKİ FORMAT E-POSTA ŞABLONU
    email_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #ffffff; padding: 20px; color: #333;">
        <div style="max-width: 800px; margin: auto;">
            
            <div style="border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #000;">KÜRESEL SAVAŞ ODASI</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px; color: #666;">Günlük İstihbarat Özeti | {today}</p>
            </div>

            <div style="font-family: 'Georgia', serif; font-size: 16px; line-height: 1.6;">
                {report_body}
            </div>

            <div style="margin-top: 40px; border-top: 1px solid #ccc; padding-top: 20px;">
                <h4 style="margin-top: 0;">Referanslar:</h4>
                <ul style="font-size: 13px; color: #555; padding-left: 20px;">
                    {references_html}
                </ul>
            </div>

            <div style="text-align: center; margin-top: 30px;">
                <a href="https://siyasi-istihbarat-botu.streamlit.app/" style="background-color: #000; color: #fff; padding: 10px 15px; text-decoration: none; font-size: 12px; font-weight: bold; border-radius: 3px;">CANLI PANEL</a>
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
            msg['Subject'] = f"KIRMIZI ALARM: Küresel Durum - {today}"
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
                f.write(report_html + "\n\n<h3>Referanslar</h3>\n<ul>" + ref_html_list + "</ul>")
            
            subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"], capture_output=True)
            subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"], capture_output=True)
            subprocess.run(["git", "add", file_name], capture_output=True)
            subprocess.run(["git", "commit", "-m", "Rapor"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
        except: pass

        send_email(report_html, ref_html_list, audio)
    else:
        print("⚠️ Veri yok.")
