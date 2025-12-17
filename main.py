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
# 2. İSTİHBARAT KAYNAKLARI (KATEGORİZE EDİLMİŞ)
# ==========================================

# Yeni sistemde kaynakları ikiye ayırıyoruz: Genel ve Stratejik
RSS_SOURCES = {
    "THINK_TANK": [
        "https://foreignpolicy.com/feed/",
        "https://carnegieendowment.org/rss/solr/get/all",
        "https://www.csis.org/rss/analysis",
        "https://www.understandingwar.org/feeds.xml", # ISW
        "https://warontherocks.com/feed/"
    ],
    "NEWS": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
        "https://tass.com/rss/v2.xml", # Rusya
        "https://thediplomat.com/feed/", # Asya-Pasifik
        "https://www.middleeasteye.net/rss", # Orta Doğu
        "https://www.chinadaily.com.cn/rss/world_rss.xml" # Çin
    ]
}

# ==========================================
# 3. VERİ TOPLAMA VE FİLTRELEME (YENİ MANTIK)
# ==========================================

def get_full_text(url):
    """Linkteki haberin tam metnini çeker (Özet yetersizse)"""
    # Hatalı markdown linki düzeltildi: [t.me](http://t.me/) -> "t.me"
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
        # Son 24 saatteki raporların içeriğini çekiyoruz
        response = supabase.table("reports").select("content").gte("created_at", past_24h.isoformat()).execute()
        past_content = str(response.data)
    except Exception as e:
        print(f"⚠️ Geçmiş kontrol hatası: {e}")
        past_content = ""

    # 1. THINK TANK TARAMASI (Zorunlu ve Öncelikli)
    print("🧠 Think-Tank kaynakları taranıyor...")
    for url in RSS_SOURCES["THINK_TANK"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]: # Her kaynaktan en yeni 2 makale
                if entry.link not in past_content:
                    # Mümkünse tam metni al, yoksa özeti
                    full_content = get_full_text(entry.link)
                    summary = full_content if full_content else entry.get('summary', '')[:500]

                    news_items.append(f"SOURCE_TYPE: THINK_TANK | SOURCE: {feed.feed.get('title', 'ThinkTank')} | TITLE: {entry.title} | LINK: {entry.link} | CONTENT: {summary}")
                    raw_links_html += f"<li><a href='{entry.link}' style='color:#c0392b; font-weight:bold;'>[THINK TANK] {entry.title}</a> - {feed.feed.get('title', 'Source')}</li>"
        except: continue

    # 2. GENEL HABER TARAMASI
    print("🌍 Küresel haber kaynakları taranıyor...")
    for url in RSS_SOURCES["NEWS"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                if entry.link not in past_content:
                    news_items.append(f"SOURCE_TYPE: NEWS | SOURCE: {feed.feed.get('title', 'News')} | TITLE: {entry.title} | LINK: {entry.link} | SUMMARY: {entry.get('summary', '')[:300]}")
                    raw_links_html += f"<li><a href='{entry.link}' style='color:#2980b9;'>{entry.title}</a> - {feed.feed.get('title', 'Source')}</li>"
        except: continue

    combined_data = "\n\n".join(news_items)
    return combined_data, raw_links_html

# ==========================================
# 4. HAFIZA (SUPABASE RAG SİSTEMİ)
# ==========================================

def get_historical_context():
    print("📚 Arşiv kayıtları ve tarihsel hafıza taranıyor...")
    try:
        # Son 15 raporu çekerek geniş bir hafıza oluşturuyoruz
        response = supabase.table("reports").select("content, created_at").order("created_at", desc=True).limit(15).execute()
        context_text = ""
        for row in response.data:
            date = row['created_at'].split('T')[0]
            # Raporun tamamını değil, özet kısmını veya başlarını alıyoruz ki token dolmasın
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
# 6. ANALİZ VE RAPORLAMA (YENİ GÜÇLÜ PROMPT)
# ==========================================

def run_agent_workflow(current_data, historical_memory):
    print("✍️ BAŞ STRATEJİST: Derin analiz protokolü çalıştırılıyor...")
    today = datetime.datetime.now().strftime("%d %B %Y")

    system_prompt = f"""
    Sen 'Savaş Odası'nın Baş İstihbarat Analistisin. Görevin, sağlanan açık kaynak verilerini (OSINT) analiz ederek Konsey Üyelerine stratejik derinliği olan bir rapor sunmaktır.

    **GÖREV KURALLARI (ZORUNLU):**
    1. **DERİNLİK & MAKİNE ÖĞRENİMİ:** Haberleri sakın tek cümleyle geçme. 'Hafıza' kısmında verilen geçmiş raporları oku. Eğer bir olay (örn: Suriye) geçen hafta da varsa, "Geçen haftaki raporumuzda belirttiğimiz X durumu, bugün Y'ye evrildi" diyerek süreklilik kur.
    2. **KAYNAK FORMATI:** Metin içinde ASLA "(Kaynak)" veya "(Source)" yazma. Haberin kaynağını cümlenin içine yedir.
       - Yanlış: "ABD yaptırım uyguladı. (Kaynak)"
       - Doğru: "Al Jazeera'nin aktardığına göre ABD, bölgedeki..." veya "[Reuters]: Moskova'nın açıklamasına göre..."
    3. **LİNKLER:** Linkleri metin içine gömme. Referansları raporun sonundaki özel bölüme bırakacağız. Ancak metin içinde akademik teori kullanırsan [Realizm] gibi belirt.
    4. **THINK TANK ZORUNLULUĞU:** "Think-Tank Köşesi" bölümünde, sağlanan verilerdeki Foreign Policy, ISW veya Carnegie raporlarından en az birini detaylıca yorumla.

    **ÇIKTI FORMATI (HTML KODU OLARAK VER - SADECE BODY KISMI):**
    Lütfen çıktıyı doğrudan HTML formatında ver, çünkü bu bir e-posta olacak. CSS kullanma, inline style kullan.

    Yapı şöyle olmalı:

    <div style="font-family: Georgia, serif; color: #333;">

        <div style="background-color: #fdf2f0; border-left: 5px solid #c0392b; padding: 15px; margin-bottom: 20px;">
            <h2 style="color: #c0392b; margin-top: 0;">🚨 KIRMIZI ALARM (Sıcak Çatışma & Riskler)</h2>
            <p>(Burada en kritik 2 konuyu, tarihsel bağlamıyla en az 2'şer paragraf analiz et.)</p>
        </div>

        <h3 style="color: #2980b9; border-bottom: 2px solid #2980b9; padding-bottom: 5px;">🌍 KÜRESEL UFUK TURU</h3>
        <p>(Haberleri bölgelere göre başlıklandır: <b>Orta Doğu:</b>, <b>Asya-Pasifik:</b> gibi. Kaynak isimlerini metne yedirerek analiz et.)</p>

        <div style="background-color: #eaf2f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #2c3e50; margin-top: 0;">🧠 THINK-TANK KÖŞESİ (Derin Okuma)</h3>
            <p>(Seçilen Think-Tank raporunun analizi ve Ankara için anlamı.)</p>
        </div>

        <h3 style="color: #27ae60;">🔮 GELECEK SENARYOLARI & POLİTİKA ÖNERİSİ</h3>
        <p>(1 ay sonra ne olur? Türkiye ne yapmalı?)</p>

    </div>
    """

    user_content = f"""
    GEÇMİŞ RAPORLAR (HAFIZA):
    {historical_memory}

    BUGÜNKÜ HAM İSTİHBARAT VERİLERİ:
    {current_data}
    """

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.6,
        max_tokens=3500, # Uzun ve detaylı analiz için artırıldı
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
    # HTML etiketlerini temizle
    clean_text = re.sub('<[^<]+?>', '', report_html)
    clean_text = clean_text.replace(" ", " ").replace("\n", " ")
    # İlk 1500 karakteri seslendir (Çok uzun olmaması için)
    script = "Savaş Odası Günlük İstihbarat Raporu. " + clean_text[:1500] + "... Raporun tamamı e-postadadır."
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

def archive_report(content_html, raw_links):
    # 1. Supabase'e Kaydet (Yapılandırılmış Veri)
    try:
        data = {"content": content_html, "created_at": datetime.datetime.now().isoformat()}
        supabase.table("reports").insert(data).execute()
        print("✅ Rapor Supabase veritabanına işlendi.")
    except Exception as e:
        print(f"❌ Supabase kayıt hatası: {e}")

    # 2. GitHub/Markdown Olarak Kaydet (Yedek)
    tr_time = datetime.datetime.now() + datetime.timedelta(hours=3)
    date_str = tr_time.strftime("%Y-%m-%d_%H-%M")
    path = f"ARSIV/Analiz_{date_str}.md"
    if not os.path.exists("ARSIV"): os.makedirs("ARSIV")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content_html + "\n\n" + raw_links)

    # GitHub Push (Opsiyonel - Eğer token varsa çalışır)
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
    
    # --- DÜZELTME BURADA YAPILDI: Saf URL formatı ---
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
            msg['Subject'] = f"🛡️ SAVAŞ ODASI: Stratejik Derinlik - {tr_today}"

            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            # HTML Şablonu
            full_html = f"""
            <html><body style='font-family: "Georgia", serif; color:#222; background-color: #f4f4f4; padding: 20px;'>
                <div style="max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 8px; border-top: 6px solid #c0392b;">

                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color:#2c3e50; font-family: 'Impact', sans-serif; letter-spacing: 1px; margin:0;">SAVAŞ ODASI</h1>
                        <p style="color:#7f8c8d; font-style: italic; margin-top: 5px;">"Veri değil, İstihbarat."</p>
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

            # Resmi Ekle
            if image_file and os.path.exists(image_file):
                with open(image_file, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<network_map>')
                    img.add_header('Content-Disposition', 'inline', filename=image_file)
                    msg.attach(img)

            # Sesi Ekle
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
    # 1. Veri Topla
    news_data, links_html = fetch_news()

    if not news_data:
        print("⚠️ Yeterli yeni veri bulunamadı. Operasyon durduruluyor (Tekrarı önlemek için).")
    else:
        # 2. Hafızayı Çağır
        memory = get_historical_context()

        # 3. Analiz Et (Yeni Prompt ile)
        report_html = run_agent_workflow(news_data, memory)

        # 4. Görselleri ve Sesi Hazırla
        graph_file = draw_network_graph(news_data)
        audio_file = create_audio_summary(report_html)

        # 5. Kaydet ve Gönder
        archive_report(report_html, links_html)
        send_email_to_council(report_html, links_html, audio_file, graph_file)
