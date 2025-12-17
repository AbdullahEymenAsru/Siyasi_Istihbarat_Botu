import feedparser
import requests
import smtplib
import os
import glob
import datetime
import time
import subprocess
import asyncio
import re
import networkx as nx
import matplotlib.pyplot as plt
import edge_tts
import trafilatura
from groq import Groq
from supabase import create_client, Client
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders

# ==========================================
# 1. AYARLAR & GÜVENLİK
# ==========================================

# GitHub Actions veya Local Environment değişkenleri
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# İstemcileri Başlat
client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SES_MODELI = "tr-TR-AhmetNeural"
plt.switch_backend('Agg') # Grafik çizimi için arka plan modu

# ALICI LİSTESİNİ VERİTABANINDAN ÇEK (DİNAMİK)
def get_email_list():
    try:
        response = supabase.table("abone_listesi").select("email").eq("aktif", True).execute()
        emails = [row['email'] for row in response.data]
        if not emails: # Eğer veritabanı boşsa çevresel değişkenden al
            raw = os.environ.get("ALICI_MAIL", "")
            return [e.strip() for e in raw.split(',')] if raw else []
        return emails
    except Exception as e:
        print(f"⚠️ Veritabanı Hatası (Mail Listesi): {e}")
        return []

ALICI_LISTESI = get_email_list()

# ==========================================
# 2. İSTİHBARAT KAYNAKLARI (STRATEJİK + TELEGRAM)
# ==========================================

RSS_SOURCES = {
    "THINK_TANK": [
        "https://foreignpolicy.com/feed/",
        "https://carnegieendowment.org/rss/solr/get/all",
        "https://www.csis.org/rss/analysis",
        "https://www.understandingwar.org/feeds.xml", # ISW (Savaş Çalışmaları)
        "https://warontherocks.com/feed/",
        "https://www.cfr.org/rss/newsletters/daily-brief", # CFR
        "https://www.setav.org/feed/" # SETA (Ankara Perspektifi)
    ],
    "NEWS": [
        "https://www.aa.com.tr/tr/rss/default?cat=guncel", # Anadolu Ajansı
        "https://www.trthaber.com/dunya_articles.rss", # TRT Haber
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
        "https://tass.com/rss/v2.xml", # Rusya Resmi (TASS)
        "https://thediplomat.com/feed/", # Asya-Pasifik
        "https://www.middleeasteye.net/rss", # Orta Doğu
        "https://www.dw.com/xml/rss-tur-dunya" # Avrupa Hattı
    ],
    "TELEGRAM_INTEL": [
        # Not: Telegram RSS köprüleri bazen yavaşlayabilir.
        "https://rsshub.app/telegram/channel/rybar_en", # RYBAR (Rus İstihbarat/Askeri Analiz - DOĞU KANADI)
        "https://rsshub.app/telegram/channel/bellingcat", # BELLINGCAT (OSINT Araştırma - BATI KANADI)
        "https://rsshub.app/telegram/channel/intelslava", # INTEL SLAVA (Rusya/Ukrayna Saha - DOĞU KANADI)
        "https://rsshub.app/telegram/channel/geopolitics_live", # Jeopolitik Özetler (KÜRESEL)
    ]
}

# ==========================================
# 3. VERİ TOPLAMA VE FİLTRELEME
# ==========================================

def get_full_text(url):
    """Linkteki haberin tam metnini çeker."""
    if "t.me" in url or "telegram" in url or ".pdf" in url: return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text: return text[:2500]
    except: pass
    return None

