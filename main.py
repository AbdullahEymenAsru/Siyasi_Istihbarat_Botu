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

# KAYNAKLAR
rss_sources = {
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'EuroNews': 'https://www.euronews.com/rss?format=mrss&level=theme&name=news',
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'SETA Vakfi': 'https://www.setav.org/feed/',
    'ORSAM': 'https://orsam.org.tr/rss',
    'TASS (Russia)': 'https://tass.com/rss/v2.xml',
    'China Daily': 'https://www.chinadaily.com.cn/rss/world_rss.xml',
    'Dawn (Pakistan)': 'https://www.dawn.com/feeds/home/'
}

KRITIK_AKTORLER = ["Turkey", "Türkiye", "Erdoğan", "Fidan", "Biden", "Putin", "Xi Jinping", "Zelensky", "Netanyahu", "Hamas", "NATO", "EU", "Iran", "China", "Russia", "Pakistan", "India"]

# ==========================================
# 2. AKILLI HABER SEÇİCİ (EDİTORYAL ALGORİTMA) 🧠
# ==========================================
def calculate_priority_score(title, summary):
    """Haberin stratejik önemini puanlar"""
    score = 0
    text = (title + " " + summary).lower()
    
    # 1. SEVİYE: KRİTİK TEHDİTLER (+50 Puan)
    high_priority = ["nuclear", "nükleer", "war", "savaş", "missile", "füze", "attack", "saldırı", "gaza", "gazze", "ukraine", "ukrayna", "taiwan"]
    if any(w in text for w in high_priority): score += 50
    
    # 2. SEVİYE: STRATEJİK İLGİ (+30 Puan)
    med_priority = ["turkey", "türkiye", "erdogan", "nato", "putin", "biden", "xi jinping", "f-16", "s-400", "pkk", "ypg", "syria", "suriye"]
    if any(w in text for w in med_priority): score += 30
    
    # 3. SEVİYE: EKONOMİ VE DİPLOMASİ (+10 Puan)
    low_priority = ["trade", "ticaret", "economy", "ekonomi", "deal", "anlaşma", "meeting", "toplantı", "eu", "ab"]
    if any(w in text for w in low_priority): score += 10
    
    return score

def fetch_news():
    print("📡 Uydular taranıyor (Akıllı Filtreleme Devrede)...")
    all_news = [] # Tüm haberleri burada toplayacağız
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            feed = feedparser.parse(resp.content)
            
            if feed.entries:
                # Her kaynaktan 5 haber çek (Havuzu genişlet)
                for entry in feed.entries[:5]:
                    title = entry.title
                    link = entry.link
                    summary = entry.summary[:200] if hasattr(entry, 'summary') else ""
                    
                    # Haberi Puanla
                    score = calculate_priority_score(title, summary)
                    
                    # Listeye ekle
                    all_news.append({
                        "source": source,
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "score": score
                    })
        except: continue

    # Puanı en yüksekten düşüğe sırala
    all_news.sort(key=lambda x: x['score'], reverse=True)
    
    # En yüksek puanlı 5 haberi seç (Burası Botun Karar Mekanizmasıdır)
    top_news = all_news[:5]
    
    buffer = ""
    raw_links_html = "<ul>"
    
    for news in top_news:
        # Seçilen haberleri işle
        icon = "🚨" if news['score'] >= 50 else "🔹"
        buffer += f"[{news['source']}] {icon} {news['title']} | URL: {news['link']}\n"
        raw_links_html += f"<li><b>{news['source']} ({news['score']} Puan):</b> <a href='{news['link']}'>{news['title']}</a></li>"
    
    raw_links_html += "</ul>"
    
    print(f"✅ Toplam {len(all_news)} haber tarandı, en kritik {len(top_news)} tanesi seçildi.")
    return buffer, raw_links_html

# ==========================================
# 3. TARİHSEL HAFIZA
# ==========================================
def read_historical_memory():
    print("⏳ Arşivler taranıyor...")
    memory_buffer = ""
    files = glob.glob("ARSIV/*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    total_chars = 0
    SAFE_LIMIT = 12000 
    
    for file_path in files:
        if total_chars > SAFE_LIMIT: break
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            filename = os.path.basename(file_path)
            short_content = content[:1500]
            memory_buffer += f"\n--- GEÇMİŞ ({filename}) ---\n{short_content}...\n"
            total_chars += len(short_content)
            
    if not memory_buffer: return "Yeterli kayıt yok."
    return memory_buffer

# ==========================================
# 4. AĞ HARİTASI
# ==========================================
def draw_network_graph(text_data):
    print("🕸️ Ağ Haritası Çiziliyor...")
    G = nx.Graph()
    sentences = text_data.split('\n')
    for sent in sentences:
        found = [actor for actor in KRITIK_AKTORLER if actor.lower() in sent.lower()]
        if len(found) > 1:
            for i in range(len(found)):
                for j in range(i+1, len(found)):
                    G.add_edge(found[i], found[j])
    
    if G.number_of_nodes() == 0: G.add_edge("Türkiye", "Dünya")

    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(G, k=0.8)
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color='#c0392b', alpha=0.9)
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.5, edge_color='gray')
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
    plt.title("KÜRESEL GÜÇ DENGESİ", fontsize=15)
    plt.axis('off')
    filename = "network_map.png"
    plt.savefig(filename, bbox_inches='tight', facecolor='#fcf3cf')
    plt.close()
    return filename

