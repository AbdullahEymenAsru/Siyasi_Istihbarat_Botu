import feedparser
import requests
import smtplib
import os
import glob
import datetime
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

# --- KAYNAK HAVUZU ---
rss_sources = {
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'CNN International': 'http://rss.cnn.com/rss/edition.rss',
    'Voice of America': 'https://www.voanews.com/api/zg$oq_et$p',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'Deutsche Welle': 'https://rss.dw.com/xml/rss-en-all',
    'TRT World': 'https://www.trtworld.com/rss',
    'Turkiye Arastirmalari Vakfi': 'https://tav.org.tr/feed/',
    'SETA Vakfi': 'https://www.setav.org/feed/',
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'Times of Israel': 'https://www.timesofisrael.com/feed/',
    'Tehran Times': 'https://www.tehrantimes.com/rss',
    'TASS (Russia)': 'https://tass.com/rss/v2.xml',
    'China Daily': 'https://www.chinadaily.com.cn/rss/world_rss.xml',
    'Yonhap (Korea)': 'https://en.yna.co.kr/RSS/news.xml',
    'Times of India': 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms',
    'Clash Report (Telegram)': 'https://rsshub.app/telegram/channel/clashreport', 
    'SavunmaSanayiST (Telegram)': 'https://rsshub.app/telegram/channel/savunmasanayist', 
    'Rybar (Telegram)': 'https://rsshub.app/telegram/channel/rybar', 
    'Intel Slava (Telegram)': 'https://rsshub.app/telegram/channel/intelslava', 
    'Zelenskiy Official (Telegram)': 'https://rsshub.app/telegram/channel/V_Zelenskiy_official', 
    'Gaza Now (Telegram)': 'https://rsshub.app/telegram/channel/gazaalannet', 
    'IDF Official (Telegram)': 'https://rsshub.app/telegram/channel/idfofficial', 
    'Insider Paper (Telegram)': 'https://rsshub.app/telegram/channel/insiderpaper', 
    'Geopolitics Live (Telegram)': 'https://rsshub.app/telegram/channel/geopolitics_live', 
    'Bellincat (OSINT)': 'https://www.bellingcat.com/feed/' 
}

# ==========================================
# 2. AJAN 1: RESEARCHER
# ==========================================
def calculate_priority_score(title, summary):
    score = 0
    text = (title + " " + summary).lower()
    high_priority = ["nuclear", "war", "missile", "attack", "gaza", "ukraine", "taiwan", "terror", "bomb", "footage", "video", "alert", "breaking", "sondakika", "operasyon", "şehit", "neutralized"]
    if any(w in text for w in high_priority): score += 50
    med_priority = ["turkey", "erdogan", "nato", "putin", "biden", "trump", "iran", "israel", "defense", "military", "troops", "bayraktar", "tb2", "kızılelma", "siha"]
    if any(w in text for w in med_priority): score += 30
    low_priority = ["trade", "economy", "deal", "meeting", "eu", "energy"]
    if any(w in text for w in low_priority): score += 10
    return score

def get_full_text(url):
    if "t.me" in url or "telegram" in url: return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text: return text[:2500] 
    except: pass
    return None

def fetch_news():
    print("🕵️‍♂️ AJAN 1: Veri toplanıyor...")
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for i, entry in enumerate(feed.entries[:3]):
                    title = entry.title
                    link = entry.link
                    summary = entry.summary[:300] if hasattr(entry, 'summary') else ""
                    if source.endswith("(Telegram)") and len(title) < 5: title = summary[:50] + "..."
                    score = calculate_priority_score(title, summary)
                    if "Telegram" in source: score += 15
                    elif i == 0: score += 10 
                    all_news.append({"source": source, "title": title, "link": link, "summary": summary, "score": score})
        except: continue

    all_news.sort(key=lambda x: x['score'], reverse=True)
    top_news = all_news[:7] 
    buffer = ""
    raw_links_html = "<ul>"
    current_keywords = []

    print("🕷️  AJAN 1: Detaylandırılıyor...")
    for news in top_news:
        full_text = get_full_text(news['link'])
        content_to_use = full_text if full_text else news['summary']
        content_type = "TAM METİN" if full_text else "ÖZET/MESAJ"
        icon = "🔥" if "Telegram" in news['source'] else ("🚨" if news['score'] >= 50 else "🔹")
        buffer += f"[{news['source']}] {icon} {news['title']} ({content_type})\nİÇERİK: {content_to_use[:1000]}...\nURL: {news['link']}\n\n"
        raw_links_html += f"<li><b>{news['source']}:</b> <a href='{news['link']}'>{news['title']}</a></li>"
        current_keywords.extend(news['title'].lower().split())
    
    raw_links_html += "</ul>"
    return buffer, raw_links_html, current_keywords

