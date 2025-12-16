import feedparser
import requests
import smtplib
import os
import glob
import datetime
import time # <--- YENI: Tarih filtresi için eklendi
import subprocess
import asyncio
import re
import networkx as nx
import matplotlib.pyplot as plt
import edge_tts
import trafilatura
from groq import Groq
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders

# ==========================================
# 1. AYARLAR
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]

raw_mail_list = os.environ["ALICI_MAIL"]
ALICI_LISTESI = [email.strip() for email in raw_mail_list.split(',')]

client = Groq(api_key=GROQ_API_KEY)
SES_MODELI = "tr-TR-AhmetNeural"
plt.switch_backend('Agg')

# --- GENİŞLETİLMİŞ KAYNAK HAVUZU (INTEGRATED) ---
rss_sources = {
    # Batı Ana Akım
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'The Diplomat': 'https://thediplomat.com/feed/',
    'Stratfor': 'https://worldview.stratfor.com/rss/feed/all',
    
    # Doğu / Alternatif
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'TASS (Russia)': 'https://tass.com/rss/v2.xml',
    'China Daily': 'https://www.chinadaily.com.cn/rss/world_rss.xml',
    'Tehran Times': 'https://www.tehrantimes.com/rss',
    'Times of Israel': 'https://www.timesofisrael.com/feed/',
    
    # Savaş Çalışmaları & Think-Tank
    'ISW (War Study)': 'https://www.understandingwar.org/feeds.xml',
    'Carnegie Endowment': 'https://carnegieendowment.org/rss/solr/?fa=ir_search',
    
    # Telegram / OSINT (Hızlı Akış)
    'Clash Report': 'https://rsshub.app/telegram/channel/clashreport', 
    'Intel Slava': 'https://rsshub.app/telegram/channel/intelslava', 
    'Geopolitics Live': 'https://rsshub.app/telegram/channel/geopolitics_live', 
    'Bellincat': 'https://www.bellingcat.com/feed/' 
}

# ==========================================
# 2. AJAN 1: RESEARCHER (GÜNCELLENDİ)
# ==========================================
def calculate_priority_score(title, summary):
    score = 0
    text = (title + " " + summary).lower()
    
    # Stratejik/Akademik Kelimeler (Yüksek Puan)
    academic_keys = ["doctrine", "strategy", "hegemony", "nuclear", "geopolitics", "sanctions", "treaty", "alliance", "deterrence", "proxy war"]
    if any(w in text for w in academic_keys): score += 60
    
    # Sıcak Çatışma/Kriz (Orta Puan)
    conflict_keys = ["war", "attack", "missile", "gaza", "ukraine", "taiwan", "china", "russia", "nato", "turkey", "syria", "drone"]
    if any(w in text for w in conflict_keys): score += 40
    
    return score

def get_full_text(url):
    # Telegram linkleri veya PDF'ler için indirme yapma
    if "t.me" in url or "telegram" in url or ".pdf" in url: return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text: return text[:3000] # Makul uzunluk
    except: pass
    return None