# ==========================================
# 5. SAVAŞ ODASI
# ==========================================
def run_war_room_simulation(current_data, historical_memory):
    print("🧠 Konsey Toplanıyor...")
    if len(current_data) > 7000: current_data = current_data[:7000]

    system_prompt = """Sen Siyaset Bilimi Doktorası yapmış kıdemli bir yapay zeka sistemisin.
    Görevin: "Savaş Odası Simülasyonu" yapmaktır.
    
    ÖZEL YETENEK (BATI vs DOĞU):
    BBC/EuroNews (Batı) ile TASS/ChinaDaily (Doğu) arasındaki söylem farklarını analiz et.
    
    ÖZEL YETENEK (HAFIZA):
    Bugünü geçmiş raporlarla kıyasla.
    
    KURAL (LİNK):
    Olayları mutlaka link vererek anlat: "...dedi (<a href='URL'>Kaynak</a>)."
    
    ADIMLAR:
    1. "REALİST ŞAHİN": Tehdit odaklı.
    2. "LİBERAL GÜVERCİN": Diplomasi odaklı.
    3. "PROPAGANDA SAVAŞI": Batı ne diyor, Doğu ne diyor?
    4. "TARİHSEL TESPİT": Arşiv analizi.
    5. "BAŞKAN": Nihai strateji.
    6. "GELECEK SİMÜLASYONU": Olasılıklar.
    """
    
    user_prompt = f"""
    SEÇİLMİŞ KRİTİK VERİLER: {current_data}
    HAFIZA: {historical_memory}
    
    RAPOR ŞABLONU (HTML):
    <h3>🦅 REALİST KANAT</h3> <p>... (<a href='URL'>Kaynak</a>)</p>
    <h3>🕊️ LİBERAL KANAT</h3> <p>... (<a href='URL'>Kaynak</a>)</p>
    
    <div style='background-color:#fadbd8; padding:10px; border-left: 5px solid #c0392b;'>
    <h3>📢 PROPAGANDA SAVAŞI (Doğu vs Batı)</h3>
    <p>...</p>
    </div>

    <div style='background-color:#e8f8f5; padding:10px; border-left: 5px solid #1abc9c;'>
    <h3>⏳ TARİHSEL TESPİT (Chronos)</h3>
    <p>Arşivime göre...</p>
    </div>
    
    <h3>🇹🇷 BAŞKANIN KARARI</h3> <p>...</p>
    
    <div style='background-color:#fef9e7; padding:15px; border-left: 5px solid #f1c40f;'>
    <h3>🎲 GELECEK SİMÜLASYONU</h3>
    <ul><li>...</li></ul>
    </div>"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7,
            max_tokens=3500,
        )
        return completion.choices[0].message.content
    except Exception as e: return f"Hata: {e}"

# ==========================================
# 6. SESLİ ASİSTAN
# ==========================================
async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio(text_content):
    print("🎙️ Seslendiriliyor...")
    clean_text = re.sub('<[^<]+?>', '', text_content)
    clean_text = re.sub(r'http\S+', '', clean_text)
    clean_text = clean_text.replace("🦅", "").replace("🕊️", "").replace("🎲", "").replace("⏳", "").replace("📢", "")
    script = "Sayın Konsey Üyeleri. Küresel İstihbarat özeti. " + clean_text[:900]
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

# ==========================================
# 7. ARŞİVLEME & MAİL
# ==========================================
def archive(report_body):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
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
    print(f"📧 Gönderiliyor: {ALICI_LISTESI}")
    msg = MIMEMultipart('related')
    msg['From'] = GMAIL_USER
    msg['To'] = ", ".join(ALICI_LISTESI) 
    msg['Subject'] = f"🧠 KÜRESEL SAVAŞ ODASI - {datetime.date.today()}"
    
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)

    html_content = f"""
    <html><body style='font-family: Arial, sans-serif; color:#333;'>
        <h1 style="color:#c0392b; text-align:center;">🛡️ KÜRESEL SAVAŞ ODASI</h1>
        <p style="text-align:center;"><i>"Algoritmik İstihbarat Seçimi ile Hazırlanmıştır"</i></p>
        <hr>
        <center>
            <h3>🕸️ GÜÇ DENGESİ AĞI</h3>
            <img src="cid:network_map" style="width:100%; max-width:600px; border:1px solid #ddd; padding:5px;">
        </center>
        {report_body}
        <br><hr>
        <div style="font-size:12px; color:#555; background:#f9f9f9; padding:10px;">
            <h3>📚 SEÇİLEN STRATEJİK KAYNAKLAR</h3>
            {raw_links}
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

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, ALICI_LISTESI, msg.as_string())
        server.quit()
        print("✅ Başarıyla iletildi!")
    except Exception as e:
        print(f"❌ Mail Hatası: {e}")

if __name__ == "__main__":
    raw_data, raw_links = fetch_news()
    memory = read_historical_memory()
    
    if len(raw_data) > 20:
        report = run_war_room_simulation(raw_data, memory)
        graph_map = draw_network_graph(raw_data)
        archive(report)
        audio = create_audio(report)
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Veri yok.")