def fetch_news():
    print("🕵️‍♂️ AJAN 1: İstihbarat toplama ve filtreleme başlatıldı...")
    news_items = []
    raw_links_html = ""

    # --- TEKRAR ÖNLEME PROTOKOLÜ (SUPABASE) ---
    try:
        past_24h = datetime.datetime.now() - datetime.timedelta(hours=24)
        response = supabase.table("reports").select("content").gte("created_at", past_24h.isoformat()).execute()
        past_content = str(response.data)
    except Exception as e:
        print(f"⚠️ Geçmiş kontrol hatası: {e}")
        past_content = ""

    # 1. THINK TANK TARAMASI (Zorunlu)
    print("🧠 Think-Tank kaynakları taranıyor...")
    for url in RSS_SOURCES["THINK_TANK"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                if entry.link not in past_content:
                    full_content = get_full_text(entry.link)
                    summary = full_content if full_content else entry.get('summary', '')[:500]
                    news_items.append(f"TYPE: ACADEMIC_INTEL | SOURCE: {feed.feed.get('title', 'ThinkTank')} | TITLE: {entry.title} | LINK: {entry.link} | CONTENT: {summary}")
                    raw_links_html += f"<li><a href='{entry.link}' style='color:#c0392b; font-weight:bold;'>[STRATEJİ] {entry.title}</a></li>"
        except: continue

    # 2. TELEGRAM İSTİHBARAT TARAMASI
    print("📡 Telegram hatları dinleniyor...")
    for url in RSS_SOURCES["TELEGRAM_INTEL"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]: # Her kanaldan son 2 mesaj
                # Telegram mesajları genellikle kısadır, başlık bazen olmaz
                title = entry.title if 'title' in entry else "Telegram Intel"
                desc = entry.description if 'description' in entry else ""
                
                # HTML taglerini temizle
                clean_desc = re.sub('<[^<]+?>', '', desc)[:1000]
                
                news_items.append(f"TYPE: FIELD_INTEL (TELEGRAM) | SOURCE: {feed.feed.get('title', 'Telegram')} | CONTENT: {clean_desc}")
                # Telegram linklerini eklemiyoruz (spam olmaması için), sadece analize sokuyoruz.
        except: continue

    # 3. GENEL HABER TARAMASI
    print("🌍 Küresel haber kaynakları taranıyor...")
    for url in RSS_SOURCES["NEWS"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                if entry.link not in past_content:
                    news_items.append(f"TYPE: OPEN_SOURCE | SOURCE: {feed.feed.get('title', 'News')} | TITLE: {entry.title} | LINK: {entry.link} | SUMMARY: {entry.get('summary', '')[:300]}")
                    raw_links_html += f"<li><a href='{entry.link}' style='color:#2980b9;'>{entry.title}</a></li>"
        except: continue

    combined_data = "\n\n".join(news_items)
    return combined_data, raw_links_html

# ==========================================
# 4. HAFIZA (SUPABASE RAG SİSTEMİ)
# ==========================================

def get_historical_context():
    print("📚 Arşiv kayıtları ve tarihsel hafıza taranıyor...")
    try:
        response = supabase.table("reports").select("content, created_at").order("created_at", desc=True).limit(15).execute()
        context_text = ""
        for row in response.data:
            date = row['created_at'].split('T')[0]
            context_text += f"--- RAPOR TARİHİ: {date} ---\n{row['content'][:800]}\n\n"
        return context_text
    except Exception as e:
        print(f"❌ Hafıza hatası: {e}")
        return "Tarihsel veri bulunamadı."

# ==========================================
# 5. HARİTA (NETWORK GRAPH)
# ==========================================

def draw_network_graph(text_data):
    print("🗺️ AJAN 5: İlişki ağı haritası çiziliyor...")
    prompt = f"Aşağıdaki metindeki devletler ve aktörler arasındaki gerilim veya ittifakları sadece 'Aktör1,Aktör2' formatında listele. Başka hiçbir şey yazma:\n{text_data[:3000]}"
    try:
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        relations = completion.choices[0].message.content.split('\n')
    except: relations = []

    G = nx.Graph()
    for line in relations:
        if "," in line:
            parts = line.split(',')
            if len(parts) >= 2: G.add_edge(parts[0].strip(), parts[1].strip())

    if G.number_of_nodes() == 0: G.add_edge("Global", "Dynamics")

    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(G, k=1.5)
    nx.draw(G, pos, with_labels=True, node_color='#2c3e50', node_size=2000, font_color='white', font_size=8, font_weight='bold', edge_color='#e74c3c', width=1.5)

    filename = "network_map.png"
    plt.savefig(filename, bbox_inches='tight', dpi=100, facecolor='#f4f6f7')
    plt.close()
    return filename

# ==========================================
# 6. AKADEMİK ANALİZ VE RAPORLAMA (DOKTRİNER MOD)
# ==========================================

def run_agent_workflow(current_data, historical_memory):
    print("✍️ BAŞ STRATEJİST: Akademik disiplin ve doktriner analiz başlatıldı...")
    today = datetime.datetime.now().strftime("%d %B %Y")

    system_prompt = f"""
    Sen 'Küresel Savaş Odası'nın Baş Jeopolitik Analisti ve Strateji Uzmanısın. Çıktıların, karar vericilere sunulan bir 'Akademik İstihbarat Brifingi' (Academic Intelligence Briefing) niteliğinde olmalıdır.

    **AKADEMİK DİSİPLİN PROTOKOLLERİ:**
    1. **KAVRAMSAL ÇERÇEVE:** Analizlerini Realizm (Güç Dengesi), Liberalizm (Karşılıklı Bağımlılık) ve Jeopolitik Determinizm (Coğrafi Etkiler) ekseninde kur. "Haber" değil, "Olayların Yapısal Analizini" sun.
    2. **TERMINOLOJİ:** Popüler dil yerine teknik terminoloji kullan. (Örn: 'Savaş çıkabilir' yerine 'Güvenlik ikilemi (Security Dilemma) tırmanmaktadır', 'Dengeler değişti' yerine 'Kutup sisteminde asimetrik kayma gözlenmektedir').
    3. **SENTETİK HAFIZA:** Hafızadaki verileri istatistiksel ve kronolojik bir trend analizi olarak kullan. Olayları tekil değil, bir sürecin parçası olarak değerlendir.
    4. **DİYALEKTİK YAKLAŞIM:** Her hamleyi 'Etki-Tepki' (Action-Reaction) mekanizmasıyla açıkla.

    **RAPOR YAPISI (ZORUNLU HTML):**
    Analizi 'Georgia' fontuyla, profesyonel bir memorandum formatında sun.

    <div style="font-family: 'Georgia', serif; line-height: 1.8; color: #1a1a1a; max-width: 800px; margin: auto;">
        <div style="text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-bottom: 30px;">
            <h1 style="color: #2c3e50; text-transform: uppercase; margin: 0;">Jeopolitik Durum Değerlendirmesi</h1>
            <p style="font-size: 13px; color: #7f8c8d;">Doktriner Analiz Birimi | Rapor No: {today.replace(' ', '-')}</p>
        </div>

        <h2 style="color: #c0392b; border-left: 4px solid #c0392b; padding-left: 10px; font-variant: small-caps;">I. Stratejik Kırılma Noktaları (Kritik Analiz)</h2>
        <p>(En önemli olayları 'Uluslararası Sistem' üzerindeki etkileriyle analiz et. Realist güç teorilerini uygula.)</p>

        <h2 style="color: #2980b9; border-left: 4px solid #2980b9; padding-left: 10px; font-variant: small-caps;">II. Bölgesel Güç Projeksiyonları</h2>
        <p>(Aktörlerin hareketlerini 'Sıfır Toplamlı Oyun' (Zero-Sum Game) perspektifiyle açıkla.)</p>

        <div style="background-color: #f9f9f9; padding: 25px; border-top: 1px solid #eee; border-bottom: 1px solid #eee; margin: 25px 0;">
            <h3 style="color: #2c3e50; margin-top: 0; font-style: italic;">📓 Doktriner Referans (Think-Tank & Teori)</h3>
            <p>(Think-Tank verilerini, akademik bir makale özeti ciddiyetinde yorumla.)</p>
        </div>

        <h2 style="color: #27ae60; border-left: 4px solid #27ae60; padding-left: 10px; font-variant: small-caps;">III. Projeksiyon ve Stratejik Tavsiye</h2>
        <p>(Kısa ve orta vadeli öngörüleri rasyonel seçim teorisi üzerinden sun.)</p>
        
        <div style="text-align: right; font-size: 11px; color: #bdc3c7; margin-top: 40px;">
            Savaş Odası Yapay Zeka Strateji Modülü tarafından otomatik olarak derlenmiştir.
        </div>
    </div>
    """

    user_content = f"GEÇMİŞ HAFIZA:\n{historical_memory}\n\nGÜNCEL VERİLER:\n{current_data}"

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.3, # Daha düşük sıcaklık = Daha tutarlı ve ciddi analiz
        max_tokens=4000
    )

    return completion.choices[0].message.content

# ==========================================
# 7. SES & MAIL & ARŞİV (DAĞITIM)
# ==========================================

async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio_summary(report_html):
    print("🎙️ Sesli brifing hazırlanıyor...")
    clean_text = re.sub('<[^<]+?>', '', report_html)
    clean_text = clean_text.replace(" ", " ").replace("\n", " ")
    script = "Savaş Odası Günlük İstihbarat Raporu. " + clean_text[:1500] + "... Raporun tamamı e-postadadır."
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

def archive_report(content_html, raw_links):
    try:
        data = {"content": content_html, "created_at": datetime.datetime.now().isoformat()}
        supabase.table("reports").insert(data).execute()
        print("✅ Rapor Supabase veritabanına işlendi.")
    except Exception as e:
        print(f"❌ Supabase kayıt hatası: {e}")

    tr_time = datetime.datetime.now() + datetime.timedelta(hours=3)
    date_str = tr_time.strftime("%Y-%m-%d_%H-%M")
    path = f"ARSIV/Analiz_{date_str}.md"
    if not os.path.exists("ARSIV"): os.makedirs("ARSIV")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content_html + "\n\n" + raw_links)

    try:
        subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"])
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "add", path])
        subprocess.run(["git", "commit", "-m", f"Rapor: {date_str}"])
        subprocess.run(["git", "push"])
    except: pass

