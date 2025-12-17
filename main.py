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
# 2. İSTİHBARAT KAYNAKLARI
# ==========================================

RSS_SOURCES = {
    "STRATEJIK": [
        "https://foreignpolicy.com/feed/",
        "https://www.understandingwar.org/feeds.xml", 
        "https://warontherocks.com/feed/",
        "https://www.cfr.org/rss/newsletters/daily-brief"
    ],
    "HABER": [
        "https://www.aa.com.tr/tr/rss/default?cat=guncel",
        "https://www.trthaber.com/dunya_articles.rss",
        "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
        "https://www.aljazeera.com/xml/rss/all.xml"
    ],
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
        return trafilatura.extract(downloaded)[:2000] if downloaded else None
    except: return None

def fetch_news():
    print("🕵️‍♂️ İSTİHBARAT TOPLANIYOR...")
    
    # AI'ya verilecek ham veri
    ai_input_data = []
    
    # E-postanın altına eklenecek düzenli kaynakça listesi (HTML)
    reference_html_list = []
    
    # Tekrar kontrolü için geçmişi çek
    try:
        past_24h = datetime.datetime.now() - datetime.timedelta(hours=24)
        response = supabase.table("reports").select("content").gte("created_at", past_24h.isoformat()).execute()
        past_content = str(response.data)
    except: past_content = ""

    all_urls = RSS_SOURCES["STRATEJIK"] + RSS_SOURCES["HABER"] + RSS_SOURCES["TELEGRAM"]
    
    counter = 1
    for url in all_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]: # Her kaynaktan en yeni 2 haber
                if entry.link not in past_content:
                    full = get_full_text(entry.link)
                    summary = full if full else entry.get('summary', '')[:500]
                    title = entry.title
                    source = feed.feed.get('title', 'Kaynak')
                    
                    # AI'ya gidecek format (Numaralı)
                    ai_input_data.append(f"[{counter}] SOURCE: {source} | TITLE: {title} | CONTENT: {summary}")
                    
                    # E-postaya gidecek format (Numaralı Liste)
                    reference_html_list.append(
                        f"<li style='margin-bottom: 5px;'><b>[{counter}]</b> <a href='{entry.link}' style='color:#2980b9; text-decoration:none;'>{title}</a> <span style='color:#7f8c8d; font-size:11px;'>— {source}</span></li>"
                    )
                    
                    counter += 1
        except: continue

    return "\n\n".join(ai_input_data), "".join(reference_html_list)

# ==========================================
# 4. DOKTRİNER VE FÜTÜRİSTİK ANALİZ (AI AGENT)
# ==========================================

def run_agent_workflow(current_data):
    print("🧠 GELECEK SENARYOLARI OLUŞTURULUYOR...")
    today = datetime.datetime.now().strftime("%d %B %Y")

    system_prompt = f"""
    Sen 'Küresel Savaş Odası'nın Baş Fütüristi ve Stratejistisin.
    GÖREVİN: Güncel istihbaratı okuyarak, bu olayların **GELECEKTEKİ ETKİLERİNİ** analiz etmek.

    **KESİN KURALLAR:**
    1. **ÖZET ÇIKARMA:** Kullanıcı olayları zaten biliyor. "Rusya Ukrayna'ya saldırdı" deme.
    2. **GELECEĞİ YAZ:** "Bu saldırı, 3 ay içinde tahıl koridorunu tıkayacak ve Kuzey Afrika'da gıda ayaklanmalarını tetikleyecek" gibi nedensellik bağları kur.
    3. **DOKTRİNER DİL:** Realizm, Güç Dengesi, Abundance Hareketi, Genesis Misyonu gibi kavramları analizlerine yedir.
    4. **NUMARALI ATIF:** Analizinde dayandığın bilgiye `` şeklinde atıf yap. (X, sana verilen verideki numaradır).

    **RAPOR FORMATI (HTML):**
    <div style="font-family: 'Georgia', serif; color: #222; line-height: 1.6;">
        
        <h2 style="color:#c0392b; border-bottom: 2px solid #c0392b; padding-bottom: 5px;">I. STRATEJİK KIRILMA VE GELECEK (YÖNETİCİ ÖZETİ)</h2>
        <p>(En kritik 3 olayın birleşimiyle oluşan "Büyük Resim" ve 6 aylık projeksiyon.)</p>

        <h2 style="color:#2980b9; border-bottom: 2px solid #2980b9; padding-bottom: 5px; margin-top:30px;">II. CEPHELER VE OLASI SENARYOLAR</h2>
        
        <h3 style="color:#2c3e50; margin-bottom: 5px;">🔮 Senaryo A: Ekonomik ve Teknolojik Savaş</h3>
        <p>(Genesis Misyonu, Çip Savaşları veya Enerji üzerinden analiz. Mutlaka kullan.)</p>

        <h3 style="color:#2c3e50; margin-bottom: 5px;">🔥 Senaryo B: Asimetrik ve Vekalet Savaşları</h3>
        <p>(Sahadaki çatışmaların sıçrama riskleri. Mutlaka kullan.)</p>

        <div style="background-color:#f8f9fa; border-left: 4px solid #27ae60; padding: 15px; margin-top: 25px; font-style: italic;">
            <b>💡 Doktriner Not:</b> (Realizm veya Liberalizm teorisi üzerinden kısa bir stratejik tavsiye.)
        </div>
    </div>
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"GÜNCEL NUMARALI İSTİHBARAT:\n{current_data}"}
            ],
            temperature=0.5 # Biraz daha yaratıcı olması için sıcaklığı artırdık
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
    
    # Nihai E-Posta Şablonu (Haritasız & Düzenli)
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
                <h3 style="color: #2c3e50; font-size: 16px; text-transform: uppercase;">📚 DOĞRULANMIŞ KAYNAKÇA & İSTİHBARAT AKIŞI</h3>
                <ol style="font-size: 13px; color: #555; padding-left: 20px; line-height: 1.8;">
                    {references_html}
                </ol>
            </div>

            <div style="text-align: center; margin-top: 30px; font-size: 11px; color: #aaa;">
                Bu rapor, yapay zeka destekli açık kaynak istihbarat (OSINT) analizidir.
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
            msg['Subject'] = f"🛡️ SAVAŞ ODASI: Gelecek Projeksiyonu ({today})"
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
    # Haberleri ve formatlanmış kaynakça listesini çek
    news_data, ref_html_list = fetch_news()
    
    if news_data:
        # Analiz yap
        report_html = run_agent_workflow(news_data)
        # Seslendir
        audio = create_audio_summary(report_html)
        
        # Arşivle (Git & Supabase)
        try:
            supabase.table("reports").insert({"content": report_html}).execute()
            
            file_name = f"ARSIV/Rapor_{datetime.datetime.now().strftime('%Y-%m-%d')}.md"
            if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
            
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(report_html + "\n\n<h3>KAYNAKÇA</h3>\n<ul>" + ref_html_list + "</ul>")
            
            # Git işlemleri (Opsiyonel, hata verirse devam et)
            subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"], capture_output=True)
            subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"], capture_output=True)
            subprocess.run(["git", "add", file_name], capture_output=True)
            subprocess.run(["git", "commit", "-m", "Otomatik Rapor"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
        except Exception as e: 
            print(f"⚠️ Arşivleme uyarısı: {e}")

        # Gönder
        send_email(report_html, ref_html_list, audio)
    else:
        print("⚠️ Yeterli yeni veri bulunamadı.")