# ==========================================
# 3. HAFIZA
# ==========================================
def read_historical_memory(current_keywords):
    memory_buffer = ""
    files = glob.glob("ARSIV/*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    stop_words = ["the", "in", "at", "on", "for", "to", "and", "a", "of", "is", "with", "haber", "son", "dakika", "breaking", "news"]
    keywords = [k for k in current_keywords if len(k) > 4 and k not in stop_words]
    keywords = list(set(keywords))[:5]
    total_chars = 0
    SAFE_LIMIT = 12000 
    for file_path in files:
        if total_chars > SAFE_LIMIT: break
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            relevance = sum(content.lower().count(k) for k in keywords)
            if relevance > 0:
                memory_buffer += f"\n--- GEÇMİŞ ({os.path.basename(file_path)}) ---\n{content[:2000]}...\n"
                total_chars += len(content[:2000])
    if not memory_buffer: return "Arşivde ilgili kayıt bulunamadı."
    return memory_buffer

# ==========================================
# 4. HARİTA (AJAN 5)
# ==========================================
def draw_network_graph(text_data):
    print("🗺️ AJAN 5: Harita çiziyor...")
    prompt = f"Metindeki ülke/lider ilişkilerini 'Aktör1,Aktör2' formatında listele:\n{text_data[:4000]}"
    try:
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        relations = completion.choices[0].message.content.split('\n')
    except: relations = ["Türkiye,Dünya"] 

    G = nx.Graph()
    for line in relations:
        if "," in line:
            parts = line.split(',')
            if len(parts) >= 2:
                G.add_edge(parts[0].strip(), parts[1].strip())
    
    if G.number_of_nodes() == 0: G.add_edge("Türkiye", "Küresel Sistem")
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, k=1.5) 
    nx.draw_networkx_nodes(G, pos, node_size=2500, node_color='#2c3e50', alpha=0.9)
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.6, edge_color='#bdc3c7')
    nx.draw_networkx_labels(G, pos, font_size=9, font_color='white', font_weight='bold')
    plt.title("GÜNLÜK JEOPOLİTİK ETKİLEŞİM AĞI", fontsize=16, color='#c0392b')
    plt.axis('off')
    filename = "network_map.png"
    plt.savefig(filename, bbox_inches='tight', facecolor='#ecf0f1')
    plt.close()
    return filename

