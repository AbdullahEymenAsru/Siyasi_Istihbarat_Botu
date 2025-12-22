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

# --- KRİTİK GÜNCELLEME: BREVO PROFESYONEL SMTP HATTI ---
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER")   # Brevo Login (9e9... ile başlayan)
SMTP_PASS = os.environ.get("SMTP_PASS")   # Brevo Master Password (Key)
SENDER_MAIL = os.environ.get("SENDER_MAIL") # Görünmesini istediğiniz adres (Örn: eymenakademi@gmail.com)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# GITHUB TOKEN (PUSH İŞLEMİ İÇİN KRİTİK)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

# Client başlatma (ilk anahtar ile varsayılan olarak)
client = Groq(api_key=GROQ_KEYS[0])
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SES_MODELI = "tr-TR-AhmetNeural"

# --- GELİŞMİŞ ALICI LİSTESİ (DİL TERCİHLİ) ---
def get_subscriber_data():
    try:
        # Sadece 'aktif' sütunu TRUE olanları filtrele ve dil tercihini de çek.
        # Bu veri token tasarrufu mantığı için kritik.
        response = supabase.table("abone_listesi").select("email, aktif_dil").eq("aktif", True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"⚠️ Veritabanı Hatası: {e}")
        return []

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
    "DUNYA_SAHASI": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://tass.com/rss/v2.xml",
        "https://www.france24.com/en/rss",
        "https://www.scmp.com/rss/91/feed" # Asya/Çin perspektifi için eklendi
    ],
    "TEKNOLOJI_VE_ENERJI": [
        "https://www.defensenews.com/arc/outboundfeeds/rss/",
        "https://www.oilprice.com/rss/main",
        "https://techcrunch.com/feed/",
        "https://thehackernews.com/rss.xml"
    ]
}

# ==========================================
# 3. VERİ TOPLAMA VE FİLTRELEME (12 SAAT KONTROLÜ)
# ==========================================

def get_full_text(url):
    if "t.me" in url or ".pdf" in url: return None
    try:
        downloaded = trafilatura.fetch_url(url)
        # Token tasarrufu için karakter limiti 1200'e çekildi
        return trafilatura.extract(downloaded)[:1200] if downloaded else None
    except: return None

def fetch_news():
    print("🕵️‍♂️ KÜRESEL İSTİHBARAT AĞI TARANIYOR (ZAMAN VE İÇERİK FİLTRESİ AKTİF)...")
    
    ai_input_data = []
    reference_html_list = []
    
    # 12 SAATLİK TEKRAR KONTROLÜ
    try:
        past_12h = datetime.datetime.now() - datetime.timedelta(hours=12)
        response = supabase.table("reports").select("content").gte("created_at", past_12h.isoformat()).execute()
        past_content = str(response.data)
    except: past_content = ""

    all_urls = []
    for cat in RSS_SOURCES.values(): all_urls.extend(cat)
    
    counter = 1
    # Her kaynaktan en taze haberi al
    for url in all_urls:
        try:
            feed = feedparser.parse(url)
            if not feed.entries: continue

            # KOMUTANIN EMRİ: SADECE EN TAZE 2 HABER
            for entry in feed.entries[:2]: 
                # 1. TARİH KONTROLÜ (BAYAT HABER ENGELLEYİCİ)
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    dt_pub = datetime.datetime(*entry.published_parsed[:6])
                    if (datetime.datetime.now() - dt_pub).days > 2:
                        continue # Haber çok eski, atla.

                # 2. İÇERİK TEKRAR KONTROLÜ
                if entry.link in past_content or entry.title[:30] in past_content:
                    continue

                full = get_full_text(entry.link)
                summary = full if full else entry.get('summary', '')[:400]
                title = entry.title
                source = feed.feed.get('title', 'Kaynak')
                
                # AI Verisi
                ai_input_data.append(f"[ID:{counter}] KAYNAK: {source} | BAŞLIK: {title} | İÇERİK: {summary}")
                
                # E-posta Kaynakça Listesi
                reference_html_list.append(
                    f"<li style='margin-bottom:6px;'><b>[{counter}]</b> <a href='{entry.link}' style='color:#0000EE; text-decoration:none;'>{source} - {title}</a></li>"
                )
                counter += 1
        except: continue

    # Veriyi liste olarak döndür, referansları string olarak döndür
    return ai_input_data, "".join(reference_html_list)

# ==========================================
# 4. ÇOK DİLLİ ANALİZ (CHUNK-BASED & ROTATIONAL MOTOR)
# ==========================================

