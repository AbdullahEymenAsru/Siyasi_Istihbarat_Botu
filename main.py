import feedparser
import requests
import smtplib
import os
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
# 1. AYARLAR VE GİZLİ SERVİS GİRİŞİ
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
ALICI_MAIL = os.environ["ALICI_MAIL"]

client = Groq(api_key=GROQ_API_KEY)
SES_MODELI = "tr-TR-AhmetNeural"

# Grafik çizimi için arka plan ayarı (Sunucuda ekran olmadığı için 'Agg' modu şart)
plt.switch_backend('Agg')

rss_sources = {
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'EuroNews': 'https://www.euronews.com/rss?format=mrss&level=theme&name=news',
    'SETA Vakfi': 'https://www.setav.org/feed/',
    'ORSAM': 'https://orsam.org.tr/rss'
}

KRITIK_AKTORLER = ["Turkey", "Türkiye", "Erdoğan", "Fidan", "Biden", "Putin", "Zelensky", "Netanyahu", "Hamas", "NATO", "EU", "Iran", "China"]

# ==========================================
# 2. İSTİHBARAT TOPLAMA
# ==========================================
def fetch_news():
    print("📡 Uydular taranıyor...")
    buffer = ""
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for entry in feed.entries[:2]: # Her kaynaktan 2 haber (Hız için)
                    title = entry.title
                    link = entry.link
                    buffer += f"[{source}] {title} | URL: {link}\n"
        except:
            continue
    return buffer

# ==========================================
# 3. LEVEL 3: İLİŞKİ AĞI GÖRSELLEŞTİRME 🕸️
# ==========================================
def draw_network_graph(text_data):
    print("🕸️ İlişki Ağı Haritalanıyor...")
    G = nx.Graph()
    
    # Metni cümlelere böl
    sentences = text_data.split('\n')
    
    # Basit Algoritma: Aynı haber satırında geçen iki aktörü birbirine bağla
    for sent in sentences:
        found = [actor for actor in KRITIK_AKTORLER if actor.lower() in sent.lower()]
        # İkili kombinasyonları bağla
        if len(found) > 1:
            for i in range(len(found)):
                for j in range(i+1, len(found)):
                    G.add_edge(found[i], found[j])

    # Eğer bağlantı bulunamazsa boş grafik çizmemek için manuel ekleme
    if G.number_of_nodes() == 0:
        G.add_edge("Türkiye", "Dünya")

    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(G, k=0.8) # Esnek yerleşim
    
    # Düğümler
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color='#3498db', alpha=0.9)
    # Kenarlar
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.5, edge_color='gray')
    # İsimler
    nx.draw_networkx_labels(G, pos, font_size=10, font_family='sans-serif', font_weight='bold', font_color='white')
    
    plt.title("GÜNLÜK JEOPOLİTİK İLİŞKİ AĞI", fontsize=15)
    plt.axis('off')
    
    filename = "network_map.png"
    plt.savefig(filename, bbox_inches='tight', facecolor='#ecf0f1')
    plt.close()
    return filename

