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

# Liste Haline Getir
raw_mail_list = os.environ["ALICI_MAIL"]
ALICI_LISTESI = [email.strip() for email in raw_mail_list.split(',')]

client = Groq(api_key=GROQ_API_KEY)
SES_MODELI = "tr-TR-AhmetNeural"
plt.switch_backend('Agg')

# --- STRATEJİK KAYNAK HAVUZU (BATI + DOĞU BLOKU) ---
rss_sources = {
    # BATI MEDYASI
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'EuroNews': 'https://www.euronews.com/rss?format=mrss&level=theme&name=news',
    
    # ORTADOĞU & TÜRKİYE
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'SETA Vakfi': 'https://www.setav.org/feed/',
    'ORSAM': 'https://orsam.org.tr/rss',
    
    # DOĞU BLOKU & ASYA (YENİ EKLENENLER)
    'TASS (Russia)': 'https://tass.com/rss/v2.xml',           # Rusya Resmi Ajansı
    'China Daily': 'https://www.chinadaily.com.cn/rss/world_rss.xml', # Çin Resmi Sesi
    'Dawn (Pakistan)': 'https://www.dawn.com/feeds/home/'     # Pakistan'ın en büyük İngilizce gazetesi
}

KRITIK_AKTORLER = ["Turkey", "Türkiye", "Erdoğan", "Fidan", "Biden", "Putin", "Xi Jinping", "Zelensky", "Netanyahu", "Hamas", "NATO", "EU", "Iran", "China", "Russia", "Pakistan", "India"]

# ==========================================
# 2. İSTİHBARAT VE LİNK TOPLAMA
# ==========================================
def fetch_news():
    print("📡 Küresel Uydular (Batı ve Doğu) taranıyor...")
    buffer = ""
    raw_links_html = "<ul>" 
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=15) # Süreyi biraz uzattık (Çin/Rusya yavaş olabilir)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                # Her kaynaktan 2 haber alıyoruz
                for entry in feed.entries[:2]:
                    title = entry.title
                    link = entry.link
                    
                    # Haber özetini de alalım ki analiz güçlensin
                    summary = entry.summary[:100] if hasattr(entry, 'summary') else ""
                    
                    buffer += f"[{source}] {title} ({summary}) | URL: {link}\n"
                    raw_links_html += f"<li><b>{source}:</b> <a href='{link}'>{title}</a></li>"
        except Exception as e:
            print(f"⚠️ {source} erişilemedi: {e}")
            continue
    
    raw_links_html += "</ul>"
    return buffer, raw_links_html

# ==========================================
# 3. TARİHSEL HAFIZA (AKILLI KOTA SİSTEMİ) ⏳
# ==========================================
def read_historical_memory():
    print("⏳ Arşivler taranıyor (Akıllı Hafıza Modu)...")
    memory_buffer = ""
    
    # Tüm arşiv dosyalarını bul
    files = glob.glob("ARSIV/*.md")
    # En yeniden eskiye sırala
    files.sort(key=os.path.getmtime, reverse=True)
    
    total_chars = 0
    # Llama-3'ün hafızasını patlatmayacak güvenli sınır (karakter)
    SAFE_LIMIT = 12000 
    
    for file_path in files:
        if total_chars > SAFE_LIMIT:
            print(f"⚠️ Hafıza kotası ({SAFE_LIMIT} karakter) doldu. Daha eski kayıtlar atlanıyor.")
            break
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            filename = os.path.basename(file_path)
            
            # Her rapordan kritik 1500 karakteri al
            short_content = content[:1500]
            
            memory_buffer += f"\n--- GEÇMİŞ RAPOR ({filename}) ---\n{short_content}...\n"
            total_chars += len(short_content)
            
    if not memory_buffer:
        return "Henüz yeterli arşiv kaydı yok."
            
    return memory_buffer

# ==========================================
# 4. İLİŞKİ AĞI HARİTASI
# ==========================================
def draw_network_graph(text_data):
    print("🕸️ İlişki Ağı Haritalanıyor...")
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
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color='#c0392b', alpha=0.9) # Kırmızı renk (Doğu bloku etkisi)
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.5, edge_color='gray')
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
    plt.title("KÜRESEL GÜÇ DENGESİ AĞI", fontsize=15)
    plt.axis('off')
    filename = "network_map.png"
    plt.savefig(filename, bbox_inches='tight', facecolor='#fcf3cf') # Hafif sarı arka plan
    plt.close()
    return filename