def run_agent_workflow(ai_input_list, target_lang="Türkçe"):
    if not ai_input_list:
        return None # Haber yoksa işlem yapma

    print(f"🧠 ANALİZ BAŞLADI (Hedef Dil: {target_lang})...")
    
    # 1. ADIM: Haberleri 6'şarlı gruplar halinde parçalara böl
    chunks = [ai_input_list[i:i + 6] for i in range(0, len(ai_input_list), 6)]
    partial_analyses = []

    # DİLE DUYARLI PROMPT
    if target_lang == "Türkçe":
        lang_instruction = "Lütfen tüm raporu profesyonel Türkçe ile hazırla."
    else:
        lang_instruction = "Please prepare the entire report in professional English."

    # DEMİR YUMRUK PROMPT (DİL VE İÇERİK KONTROLÜ)
    system_prompt = f"""
    Sen bir Askeri İstihbarat Analistisin.
    GÖREVİN: Ham verileri alıp, varsa YABANCI DİLLERİ temizleyerek profesyonel rapor oluşturmak.
    
    KURALLAR:
    1. DİL: {lang_instruction}
    2. TERMİNOLOJİ: Kritik kavramların İngilizcesini parantez içinde ver.
    3. YORUM YOK, OLGU VAR: Analist notunu 15 kelimeyle sınırla.
    4. KAVRAM SEÇİMİ: Basit klişeleri YASAKLA. Daha sofistike kavramlar kullan.
    5. Her haberin başına [ID:X] etiketini koru.
    """

    # 2. ADIM: Her parçayı ayrı ayrı analiz et
    for chunk in chunks:
        chunk_text = "\n\n".join(chunk)
        success = False
        
        # Rotasyon denemesi
        for i, key in enumerate(GROQ_KEYS):
            if not key or success: continue
            try:
                temp_client = Groq(api_key=key)
                completion = temp_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Şu verileri TEMİZLE, ÇEVİR ve ÖZETLE:\n{chunk_text}"}
                    ],
                    temperature=0.2 
                )
                partial_analyses.append(completion.choices[0].message.content)
                success = True
            except Exception as e:
                print(f"⚠️ {i+1}. Anahtar hatası, rotasyon deneniyor... {e}")
                continue
    
    # 3. ADIM: Final Raporu Oluştur
    final_input = "\n\n".join(partial_analyses)
    
    if target_lang == "Türkçe":
        final_prompt = """
        Aşağıdaki analiz notlarını birleştirerek profesyonel bir SAHA RAPORU oluştur.

        **ZORUNLU HTML FORMATI:**
        <div style="background-color: #2c3e50; color: #ecf0f1; padding: 20px; border-left: 6px solid #e74c3c; margin-bottom: 25px; border-radius: 4px;">
            <h2 style="color: #e74c3c; margin-top: 0; font-family: 'Arial Black', sans-serif;">🚨 SICAK GELİŞMELER (Flashpoint)</h2>
            <p style="font-size: 16px; line-height: 1.6;">(En kritik 2-3 olayı [ID:X] ile anlat.)</p>
        </div>
        
        <div style="margin-bottom: 30px; border-bottom: 2px solid #bdc3c7; padding-bottom: 20px;">
            <h2 style="color: #2980b9; font-family: 'Georgia', serif;">🌐 KÜRESEL SAHA GÖZLEMİ</h2>
            <p><b>📍 Asya & Pasifik:</b> ...</p>
            <p><b>📍 Avrupa & Batı:</b> ...</p>
            <p><b>📍 Küresel Güney & Orta Doğu:</b> ...</p>
        </div>
        
        <div style="background-color: #f4f6f7; padding: 20px; border-radius: 8px; margin-bottom: 30px; border: 1px solid #d5dbdb;">
            <h2 style="color: #16a085; margin-top: 0; font-family: 'Georgia', serif;">⚡ TEKNOLOJİ, ENERJİ VE SİBER SAVAŞ</h2>
            <p style="color: #2c3e50; line-height: 1.6;">...</p>
        </div>

        <div style="background-color: #fff8e1; border: 1px solid #ffecb3; padding: 15px; border-radius: 5px;">
            <h3 style="color: #d35400; margin-top: 0;">🎓 GÜNÜN AKADEMİK KAVRAMI</h3>
            <p><b>Kavram:</b> ... | <b>Tanım:</b> ...</p>
        </div>
        """
    else:
        final_prompt = """
        Combine the notes below into a professional FIELD REPORT.

        **MANDATORY HTML FORMAT:**
        <div style="background-color: #2c3e50; color: #ecf0f1; padding: 20px; border-left: 6px solid #e74c3c; margin-bottom: 25px; border-radius: 4px;">
            <h2 style="color: #e74c3c; margin-top: 0; font-family: 'Arial Black', sans-serif;">🚨 FLASHPOINTS</h2>
            <p style="font-size: 16px; line-height: 1.6;">(Describe top 2-3 events using [ID:X].)</p>
        </div>
        
        <div style="margin-bottom: 30px; border-bottom: 2px solid #bdc3c7; padding-bottom: 20px;">
            <h2 style="color: #2980b9; font-family: 'Georgia', serif;">🌐 GLOBAL FIELD OBSERVATIONS</h2>
            <p><b>📍 Asia & Pacific:</b> ...</p>
            <p><b>📍 Europe & West:</b> ...</p>
            <p><b>📍 Global South & Middle East:</b> ...</p>
        </div>
        
        <div style="background-color: #f4f6f7; padding: 20px; border-radius: 8px; margin-bottom: 30px; border: 1px solid #d5dbdb;">
            <h2 style="color: #16a085; margin-top: 0; font-family: 'Georgia', serif;">⚡ TECH, ENERGY & CYBER WARFARE</h2>
            <p style="color: #2c3e50; line-height: 1.6;">...</p>
        </div>

        <div style="background-color: #fff8e1; border: 1px solid #ffecb3; padding: 15px; border-radius: 5px;">
            <h3 style="color: #d35400; margin-top: 0;">🎓 ACADEMIC CONCEPT OF THE DAY</h3>
            <p><b>Concept:</b> ... | <b>Definition:</b> ...</p>
        </div>
        """

    for i, key in enumerate(GROQ_KEYS):
        try:
            temp_client = Groq(api_key=key)
            final_report = temp_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{final_prompt}\n\nVERİLER:\n{final_input}"}
                ],
                temperature=0.4
            )
            return final_report.choices[0].message.content
        except Exception as e:
            if "429" in str(e): continue
            return f"<p>Final Rapor Hatası: {e}</p>"
    
    return "<p>❌ Kritik Hata: Rapor oluşturulamadı (Tüm API'ler dolu).</p>"