# ==========================================
# 4. LEVEL 1 & 4: SANAL KONSEY VE SİMÜLASYON 🧠🎲
# ==========================================
def run_war_room_simulation(text_data):
    print("🧠 Savaş Odası (War Room) Toplanıyor...")
    if len(text_data) > 7000: text_data = text_data[:7000]

    system_prompt = """Sen Siyaset Bilimi Doktorası yapmış kıdemli bir yapay zeka sistemisin.
    Görevin standart bir özet çıkarmak DEĞİL. Bir "Savaş Odası Simülasyonu" yapmaktır.
    
    SİMÜLASYON ADIMLARI:
    1. Önce "REALİST ŞAHİN" (The Hawk) görüşünü yaz: Güç, ordu ve tehdit odaklı analiz et.
    2. Sonra "LİBERAL GÜVERCİN" (The Dove) görüşünü yaz: Diplomasi, hukuk ve ticaret odaklı analiz et.
    3. Sonra "BAŞKAN" (The President) olarak nihai kararı ver ve Türkiye için strateji belirle.
    4. En sona "OYUN TEORİSİ" (Game Theory) tablosu koy: Gelecek senaryolarına yüzdelik ihtimal ver.
    
    ÇIKTI FORMATI (HTML):
    Raporu HTML tagleri ile süsle. Linkleri <a href='URL'>Kaynak</a> şeklinde ver.
    """
    
    user_prompt = f"""
    İSTİHBARAT VERİLERİ:
    {text_data}
    
    RAPOR ŞABLONU:
    <h3>🦅 REALİST KANAT (Güvenlik Odağı)</h3>
    <p>...</p>
    
    <h3>🕊️ LİBERAL KANAT (Diplomasi Odağı)</h3>
    <p>...</p>
    
    <h3>🇹🇷 BAŞKANIN STRATEJİSİ (Nihai Karar)</h3>
    <p>...</p>
    
    <div style='background-color:#fef9e7; padding:15px; border-left: 5px solid #f1c40f;'>
    <h3>🎲 GELECEK SİMÜLASYONU (Monte Carlo Tahmini)</h3>
    <ul>
      <li><b>Senaryo A (%? Olasılık):</b> ...</li>
      <li><b>Senaryo B (%? Olasılık):</b> ...</li>
      <li><b>Siyah Kuğu (%5 Olasılık):</b> (Beklenmedik felaket senaryosu)</li>
    </ul>
    </div>
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.6, # Biraz yaratıcılık lazım
            max_tokens=2500,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Simülasyon Hatası: {e}"

# ==========================================
# 5. SESLİ ASİSTAN
# ==========================================
async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio(text_content):
    print("🎙️ Neural Ses Hazırlanıyor...")
    clean_text = re.sub('<[^<]+?>', '', text_content)
    clean_text = re.sub(r'http\S+', '', clean_text)
    clean_text = clean_text.replace("🦅", "").replace("🕊️", "").replace("🎲", "")
    
    script = "Sayın Eymen. Savaş Odası toplandı. İşte konseyin bugünkü analizi. " + clean_text[:800] + "... Detaylar rapordadır."
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except:
        return None

# ==========================================
# 6. ARŞİV VE MAİL
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

def send_email(report_body, audio_file, image_file):
    msg = MIMEMultipart('related') # Resim gömmek için 'related'
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL
    msg['Subject'] = f"🧠 SAVAŞ ODASI SİMÜLASYONU - {datetime.date.today()}"
    
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)

    # HTML İçeriği (Resmi CID ile gömüyoruz)
    html_content = f"""
    <html><body style='font-family: Arial, sans-serif; color:#333;'>
        <h1 style="color:#c0392b; text-align:center;">🛡️ SANAL SAVAŞ ODASI</h1>
        <p style="text-align:center;"><i>"Si vis pacem, para bellum" (Barış istiyorsan, savaşa hazır ol)</i></p>
        <hr>
        
        <center>
            <h3>🕸️ GÜNLÜK İLİŞKİ AĞI</h3>
            <img src="cid:network_map" style="width:100%; max-width:600px; border:1px solid #ddd; padding:5px;">
        </center>
        
        {report_body}
        
        <br><hr>
        <p><b>Ekler:</b> Sesli Brifing (MP3) ve Yüksek Çözünürlüklü Harita.</p>
    </body></html>
    """
    msg_alternative.attach(MIMEText(html_content, 'html'))

    # 1. Resmi Göm (Inline Image)
    if image_file and os.path.exists(image_file):
        with open(image_file, 'rb') as f:
            img = MIMEImage(f.read())
            img.add_header('Content-ID', '<network_map>') # HTML'deki cid ile aynı olmalı
            img.add_header('Content-Disposition', 'inline', filename=image_file)
            msg.attach(img)

    # 2. Sesi Ekle (Attachment)
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
        server.sendmail(GMAIL_USER, ALICI_MAIL, msg.as_string())
        server.quit()
        print("✅ Simülasyon Sonuçları Gönderildi!")
    except Exception as e:
        print(f"❌ Mail Hatası: {e}")

# ==========================================
# ÇALIŞTIR
# ==========================================
if __name__ == "__main__":
    raw_data = fetch_news()
    if len(raw_data) > 20:
        # 1. Konsey Toplanıyor (AI Analizi)
        report = run_war_room_simulation(raw_data)
        
        # 2. Harita Çiziliyor (Knowledge Graph)
        graph_map = draw_network_graph(raw_data)
        
        # 3. Arşivleniyor
        archive(report)
        
        # 4. Seslendiriliyor
        audio = create_audio(report)
        
        # 5. Gönderiliyor
        send_email(report, audio, graph_map)
    else:
        print("Veri yok.")