# ==========================================
# 5. SAVAŞ ODASI SİMÜLASYONU
# ==========================================
def run_war_room_simulation(current_data, historical_memory):
    print("🧠 Konsey Toplanıyor (Batı ve Doğu verileriyle)...")
    if len(current_data) > 7000: current_data = current_data[:7000]

    system_prompt = """Sen Siyaset Bilimi Doktorası yapmış kıdemli bir yapay zeka sistemisin.
    Görevin: Bir "Savaş Odası Simülasyonu" yapmaktır.
    
    ÖZEL YETENEK (KÜRESEL BAKIŞ):
    Sana hem BATI (BBC, EuroNews) hem de DOĞU (TASS, China Daily) kaynaklarını verdim.
    Analiz yaparken bu iki blok arasındaki söylem farklarını (Propaganda savaşını) ortaya çıkar.
    
    ÖZEL YETENEK (HAFIZA):
    Geçmiş raporları tarayarak bugünkü olaylarla kıyasla (Trend Analizi).
    
    KURAL (KAYNAKÇA):
    Analizinde bahsettiğin olayların yanına mutlaka HTML formatında link ver.
    Örnek: "...Rusya iddiaları reddetti (<a href='URL'>TASS</a>)."
    
    ADIMLAR:
    1. "REALİST ŞAHİN": Güç, ordu ve tehdit odaklı analiz.
    2. "LİBERAL GÜVERCİN": Diplomasi ve ticaret odaklı analiz.
    3. "PROPAGANDA SAVAŞI": Batı ve Doğu medyası aynı olayı nasıl farklı anlatıyor?
    4. "TARİHSEL TESPİT (CHRONOS)": Geçmiş raporlarla kıyaslama.
    5. "BAŞKAN": Nihai karar.
    6. "GELECEK SİMÜLASYONU": Olasılıklar.
    """
    
    user_prompt = f"""
    BUGÜNÜN KÜRESEL VERİLERİ: 
    {current_data}
    
    HAFIZA (GEÇMİŞ RAPORLAR):
    {historical_memory}
    
    RAPOR ŞABLONU (HTML):
    <h3>🦅 REALİST KANAT</h3> <p>... (<a href='URL'>Kaynak</a>)</p>
    <h3>🕊️ LİBERAL KANAT</h3> <p>... (<a href='URL'>Kaynak</a>)</p>
    
    <div style='background-color:#fadbd8; padding:10px; border-left: 5px solid #c0392b;'>
    <h3>📢 PROPAGANDA SAVAŞI (Doğu vs Batı)</h3>
    <p>Batı medyası olayı ... olarak görürken, Rus/Çin kaynakları (<a href='URL'>TASS/China Daily</a>) durumu ... olarak sunuyor.</p>
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
            temperature=0.5, max_tokens=3500,
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
    script = "Sayın Konsey Üyeleri. Küresel İstihbarat özeti başlıyor. " + clean_text[:900]
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

# ==========================================
# 7. ARŞİVLEME
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

# ==========================================
# 8. MAİL GÖNDERME
# ==========================================
def send_email_to_council(report_body, raw_links, audio_file, image_file):
    print(f"📧 Konsey Üyelerine Gönderiliyor: {ALICI_LISTESI}")
    
    msg = MIMEMultipart('related')
    msg['From'] = GMAIL_USER
    msg['To'] = ", ".join(ALICI_LISTESI) 
    msg['Subject'] = f"🧠 KÜRESEL SAVAŞ ODASI RAPORU - {datetime.date.today()}"
    
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)

    html_content = f"""
    <html><body style='font-family: Arial, sans-serif; color:#333;'>
        <h1 style="color:#c0392b; text-align:center;">🛡️ KÜRESEL SAVAŞ ODASI</h1>
        <p style="text-align:center;"><i>"Propaganda Savaşları ve Stratejik Analiz"</i></p>
        <hr>
        <center>
            <h3>🕸️ GÜÇ DENGESİ AĞI</h3>
            <img src="cid:network_map" style="width:100%; max-width:600px; border:1px solid #ddd; padding:5px;">
        </center>
        
        {report_body}
        
        <br><hr>
        <div style="font-size:12px; color:#555; background:#f9f9f9; padding:10px;">
            <h3>📚 DOĞRULANMIŞ KAYNAKÇA (BATI & DOĞU)</h3>
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

# ==========================================
# ÇALIŞTIR
# ==========================================
if __name__ == "__main__":
    # 1. Veri topla
    raw_data, raw_links = fetch_news()
    
    # 2. Geçmişi hatırla (AKILLI KOTA SİSTEMİ)
    memory = read_historical_memory()
    
    if len(raw_data) > 20:
        # 3. Analiz et
        report = run_war_room_simulation(raw_data, memory)
        
        graph_map = draw_network_graph(raw_data)
        archive(report)
        audio = create_audio(report)
        
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Veri yok.")