# ==========================================
# 5. SES & ARŞİV & DAĞITIM
# ==========================================

async def generate_voice(text, output_file):
    # HTML taglerini temizle
    clean = re.sub('<[^<]+?>', '', text)[:1500]
    communicate = edge_tts.Communicate(clean, SES_MODELI)
    await asyncio.wait_for(communicate.save(output_file), timeout=60)

def create_audio_summary(report_html):
    print("🎙️ Sesli özet hazırlanıyor...")
    filename = "Gunluk_Ozet.mp3"
    try:
        asyncio.run(generate_voice(report_html, filename))
        return filename
    except: return None

def send_custom_email(report_body, references_html, audio_file, email, lang="Türkçe"):
    print(f"📧 {email} adresine ({lang}) Brevo Kuryesi ile gönderiliyor...")
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    
    # --- STRATEJİK İSİMLENDİRME ---
    sender_name = "Savaş Odası HQ" if lang == "Türkçe" else "War Room Headquarters"
    subject = f"🛡️ [SAVAŞ ODASI] Stratejik İstihbarat Akışı | {today}" if lang == "Türkçe" else f"🛡️ [WAR ROOM] Strategic Intelligence Brief | {today}"
    
    panel_text = "📡 CANLI STRATEJİK PANELİ AÇ" if lang == "Türkçe" else "📡 OPEN LIVE STRATEGIC PANEL"
    source_text = "📚 DOĞRULANMIŞ KAYNAKLAR" if lang == "Türkçe" else "📚 VERIFIED INTELLIGENCE SOURCES"
    
    email_html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; color: #333; background-color: #f9f9f9;">
        <div style="max-width: 850px; margin: auto; background: white; border: 1px solid #ddd; padding: 25px; box-shadow: 0 4px 8px rgba(0,0,0,0.05);">
            
            <div style="text-align: center; margin-bottom: 25px;">
                <a href="https://siyasi-istihbarat-botu.streamlit.app/" 
                   style="background-color: #cc0000; color: #ffffff; padding: 12px 25px; text-decoration: none; font-weight: bold; border-radius: 5px; display: inline-block;">
                   {panel_text}
                </a>
            </div>

            <div style="text-align: center; border-bottom: 3px solid #2c3e50; padding-bottom: 15px; margin-bottom: 25px;">
                <h1 style="color: #2c3e50; margin: 0; font-size: 24px;">KÜRESEL SAVAŞ ODASI</h1>
                <p style="color: #7f8c8d; font-style: italic; margin-top: 5px;">{today}</p>
            </div>

            <div style="line-height: 1.7; font-size: 15px;">
                {report_body}
            </div>

            <div style="margin-top: 40px; background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db;">
                <h3 style="color: #2c3e50; margin-top: 0; font-size: 16px;">{source_text}</h3>
                <ul style="font-size: 12px; color: #34495e; padding-left: 20px;">{references_html}</ul>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        # --- KRİTİK GÜNCELLEME: BREVO BAĞLANTISI (KESİN ÇÖZÜM) ---
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Güvenli bağlantıyı başlat
        server.login(SMTP_USER, SMTP_PASS) # Brevo kimlik doğrulaması

        msg = MIMEMultipart()
        # Profesyonel Gönderici Görünümü (Maskelenmiş)
        msg['From'] = f"{sender_name} <{SENDER_MAIL}>"
        msg['To'] = email
        msg['Subject'] = subject
        msg['Reply-To'] = SENDER_MAIL # Yanıtlar size döner

        msg.attach(MIMEText(email_html, 'html'))

        if audio_file and os.path.exists(audio_file):
            with open(audio_file, "rb") as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{audio_file}"')
                msg.attach(part)

        # SMTP_USER (Brevo Hesabı) ile sunucuya bağlanır ama SENDER_MAIL (Sizin adresiniz) başlıkta görünür
        server.sendmail(SMTP_USER, email, msg.as_string())
        server.quit()
        print(f"✅ Brevo Kuryesi ile Başarılı: {email}")
    except Exception as e:
        print(f"❌ Mail Dağıtım Hatası ({email}): {e}")