# ==========================================
# 5. AJANLI SİMÜLASYON (DİL DÜZELTMELİ)
# ==========================================
def run_agent_workflow(current_data, historical_memory):
    
    print("⏳ AJAN 2 ve 3 çalışıyor...")
    # Tarihçi ve Eleştirmen için Türkçe zorlaması
    historian_report = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": f"Tarihçi olarak bugünkü verileri ({current_data[:4000]}) geçmişle ({historical_memory}) kıyasla. Yanıtı SADECE Türkçe ver."}]
    ).choices[0].message.content

    critic_report = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": f"Kızıl Takım olarak ({current_data[:4000]}) verilerindeki Batı/Doğu/OSINT çelişkilerini sertçe eleştir. Yanıtı SADECE Türkçe ver."}]
    ).choices[0].message.content

    print("✍️ AJAN 4 (CHIEF EDITOR): Nihai raporu KATI KURALLARA GÖRE yazıyor...")
    
    # --- YENİ PROMPT (Dil Sızmasını Önleyen) ---
    final_system_prompt = """Sen Savaş Odası Başkanısın. Raporun dili %100 AKICI VE RESMİ İSTANBUL TÜRKÇESİ olmalıdır.
    
    KATI DİL KURALLARI (ASLA İHLAL ETME):
    1. ASLA yabancı kelime kullanma (Örn: 'Conflict' yerine 'Çatışma', 'Continuar' yerine 'Devam eden' yaz).
    2. ASLA Çince (东), Rusça veya İspanyolca karakter kullanma.
    3. Kelimeleri birleştirme (Örn: 'buConflict' YASAK, 'bu çatışma' DOĞRU).
    4. Cümleler düşük olmamalı, haber spikeri gibi net olmalı.
    
    KATI BİÇİM KURALLARI (FORMAT):
    1. ASLA düz paragraf yazma. Her şeyi <ul> ve <li> etiketleri ile maddeler halinde yaz.
    2. Her maddenin başına uygun bir emoji koy (📍, 💥, 🛑, 💰 gibi).
    3. Önemli isimleri (Putin, Erdoğan, NATO) ve ülkeleri mutlaka <b>KALIN</b> yaz.
    4. Her cümlenin sonuna kaynağını (<a href='URL'>Kaynak</a>) formatında ekle. Link yoksa o cümleyi yazma.
    
    RAPOR ŞABLONU (HTML):
    
    <h3 style="color:#c0392b; border-bottom: 2px solid #c0392b;">1. 🔥 SAHADAN SON DAKİKA (Telegram/OSINT)</h3>
    <ul>
      <li>💥 <b>Rusya</b> ordusu ilerliyor... (<a href='...'>Intel Slava</a>)</li>
      <li>📍 <b>Gazze</b> sokaklarında çatışma... (<a href='...'>Gaza Now</a>)</li>
    </ul>

    <h3 style="color:#2980b9; border-bottom: 2px solid #2980b9;">2. 🌍 JEOPOLİTİK RİSK ANALİZİ</h3>
    <ul>
      <li>🛑 <b>ABD</b> ve <b>Çin</b> arasında gerilim... (<a href='...'>CNN</a>)</li>
    </ul>

    <h3 style="color:#27ae60; border-bottom: 2px solid #27ae60;">3. 🤝 DİPLOMASİ VE EKONOMİ</h3>
    <ul>
      <li>💰 <b>Avrupa</b> borsaları düşüşte... (<a href='...'>Bloomberg</a>)</li>
    </ul>

    <h3 style="color:#8e44ad; border-bottom: 2px solid #8e44ad;">4. 👁️ KIZIL TAKIM: PROPAGANDA SAVAŞI</h3>
    <p><i>(Burada Denetçi Notlarını maddeler halinde özetle)</i></p>

    <h3 style="color:#d35400; border-bottom: 2px solid #d35400;">5. 🇹🇷 ANKARA İÇİN STRATEJİK TAVSİYE</h3>
    <ul>
      <li>👉 <b>Türkiye</b> bu durumda... yapmalıdır.</li>
    </ul>
    
    <div style="background-color:#fef9e7; color: black !important; padding:10px; border:1px solid #f1c40f; border-radius:5px;">
    <b style="color:#d35400;">🎲 GELECEK SENARYOLARI:</b>
    <ul style="color: black !important;">
       <li>%60 İhtimalle: ...</li>
       <li>%30 İhtimalle: ...</li>
    </ul>
    </div>
    """
    
    final_user_prompt = f"""
    HAM VERİLER: {current_data[:7000]}
    TARİHÇİ: {historian_report}
    DENETÇİ: {critic_report}
    
    Yukarıdaki verileri analiz et ve SADECE TÜRKÇE rapor yaz.
    """
    
    final_report = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": final_user_prompt}
        ],
        temperature=0.2 
    ).choices[0].message.content
    
    return final_report

# ==========================================
# 6. SES & MAİL & ARŞİV (DÜZELTİLDİ)
# ==========================================
async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio(text_content):
    print("🎙️ Seslendiriliyor...")
    clean_text = re.sub('<[^<]+?>', '', text_content)
    clean_text = re.sub(r'http\S+', '', clean_text)
    script = "Sayın Konsey Üyeleri. Küresel İstihbarat Raporu arz edilir. " + clean_text[:900]
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

