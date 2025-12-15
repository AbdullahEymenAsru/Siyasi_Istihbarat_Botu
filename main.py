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
# 2. İSTİHBARAT VE LİNK TOPLAMA
# ==========================================
def fetch_news():
    print("📡 Uydular taranıyor...")
    buffer = ""
    # Linkleri ayrıca saklamak için liste (Garanti Yöntemi İçin)
    raw_links_html = "<ul>" 
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for entry in feed.entries[:2]:
                    title = entry.title
                    link = entry.link
                    # AI'ya gidecek veri
                    buffer += f"[{source}] {title} | URL: {link}\n"
                    # En alta eklenecek garanti liste
                    raw_links_html += f"<li><b>{source}:</b> <a href='{link}'>{title}</a></li>"
        except: continue
    
    raw_links_html += "</ul>"
    return buffer, raw_links_html

# ==========================================
# 3. İLİŞKİ AĞI HARİTASI
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
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color='#3498db', alpha=0.9)
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.5, edge_color='gray')
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
    plt.title("GÜNLÜK JEOPOLİTİK İLİŞKİ AĞI", fontsize=15)
    plt.axis('off')
    filename = "network_map.png"
    plt.savefig(filename, bbox_inches='tight', facecolor='#ecf0f1')
    plt.close()
    return filename

# ==========================================
# 4. SAVAŞ ODASI (LINK ZORUNLULUĞU İLE)
# ==========================================
def run_war_room_simulation(text_data):
    print("🧠 Konsey Toplanıyor...")
    if len(text_data) > 7000: text_data = text_data[:7000]

    system_prompt = """Sen Siyaset Bilimi Doktorası yapmış kıdemli bir yapay zeka sistemisin.
    Görevin: Bir "Savaş Odası Simülasyonu" yapmaktır.
    
    ÇOK ÖNEMLİ KURAL (KAYNAKÇA):
    Analizinde bahsettiğin olayların yanına mutlaka HTML formatında link ver.
    Örnek: "...saldırı gerçekleşti (<a href='URL'>BBC</a>)."
    Link vermeden asla kesin konuşma.
    
    ADIMLAR:
    1. "REALİST ŞAHİN": Güç ve tehdit odaklı analiz.
    2. "LİBERAL GÜVERCİN": Diplomasi ve hukuk odaklı analiz.
    3. "BAŞKAN": Nihai karar ve strateji.
    4. "OYUN TEORİSİ": Gelecek senaryoları.
    """
    
    user_prompt = f"""VERİLER: {text_data}
    
    RAPOR ŞABLONU (HTML):
    <h3>🦅 REALİST KANAT</h3> <p>Analiz... (<a href='URL'>Kaynak</a>)</p>
    <h3>🕊️ LİBERAL KANAT</h3> <p>Analiz... (<a href='URL'>Kaynak</a>)</p>
    <h3>🇹🇷 BAŞKANIN KARARI</h3> <p>...</p>
    <div style='background-color:#fef9e7; padding:15px; border-left: 5px solid #f1c40f;'>
    <h3>🎲 GELECEK SİMÜLASYONU</h3>
    <ul><li>...</li></ul>
    </div>"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.5, max_tokens=2500,
        )
        return completion.choices[0].message.content
    except Exception as e: return f"Hata: {e}"

# ==========================================
# 5. SESLİ ASİSTAN
# ==========================================
async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio(text_content):
    print("🎙️ Seslendiriliyor...")
    clean_text = re.sub('<[^<]+?>', '', text_content)
    clean_text = re.sub(r'http\S+', '', clean_text)
    clean_text = clean_text.replace("🦅", "").replace("🕊️", "").replace("🎲", "")
    script = "Sayın Konsey Üyeleri. Savaş Odası analizi başlıyor. " + clean_text[:800]
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

# ==========================================
# 6. ARŞİVLEME
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
# 7. MAİL GÖNDERME (KAYNAKÇA EKLENTİLİ)
# ==========================================
def send_email_to_council(report_body, raw_links, audio_file, image_file):
    print(f"📧 Konsey Üyelerine Gönderiliyor: {ALICI_LISTESI}")
    
    msg = MIMEMultipart('related')
    msg['From'] = GMAIL_USER
    msg['To'] = ", ".join(ALICI_LISTESI) 
    msg['Subject'] = f"🧠 SAVAŞ ODASI KONSEY RAPORU - {datetime.date.today()}"
    
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)

    # İŞTE BURADA GARANTİ LİNKLERİ EKLİYORUZ (raw_links)
    html_content = f"""
    <html><body style='font-family: Arial, sans-serif; color:#333;'>
        <h1 style="color:#c0392b; text-align:center;">🛡️ SANAL SAVAŞ ODASI</h1>
        <p style="text-align:center;"><i>"Gizli Dağıtım: {len(ALICI_LISTESI)} Konsey Üyesi"</i></p>
        <hr>
        <center>
            <h3>🕸️ İLİŞKİ AĞI HARİTASI</h3>
            <img src="cid:network_map" style="width:100%; max-width:600px; border:1px solid #ddd; padding:5px;">
        </center>
        
        {report_body}
        
        <br><hr>
        <div style="font-size:12px; color:#555; background:#f9f9f9; padding:10px;">
            <h3>📚 DOĞRULANMIŞ KAYNAKÇA (REFERANS LİSTESİ)</h3>
            <p>Yapay zeka analizinde kullanılan ham veriler:</p>
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
    # raw_data ve raw_links'i ayrı ayrı alıyoruz
    raw_data, raw_links = fetch_news()
    
    if len(raw_data) > 20:
        report = run_war_room_simulation(raw_data)
        graph_map = draw_network_graph(raw_data)
        archive(report)
        audio = create_audio(report)
        
        # raw_links'i de mail fonksiyonuna gönderiyoruz
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Veri yok.")
