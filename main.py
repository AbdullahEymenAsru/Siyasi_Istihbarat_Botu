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
# 1. AYARLAR & API ROTASYON SİSTEMİ
# ==========================================

# Sistem iki farklı hesabı sırayla dener. Biri biterse diğeri devreye girer.
GROQ_KEYS = [
    os.environ.get("GROQ_API_KEY"),   # Birinci hesap (100k Token)
    os.environ.get("GROQ_API_KEY_2")  # İkinci hesap (100k Token)
]

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Client başlatma (ilk anahtar ile varsayılan olarak)
client = Groq(api_key=GROQ_KEYS[0])
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SES_MODELI = "tr-TR-AhmetNeural"

# --- KRİTİK DÜZELTME: SADECE 'TRUE' OLANLARI ÇEK ---
def get_email_list():
    try:
        # Sadece 'aktif' sütunu TRUE olanları filtrele. 
        # FALSE veya NULL olanlar bu filtreye takılır ve listeye alınmaz.
        response = supabase.table("abone_listesi").select("email").eq("aktif", True).execute()
        return [row['email'] for row in response.data] if response.data else []
    except Exception as e:
        print(f"⚠️ Veritabanı Hatası: {e}")
        return []

ALICI_LISTESI = get_email_list()

# ==========================================
# 2. GENİŞLETİLMİŞ KÜRESEL İSTİHBARAT AĞI
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
    "BATI": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "http://rss.cnn.com/rss/edition_world.rss",
        "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
        "https://www.voanews.com/api/z$omeovuro",
        "https://www.france24.com/en/rss"
    ],
    "DOGU": [
        "http://www.xinhuanet.com/english/rss/worldrss.xml", # Çin
        "http://www.chinadaily.com.cn/rss/world_rss.xml",
        "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", # Hindistan
        "https://www.dawn.com/feeds/home",            # Pakistan
        "https://tass.com/rss/v2.xml",                # Rusya
        "https://www.aljazeera.com/xml/rss/all.xml"   # Orta Doğu
    ],
    "TELEGRAM": [
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
    print("🕵️‍♂️ KÜRESEL İSTİHBARAT AĞI TARANIYOR (12 SAATLİK AGRESİF HAFIZA)...")
    
    ai_input_data = []
    reference_html_list = []
    
    # 12 SAATLİK TEKRAR KONTROLÜ (Daha sıkı takip için süre kısaltıldı)
    try:
        past_12h = datetime.datetime.now() - datetime.timedelta(hours=12)
        response = supabase.table("reports").select("content").gte("created_at", past_12h.isoformat()).execute()
        past_content = str(response.data)
    except: past_content = ""

    all_urls = []
    for cat in RSS_SOURCES.values(): all_urls.extend(cat)
    
    counter = 1
    # Her kaynaktan en taze 3 haberi al (Daha fazla veri)
    for url in all_urls:
        try:
            feed = feedparser.parse(url)
            if not feed.entries: continue

            for entry in feed.entries[:3]: 
                # Link veritabanında var mı diye kontrol et
                if entry.link not in past_content:
                    full = get_full_text(entry.link)
                    summary = full if full else entry.get('summary', '')[:600]
                    title = entry.title
                    source = feed.feed.get('title', 'Kaynak')
                    
                    # AI Verisi
                    ai_input_data.append(f"[{counter}] SOURCE: {source} | TITLE: {title} | CONTENT: {summary}")
                    
                    # E-posta Kaynakça Listesi
                    reference_html_list.append(
                        f"<li style='margin-bottom:6px;'><b>[{counter}]</b> <a href='{entry.link}' style='color:#0000EE; text-decoration:none;'>{source} - {title}</a></li>"
                    )
                    counter += 1
        except: continue

    return "\n\n".join(ai_input_data), "".join(reference_html_list)

# ==========================================
# 4. ANALİZ (ROTASYONEL DOKTRİNER MOTOR)
# ==========================================

def run_agent_workflow(current_data):
    print("🧠 STRATEJİK ANALİZ VE TASARIM OLUŞTURULUYOR (ROTASYON AKTİF)...")
    
    system_prompt = f"""
    Sen 'Küresel Savaş Odası'nın Baş Stratejistisin.
    GÖREVİN: İstihbarat verilerini analiz etmek ve **DOKTRİNER DİLLE**, aşağıdaki **ESKİ VE NET FORMATTA** raporlamak.

    **GENEL KURALLAR:**
    1. **GELECEK ODAKLI:** "Rusya saldırdı" deme. "Bu saldırı tahıl krizini tetikleyerek Afrika'da istikrarsızlık yaratacak" de.
    2. **ATIF:** Bilgi verdiğin her yerde `` kullan.
    3. **DİL:** Ciddi, akademik ve sürükleyici.

    **ZORUNLU HTML FORMATI (BUNU KULLAN):**
    
    <div style="background-color: #3e0e0e; color: #fff; padding: 20px; border-left: 6px solid #e74c3c; margin-bottom: 25px; border-radius: 4px;">
        <h2 style="color: #ff6b6b; margin-top: 0; font-family: 'Arial Black', sans-serif;">🚨 KIRMIZI ALARM (Sıcak Çatışma & Riskler)</h2>
        <p style="font-size: 16px; line-height: 1.6;">
            (En acil çatışma haberini ve gelecek risklerini buraya yaz.)
        </p>
    </div>

    <div style="margin-bottom: 30px; border-bottom: 2px solid #ccc; padding-bottom: 20px;">
        <h2 style="color: #2980b9; font-family: 'Georgia', serif;">🌍 KÜRESEL UFUK TURU</h2>
        <p><b>📍 Asya-Pasifik & Doğu:</b> (Çin, Hindistan, Rusya hamleleri.)</p>
        <p><b>📍 Avrupa & Batı Bloku:</b> (ABD, AB, Ukrayna gelişmeleri.)</p>
        <p><b>📍 Orta Doğu Hattı:</b> (İsrail, Filistin, Türkiye ekseni.)</p>
    </div>

    <div style="background-color: #f0f3f4; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
        <h2 style="color: #8e44ad; margin-top: 0; font-family: 'Georgia', serif;">🧠 THINK-TANK KÖŞESİ (Derin Okuma)</h2>
        <p style="color: #333; line-height: 1.6;">
            (Akademik ve derin analizler.)
        </p>
    </div>

    <div style="border-left: 5px solid #27ae60; padding-left: 15px; margin-bottom: 30px;">
        <h2 style="color: #27ae60; margin-top: 0; font-family: 'Georgia', serif;">🔮 GELECEK SENARYOLARI & POLİTİKA</h2>
        <p style="color: #222; line-height: 1.6;">
            (Önümüzdeki 1 ay için öngörün ve Türkiye'ye tavsiyen.)
        </p>
    </div>

    <div style="background-color: #fff8e1; border: 1px solid #ffecb3; padding: 15px; border-radius: 5px;">
        <h3 style="color: #d35400; margin-top: 0;">🎓 GÜNÜN AKADEMİK KAVRAMI</h3>
        <p><b>Kavram:</b> (Örn: Security Dilemma)<br>
        <b>Tanım:</b> (Kısa akademik tanım)<br>
        <b>📖 Kitap/Makale Önerisi:</b> (Yazar - Eser Adı)</p>
    </div>
    """

    # --- ROTASYON MANTIĞI: 1. KEY BİTERSE 2. KEY'E GEÇER ---
    for i, key in enumerate(GROQ_KEYS):
        if not key: continue
        try:
            temp_client = Groq(api_key=key)
            completion = temp_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"İSTİHBARAT VERİLERİ:\n{current_data}"}
                ],
                temperature=0.4
            )
            return completion.choices[0].message.content
        except Exception as e:
            if "429" in str(e): # Kota aşımı hatası tespit edilirse
                print(f"⚠️ {i+1}. API Hattı Dolu, Yedek Hatta Geçiliyor...")
                continue
            return f"<p>AI Analiz Hatası: {e}</p>"
    
    return "<p>❌ Tüm API kotaları tükendi. Operasyon durduruldu.</p>"