# --- DOSYA ÜZERİNE YAZMA SORUNUNU ÇÖZEN FONKSİYON ---
def archive(report_body):
    # DÜZELTME: Dosya ismine SAAT ve DAKİKA eklendi (%H-%M)
    # Artık sabah ve akşam raporları farklı isimlerle kaydedilecek.
    date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = f"ARSIV/WarRoom_{date_str}.md"
    
    if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
    with open(path, "w", encoding="utf-8") as f: f.write(report_body)
    
    try:
        subprocess.run(["git", "config", "--global", "user.name", "WarRoom Bot"])
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "add", path])
        subprocess.run(["git", "commit", "-m", f"Simülasyon: {date_str}"])
        subprocess.run(["git", "push"])
    except: pass

def send_email_to_council(report_body, raw_links, audio_file, image_file):
    print(f"📧 Dağıtım Başlıyor: {len(ALICI_LISTESI)} Kişi")
    
    CANLI_DASHBOARD_LINKI = "https://siyasi-istihbarat-botu.streamlit.app" 
    
    saat = datetime.datetime.now().hour + 3 
    if 5 <= saat < 13:
        baslik_ek = "🌅 SABAH İSTİHBARATI (Morning Brief)"
        renk = "#2980b9"
    else:
        baslik_ek = "🌙 AKŞAM ÖZETİ VE ANALİZ (Evening Wrap-up)"
        renk = "#2c3e50"

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        
        for alici in ALICI_LISTESI:
            print(f"   -> Gönderiliyor: {alici}")
            msg = MIMEMultipart('related')
            msg['From'] = GMAIL_USER
            msg['To'] = alici 
            msg['Subject'] = f"🧠 {baslik_ek} - {datetime.date.today()}"
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            html_content = f"""
            <html><body style='font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; color:#333; line-height: 1.6; background-color: #f4f4f4; padding: 20px;'>
                <div style="max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                    
                    <div style="text-align: center; border-bottom: 3px solid {renk}; padding-bottom: 20px; margin-bottom: 20px;">
                        <h1 style="color:{renk}; margin: 0;">🛡️ SAVAŞ ODASI</h1>
                        <h3 style="color:#555; margin-top: 5px;">{baslik_ek}</h3>
                        
                        <a href="{CANLI_DASHBOARD_LINKI}" style="display: inline-block; background-color: #c0392b; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px;">
                           💬 YAPAY ZEKA İLE CANLI KONUŞ
                        </a>
                    </div>

                    <center>
                        <div style="border: 1px solid #ddd; padding: 5px; border-radius: 8px; display: inline-block;">
                            <h4 style="margin: 0 0 10px 0; color: #555;">🕸️ KÜRESEL İLİŞKİ AĞI</h4>
                            <img src="cid:network_map" style="width:100%; max-width:600px; border-radius:5px;">
                        </div>
                    </center>
                    <br>

                    <div style="font-size: 15px;">{report_body}</div>
                    
                    <br><hr style="border: 0; border-top: 1px solid #eee;">
                    
                    <div style="font-size:12px; color:#666; background:#f9f9f9; padding:15px; border-radius: 5px;">
                        <h4 style="margin-top: 0;">📚 DOĞRULANMIŞ KAYNAKÇA</h4>
                        {raw_links}
                    </div>
                    
                    <div style="text-align:center; margin-top:20px;">
                        <a href="{CANLI_DASHBOARD_LINKI}" style="color: #2980b9; font-weight: bold;">📊 Tüm Arşivi ve Detaylı Analizi Dashboard'da Gör</a>
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
        print("✅ Dağıtım tamamlandı!")
    except Exception as e:
        print(f"❌ Hata: {e}")

if __name__ == "__main__":
    raw_data, raw_links, current_keywords = fetch_news()
    memory = read_historical_memory(current_keywords)
    if len(raw_data) > 20:
        report = run_agent_workflow(raw_data, memory)
        graph_map = draw_network_graph(raw_data)
        archive(report)
        audio = create_audio(report)
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Veri yok.")