def fetch_news():
    print("🕵️‍♂️ AJAN 1: Geniş çaplı veri taraması yapılıyor...")
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Şu anki zamanı al (Bayat haber kontrolü için)
    now = datetime.datetime.now()

    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for entry in feed.entries[:6]: # Her kaynaktan 6 habere bak, filtrele
                    
                    # --- TARİH FİLTRESİ (24 Saat Kuralı) ---
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            pub_date = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
                            # 86400 saniye = 24 saat. Bundan eskiyse alma.
                            if (now - pub_date).total_seconds() > 86400:
                                continue 
                        except: pass 
                    # ---------------------------------------

                    title = entry.title
                    link = entry.link
                    summary = entry.summary[:400] if hasattr(entry, 'summary') else ""
                    score = calculate_priority_score(title, summary)
                    all_news.append({"source": source, "title": title, "link": link, "summary": summary, "score": score})
        except: continue

    # Puanına göre sırala ve EN İYİ 12 GÜNCEL HABERİ seç
    all_news.sort(key=lambda x: x['score'], reverse=True)
    top_news = all_news[:12] 
    
    buffer = ""
    raw_links_html = "<ul>"
    current_keywords = []

    print(f"🕷️  AJAN 1: Seçilen {len(top_news)} GÜNCEL haber işleniyor...")
    
    for i, news in enumerate(top_news):
        # Sadece ilk 5 haberin tam metnini al (Derin analiz için), diğerlerinin özetini al
        full_text = get_full_text(news['link']) if i < 5 else None
        content_to_use = full_text if full_text else news['summary']
        
        buffer += f"--- HABER {i+1} ({news['source']}) ---\nBAŞLIK: {news['title']}\nİÇERİK: {content_to_use[:1200]}\nURL: {news['link']}\n\n"
        raw_links_html += f"<li><b>{news['source']}:</b> <a href='{news['link']}'>{news['title']}</a></li>"
        current_keywords.extend(news['title'].lower().split())
    
    raw_links_html += "</ul>"
    return buffer, raw_links_html, current_keywords