def send_email_to_council(report_body, raw_links, audio_file, image_file):
    if not ALICI_LISTESI:
        print("❌ HATA: Alıcı listesi boş! Mail gönderilmedi.")
        return

    print(f"📧 Dağıtım Başladı: {len(ALICI_LISTESI)} alıcı.")
    
    # --- DÜZELTME: Saf URL formatı (Markdown değil) ---
    CANLI_DASHBOARD_LINKI = "https://siyasi-istihbarat-botu.streamlit.app/"

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)

        tr_today = (datetime.datetime.now() + datetime.timedelta(hours=3)).date()

        for alici in ALICI_LISTESI:
            msg = MIMEMultipart('related')
            msg['From'] = GMAIL_USER
            msg['To'] = alici
            msg['Subject'] = f"🛡️ SAVAŞ ODASI: Stratejik Durum - {tr_today}"

            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            full_html = f"""
            <html><body style='font-family: "Georgia", serif; color:#222; background-color: #f4f4f4; padding: 20px;'>
                <div style="max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 8px; border-top: 6px solid #2c3e50;">

                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color:#2c3e50; font-family: 'Times New Roman', serif; letter-spacing: 1px; margin:0;">KÜRESEL SAVAŞ ODASI</h1>
                        <p style="color:#7f8c8d; font-style: italic; margin-top: 5px;">"Stratejik İstihbarat Merkezi"</p>
                    </div>

                    <div style="text-align:center; margin-bottom: 20px;">
                         <a href="{CANLI_DASHBOARD_LINKI}" style="background-color: #2c3e50; color: #ffffff; padding: 12px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px;">
                            🚀 CANLI DASHBOARD'A GİT
                        </a>
                    </div>

                    <div style="text-align:center; margin-bottom:30px;">
                         <img src="cid:network_map" style="width:100%; max-width:700px; border: 1px solid #ddd; padding: 5px; border-radius: 5px;">
                         <p style="font-size:12px; color:#999;">Günlük Küresel İlişki Ağı</p>
                    </div>

                    {report_body}

                    <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">

                    <div style="background-color:#f9f9f9; padding:15px; border-radius:5px;">
                        <h4 style="color:#555; margin-top:0;">📚 DOĞRULANMIŞ KAYNAKÇA & DOI</h4>
                        <ul style="font-size:12px; color:#555; padding-left: 20px;">
                           {raw_links}
                        </ul>
                    </div>
                </div>
            </body></html>
            """

            msg_alternative.attach(MIMEText(full_html, 'html'))

            if image_file and os.path.exists(image_file):
                with open(image_file, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<network_map>')
                    img.add_header('Content-Disposition', 'inline', filename=image_file)
                    msg.attach(img)

            if audio_file and os.path.exists(audio_file):
                with open(audio_file, "rb") as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{audio_file}"')
                    msg.attach(part)

            server.sendmail(GMAIL_USER, alici, msg.as_string())

        server.quit()
        print("✅ Tüm raporlar başarıyla dağıtıldı.")
    except Exception as e:
        print(f"❌ Mail Gönderim Hatası: {e}")

# ==========================================
# 8. ÇALIŞTIRMA (MAIN)
# ==========================================

if __name__ == "__main__":
    news_data, links_html = fetch_news()

    if not news_data:
        print("⚠️ Yeterli yeni veri bulunamadı. Operasyon durduruluyor.")
    else:
        memory = get_historical_context()
        report_html = run_agent_workflow(news_data, memory)
        graph_file = draw_network_graph(news_data)
        audio_file = create_audio_summary(report_html)
        archive_report(report_html, links_html)
        send_email_to_council(report_html, links_html, audio_file, graph_file)