# ==========================================
# 6. ÇALIŞTIRMA (MAIN BLOCK)
# ==========================================

if __name__ == "__main__":
    news_list, ref_html = fetch_news()
    subscribers = get_subscriber_data() # Tüm abone verilerini (dil dahil) çek
    
    if news_list and subscribers:
        print("✅ Yeni istihbarat işleniyor...")
        
        # --- TOKEN TASARRUFU & AKILLI ÜRETİM ---
        # Abone listesindeki dilleri kontrol et.
        needed_langs = set(sub.get('aktif_dil', 'Türkçe') for sub in subscribers)
        reports = {}

        for lang in needed_langs:
            reports[lang] = run_agent_workflow(news_list, lang)

        # Varsayılan Raporu (Türkçe) Arşivle ve Seslendir
        main_report = reports.get('Türkçe') or list(reports.values())[0]
        
        audio = create_audio_summary(main_report)
        
        # --- ENTEGRE KAYIT SİSTEMİ (SUPABASE + GITHUB) ---
        try:
            # 1. Supabase'e Kayıt (Dashboard için kritik)
            supabase.table("reports").insert({"content": main_report}).execute()
            print("✅ Rapor Supabase'e işlendi.")
            
            # 2. GitHub Arşivleme (GÜVENLİ PUSH SİSTEMİ)
            now = datetime.datetime.now()
            file_name = f"ARSIV/RAPOR_{now.strftime('%Y-%m-%d_%H-%M')}.md"
            
            if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
            
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(main_report + "\n\n<h3>REFERANSLAR</h3>\n<ul>" + ref_html + "</ul>")
            
            # Git işlemleri ile depoya geri yükle (TOKEN İLE GÜVENLİ BAĞLANTI)
            if GITHUB_TOKEN and GITHUB_REPOSITORY:
                repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPOSITORY}.git"
                subprocess.run(["git", "config", "--global", "user.name", "FieldBot"], capture_output=True)
                subprocess.run(["git", "config", "--global", "user.email", "bot@field.com"], capture_output=True)
                subprocess.run(["git", "add", "ARSIV/*.md"], capture_output=True)
                subprocess.run(["git", "commit", "-m", f"Saha Raporu: {now.strftime('%Y-%m-%d %H:%M')}"], capture_output=True)
                subprocess.run(["git", "push", repo_url, "HEAD:main"], capture_output=True)
                print(f"✅ Rapor GitHub'a arşivlendi: {file_name}")
            else:
                print("⚠️ GITHUB_TOKEN eksik, dosya push edilemedi.")
            
        except Exception as e:
            print(f"⚠️ Arşivleme/Git Hatası: {e}")

        # --- KİŞİSELLEŞTİRİLMİŞ E-POSTA DAĞITIMI ---
        for sub in subscribers:
            email = sub.get('email')
            lang = sub.get('aktif_dil', 'Türkçe') # Varsayılan Türkçe
            
            # Dile göre rapor seçimi (Eğer o dil üretilmediyse varsayılanı kullan)
            target_report = reports.get(lang, main_report)
            
            send_custom_email(target_report, ref_html, audio, email, lang)
            
        print("🚀 İstihbarat akışı başarıyla tamamlandı.")
    else:
        print("⚠️ Son 24 saat içinde raporlanmamış YENİ bir gelişme tespit edilemedi. Operasyon askıya alındı.")