# ==========================================
# 3. HAFIZA (GÜNCELLENDİ)
# ==========================================
def read_historical_memory(current_keywords):
    memory_buffer = ""
    files = glob.glob("ARSIV/*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    
    keywords = list(set([k for k in current_keywords if len(k) > 5]))[:5]
    total_chars = 0
    
    for file_path in files:
        if total_chars > 10000: break
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if sum(content.lower().count(k) for k in keywords) > 0:
                memory_buffer += f"\n[GEÇMİŞ RAPOR - {os.path.basename(file_path)}]: {content[:1500]}...\n"
                total_chars += len(content[:1500])
                
    return memory_buffer if memory_buffer else "Arşivde doğrudan ilişkili örüntü bulunamadı."

# ==========================================
# 4. HARİTA (AJAN 5 - OPTİMİZE EDİLDİ)
# ==========================================
def draw_network_graph(text_data):
    print("🗺️ AJAN 5: İlişki ağı çiziliyor...")
    prompt = f"Metindeki 'Ülke-Ülke' veya 'Lider-Lider' gerilimlerini/ittifaklarını 'Aktör1,Aktör2' formatında listele:\n{text_data[:4000]}"
    try:
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        relations = completion.choices[0].message.content.split('\n')
    except: relations = [] 

    G = nx.Graph()
    for line in relations:
        if "," in line:
            parts = line.split(',')
            if len(parts) >= 2: G.add_edge(parts[0].strip(), parts[1].strip())
    
    if G.number_of_nodes() == 0: G.add_edge("Ankara", "Dünya")
    
    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(G, k=1.8) 
    nx.draw(G, pos, with_labels=True, node_color='#2c3e50', node_size=2200, font_color='white', font_size=8, font_weight='bold', edge_color='#95a5a6')
    
    filename = "network_map.png"
    plt.savefig(filename, bbox_inches='tight', dpi=100)
    plt.close()
    return filename

# ==========================================
# 5. AJANLI SİMÜLASYON (AKADEMİK MOD)
# ==========================================
def run_agent_workflow(current_data, historical_memory):
    
    print("⏳ AJAN 2 (Tarihçi) ve AJAN 3 (Teorisyen) çalışıyor...")
    
    critic_report = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": f"""
        Verilen metinlerdeki ({current_data[:5000]}) anlatıları 'Söylem Analizi' ile incele.
        Batı ve Doğu medyası arasındaki çelişkileri bul. Yanıtı Türkçe ver.
        """}]
    ).choices[0].message.content

    print("✍️ AJAN 4 (BAŞ STRATEJİST): Rapor yazılıyor...")
    
    # --- YENİ STRATEJİK & AKADEMİK PROMPT ---
    final_system_prompt = """Sen Savaş Odası'nın Baş Stratejistisin. Hedef kitlen Siyaset Bilimi öğrencileri ve akademisyenler.
    
    GÖREVİN: Elindeki GÜNCEL haberleri analiz et ve aşağıdaki FORMATTA raporla:
    
    1. DERİNLİK (İlk Bölüm): En kritik 3 GÜNCEL olayı seç. Bunları Uluslararası İlişkiler Teorileri (Realizm, Liberalizm, Konstrüktivizm, Güvenlik İkilemi vb.) ile akademik dilde analiz et. "So What?" (Bu neden önemli?) sorusuna cevap ver.
    2. GENİŞLİK (İkinci Bölüm): Kalan haberleri "Küresel Ufuk Turu" başlığı altında, kısa ve net maddeler halinde listele.
    3. DİL: %100 Resmi, Akademik ve Akıcı İstanbul Türkçesi.
    
    RAPOR ŞABLONU (HTML KULLAN):
    
    <div style="background-color:#f4f6f7; padding:15px; border-left:5px solid #c0392b; margin-bottom:20px;">
        <h2 style="color:#c0392b; margin-top:0;">⚡ GÜNÜN STRATEJİK ÖZETİ</h2>
        <p><i>(Buraya tüm olayları sentezleyen, vizyoner bir giriş paragrafı yaz.)</i></p>
    </div>

    <h3 style="color:#2c3e50;">1. 🔭 DERİN ANALİZ: TEORİ VE PRATİK</h3>
    <p><b>Olay 1:</b> (Başlık)</p>
    <p><b>Teorik Çerçeve:</b> (Örn: "Bu hamle, Mearsheimer'ın Ofansif Realizm teorisi bağlamında, bölgesel hegemonya arayışı olarak okunmalıdır...")</p>
    <p><b>Gelecek Projeksiyonu:</b> (Bu olay nereye evrilir?)</p>
    <br>
    <p><b>Olay 2:</b> (Başlık)</p>
    <p><b>Teorik Çerçeve:</b> (Akademik analiz...)</p>
    <br>
    <p><b>Olay 3:</b> (Başlık)</p>
    <p><b>Teorik Çerçeve:</b> (Akademik analiz...)</p>

    <h3 style="color:#2980b9;">2. 🌐 KÜRESEL UFUK TURU (Diğer Gelişmeler)</h3>
    <ul>
        <li>🌍 (Diğer önemli haber 1) - Kaynak</li>
        <li>🌍 (Diğer önemli haber 2) - Kaynak</li>
        <li>🌍 (Diğer önemli haber 3) - Kaynak</li>
        <li>(Kalan haberleri buraya ekle...)</li>
    </ul>

    <h3 style="color:#d35400;">3. 👁️ KIZIL TAKIM NOTLARI (Propaganda Analizi)</h3>
    <div style="font-size:14px; font-style:italic; color:#555;">
        {critic_report_placeholder}
    </div>

    <div style="background-color:#e8f8f5; padding:15px; border-radius:5px; margin-top:20px; border:1px solid #1abc9c;">
        <h4 style="color:#16a085; margin-top:0;">🇹🇷 ANKARA İÇİN POLİTİKA ÖNERİSİ</h4>
        <p>(Makyevelist ve Realist bir perspektifle Türkiye'ye somut tavsiye ver.)</p>
    </div>
    
    <br>
    <div style="background-color:#fff3cd; padding:10px; border-radius:5px;">
        <b style="color:#856404;">📚 GÜNÜN AKADEMİK KAVRAMI:</b> (Olaylarla ilgili bir IR kavramını açıkla.)
    </div>
    """
    
    final_user_prompt = f"""
    HAM VERİLER (12 Haber): {current_data[:12000]}
    TARİHSEL BAĞLAM: {historical_memory}
    ELEŞTİREL ANALİZ: {critic_report}
    
    Yukarıdaki verileri şablona uygun olarak işle. Hem derinlik (teori) hem genişlik (ufuk turu) sağla.
    Şablondaki {{critic_report_placeholder}} yerine eleştirel analizi özetleyerek koy.
    """
    
    final_report = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": final_system_prompt.replace("{critic_report_placeholder}", "Aşağıda detaylandırılmıştır.")},
            {"role": "user", "content": final_user_prompt}
        ],
        temperature=0.3
    ).choices[0].message.content
    
    return final_report

# ==========================================
# 6. SES & MAİL & ARŞİV
# ==========================================
async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio(text_content):
    print("🎙️ Seslendiriliyor...")
    clean_text = re.sub('<[^<]+?>', '', text_content)
    clean_text = re.sub(r'http\S+', '', clean_text)
    script = "Savaş Odası Günlük İstihbarat Raporu. " + clean_text[:1500]
    filename = "Analiz_Ozet.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

def archive(report_body):
    # Dosya üzerine yazma sorununu çözen format
    date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = f"ARSIV/Analiz_{date_str}.md"
    if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
    with open(path, "w", encoding="utf-8") as f: f.write(report_body)
    try:
        subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"])
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "add", path])
        subprocess.run(["git", "commit", "-m", f"Rapor: {date_str}"])
        subprocess.run(["git", "push"])
    except: pass

def send_email_to_council(report_body, raw_links, audio_file, image_file):
    print(f"📧 Gönderiliyor: {len(ALICI_LISTESI)} kişi")
    CANLI_DASHBOARD_LINKI = "https://siyasi-istihbarat-botu.streamlit.app" 
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        
        for alici in ALICI_LISTESI:
            msg = MIMEMultipart('related')
            msg['From'] = GMAIL_USER
            msg['To'] = alici 
            msg['Subject'] = f"🧠 SAVAŞ ODASI: Stratejik Derinlik - {datetime.date.today()}"
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            html_content = f"""
            <html><body style='font-family: "Georgia", serif; color:#222; line-height: 1.6; background-color: #f9f9f9; padding: 20px;'>
                <div style="max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.05); border-top: 5px solid #c0392b;">
                    
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color:#2c3e50; font-family: 'Impact', sans-serif; letter-spacing: 1px;">SAVAŞ ODASI</h1>
                        <p style="color:#7f8c8d; font-style: italic;">"Derinlik, Genişlik ve Strateji"</p>
                    </div>

                    <div style="text-align:center; margin-bottom:20px;">
                         <img src="cid:network_map" style="width:100%; max-width:700px; border: 1px solid #ddd; padding: 5px;">
                         <p style="font-size:12px; color:#999;">Günlük İlişki Ağı</p>
                    </div>

                    <div style="font-size: 16px;">{report_body}</div>
                    
                    <div style="margin-top: 40px; padding: 20px; background-color: #eef2f3; border-radius: 5px;">
                        <h4 style="margin-top: 0; color: #2c3e50;">🔗 İLERİ OKUMA & KAYNAKLAR</h4>
                        <div style="font-size: 13px; color: #555;">{raw_links}</div>
                    </div>
                    
                    <div style="text-align:center; margin-top:30px;">
                        <a href="{CANLI_DASHBOARD_LINKI}" style="background-color: #c0392b; color: white; padding: 12px 25px; text-decoration: none; border-radius: 3px; font-weight: bold; font-family: sans-serif;">
                           CANLI İSTİHBARAT MASASINA GİT >>
                        </a>
                    </div>
                </div>
            </body></html>
            """
            msg_alternative.attach(MIMEText(html_content, 'html'))
            
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
        print("✅ Rapor başarıyla dağıtıldı.")
    except Exception as e:
        print(f"❌ Mail Hatası: {e}")

if __name__ == "__main__":
    raw_data, raw_links, current_keywords = fetch_news()
    memory = read_historical_memory(current_keywords)
    if len(raw_data) > 50: 
        report = run_agent_workflow(raw_data, memory)
        graph_map = draw_network_graph(raw_data)
        archive(report)
        audio = create_audio(report)
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Yeterli veri yok, rapor oluşturulmadı.")