# ==========================================
# 5. SES & ARŞİV & DAĞITIM
# ==========================================

async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await asyncio.wait_for(communicate.save(output_file), timeout=60)

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
        print("⚠️ Aktif alıcı bulunamadı (Tüm kullanıcılar FALSE veya NULL olabilir).")
        return
    
    print(f"📧 {len(ALICI_LISTESI)} aktif aboneye gönderiliyor...")
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    
    # TASARIM: Sizin İstediğiniz "Eski Tarz" (Görsel Odaklı)
    email_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #ffffff; padding: 20px; color: #333;">
        <div style="max-width: 800px; margin: auto;">
            
            <div style="text-align: center; border-bottom: 3px solid #000; padding-bottom: 15px; margin-bottom: 30px;">
                <h1 style="margin: 0; color: #000; font-family: 'Times New Roman', serif; text-transform: uppercase;">KÜRESEL SAVAŞ ODASI</h1>
                <p style="margin: 5px 0 0 0; color: #555; font-style: italic;">Stratejik İstihbarat Bülteni | {today}</p>
                <br>
                <a href="https://siyasi-istihbarat-botu.streamlit.app/" style="background-color: #000; color: #fff; padding: 8px 15px; text-decoration: none; font-size: 12px; font-weight: bold;">CANLI PANEL</a>
            </div>

            {report_body}

            <div style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #ccc;">
                <h3 style="color: #333; font-family: 'Georgia', serif;">📚 DOĞRULANMIŞ KAYNAKÇA & REFERANSLAR</h3>
                <ul style="font-size: 12px; color: #555; padding-left: 20px; line-height: 1.8;">
                    {references_html}
                </ul>
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
            msg['Subject'] = f"KIRMIZI ALARM: Stratejik Durum - {today}"
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
# 6. ÇALIŞTIRMA (MAIN BLOCK)
# ==========================================

if __name__ == "__main__":
    news_data, ref_html_list = fetch_news()
    
    if news_data:
        report_html = run_agent_workflow(news_data)
        audio = create_audio_summary(report_html)
        
        try:
            # Raporun veritabanına kaydı
            supabase.table("reports").insert({"content": report_html}).execute()
            
            # --- KRİTİK GÜNCELLEME: STANDART DOSYA İSMİ FORMATI ---
            # Dosya ismi artık her zaman: RAPOR_YYYY-MM-DD_HH-mm.md formatında olacak.
            file_name = f"ARSIV/RAPOR_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')}.md"
            
            if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(report_html + "\n\n<h3>REFERANSLAR</h3>\n<ul>" + ref_html_list + "</ul>")
            
            # Git işlemleri
            subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"], capture_output=True)
            subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"], capture_output=True)
            subprocess.run(["git", "add", "ARSIV/*.md"], capture_output=True) # Tüm arşiv klasörünü ekle
            subprocess.run(["git", "commit", "-m", f"Otomatik Rapor: {datetime.datetime.now().strftime('%d.%m.%Y')}"], capture_output=True)
            subprocess.run(["git", "push"], capture_output=True)
        except Exception as e:
            print(f"⚠️ Arşivleme/Git Hatası: {e}")

        # E-posta Dağıtımı
        send_email(report_html, ref_html_list, audio)
    else:
        print("⚠️ Yeterli yeni veri bulunamadı.")
