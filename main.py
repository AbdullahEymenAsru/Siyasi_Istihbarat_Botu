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
# 2. AJAN 1: RESEARCHER (VERİ TOPLAYICI) 🕵️‍♂️
# ==========================================
def calculate_priority_score(title, summary):
    score = 0
    text = (title + " " + summary).lower()
    
    high_priority = ["nuclear", "nükleer", "war", "savaş", "missile", "füze", "attack", "saldırı", "gaza", "gazze", "ukraine", "ukrayna", "taiwan"]
    if any(w in text for w in high_priority): score += 50
    
    med_priority = ["turkey", "türkiye", "erdogan", "nato", "putin", "biden", "xi jinping", "f-16", "s-400", "pkk", "ypg", "syria", "suriye"]
    if any(w in text for w in med_priority): score += 30
    
    low_priority = ["trade", "ticaret", "economy", "ekonomi", "deal", "anlaşma", "meeting", "toplantı", "eu", "ab"]
    if any(w in text for w in low_priority): score += 10
    
    return score

def fetch_news():
    print("🕵️‍♂️ AJAN 1 (RESEARCHER): Sahadan veri topluyor...")
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for entry in feed.entries[:5]:
                    title = entry.title
                    link = entry.link
                    summary = entry.summary[:200] if hasattr(entry, 'summary') else ""
                    score = calculate_priority_score(title, summary)
                    all_news.append({"source": source, "title": title, "link": link, "summary": summary, "score": score})
        except: continue

    all_news.sort(key=lambda x: x['score'], reverse=True)
    top_news = all_news[:5]
    
    buffer = ""
    raw_links_html = "<ul>"
    for news in top_news:
        icon = "🚨" if news['score'] >= 50 else "🔹"
        buffer += f"[{news['source']}] {icon} {news['title']} | URL: {news['link']}\n"
        raw_links_html += f"<li><b>{news['source']} ({news['score']} Puan):</b> <a href='{news['link']}'>{news['title']}</a></li>"
    raw_links_html += "</ul>"
    
    return buffer, raw_links_html

# ==========================================
# 3. HAFIZA MODÜLÜ (DATA BANK)
# ==========================================
def read_historical_memory():
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
# 4. GÖRSELLEŞTİRME (HARİTACI)
# ==========================================
def draw_network_graph(text_data):
    print("🗺️ AJAN 5 (VISUALIZER): Harita çiziyor...")
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
# 5. AJANLI SİMÜLASYON (MULTI-AGENT WORKFLOW) 🤖🤖🤖
# ==========================================
def run_agent_workflow(current_data, historical_memory):
    
    # --- ADIM 1: AJAN 2 (HISTORIAN) ---
    print("⏳ AJAN 2 (HISTORIAN): Geçmişi tarıyor...")
    historian_prompt = f"""
    Sen uzman bir Tarihçisin. Görevin bugünkü haberlerle geçmiş raporları kıyaslamak.
    
    BUGÜN: {current_data}
    GEÇMİŞ: {historical_memory}
    
    GÖREV: Sadece ve sadece geçmişle bugün arasındaki BENZERLİKLERİ veya ÇELİŞKİLERİ maddeler halinde yaz.
    Yorum yapma, sadece tespit yap.
    """
    history_analysis = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": historian_prompt}]
    ).choices[0].message.content

    # --- ADIM 2: AJAN 3 (THE CRITIC) ---
    print("⚖️ AJAN 3 (THE CRITIC): Analizi denetliyor...")
    critic_prompt = f"""
    Sen 'Kızıl Takım' (Red Team) liderisin. Görevin analizlerdeki açıkları bulmak.
    
    VERİLER: {current_data}
    
    GÖREV: Bu verilerde Batı veya Doğu medyasının manipülasyonu var mı? 
    Hangi kaynaklar birbirini yalanlıyor? Çok sert ve şüpheci bir dille kısa bir 'İç İstihbarat Notu' yaz.
    """
    critic_analysis = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": critic_prompt}]
    ).choices[0].message.content

    # --- ADIM 3: AJAN 4 (CHIEF EDITOR) ---
    print("✍️ AJAN 4 (CHIEF EDITOR): Nihai raporu yazıyor...")
    
    final_system_prompt = """Sen Savaş Odası'nın Başkanısın. 
    Tarihçi ve Denetçi'den gelen raporları birleştirip NİHAİ STRATEJİK RAPORU yazacaksın.
    
    FORMAT: HTML kullan.
    ÜSLUP: Akademik, net, yönlendirici.
    
    BÖLÜMLER:
    1. REALİST KANAT (Güvenlik)
    2. LİBERAL KANAT (Diplomasi)
    3. PROPAGANDA SAVAŞI (Denetçi Notları buraya)
    4. TARİHSEL TESPİT (Tarihçi Notları buraya)
    5. BAŞKANIN KARARI (Senin hükmün)
    6. GELECEK SİMÜLASYONU (% Olasılıklar)
    """
    
    final_user_prompt = f"""
    HAM VERİLER: {current_data}
    TARİHÇİ RAPORU: {history_analysis}
    DENETÇİ NOTU: {critic_analysis}
    """
    
    final_report = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": final_user_prompt}
        ],
        temperature=0.6
    ).choices[0].message.content
    
    return final_report

# ==========================================
# 6. SES & MAİL
# ==========================================
async def generate_voice(text, output_file):
    communicate = edge_tts.Communicate(text, SES_MODELI)
    await communicate.save(output_file)

def create_audio(text_content):
    print("🎙️ Seslendiriliyor...")
    clean_text = re.sub('<[^<]+?>', '', text_content)
    clean_text = re.sub(r'http\S+', '', clean_text)
    script = "Sayın Konsey Üyeleri. Ajan raporları tamamlandı. " + clean_text[:900]
    filename = "Gunluk_Brifing.mp3"
    try:
        asyncio.run(generate_voice(script, filename))
        return filename
    except: return None

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
    msg['Subject'] = f"🧠 ÇOKLU AJAN SİSTEMİ RAPORU - {datetime.date.today()}"
    
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)

    html_content = f"""
    <html><body style='font-family: Arial, sans-serif; color:#333;'>
        <h1 style="color:#c0392b; text-align:center;">🛡️ SAVAŞ ODASI: ÖZEL TİM</h1>
        <p style="text-align:center;"><i>"Researcher > Historian > Critic > Editor"</i></p>
        <hr>
        <center>
            <h3>🕸️ GÜÇ DENGESİ AĞI</h3>
            <img src="cid:network_map" style="width:100%; max-width:600px; border:1px solid #ddd; padding:5px;">
        </center>
        {report_body}
        <br><hr>
        <div style="font-size:12px; color:#555; background:#f9f9f9; padding:10px;">
            <h3>📚 AJAN 1 TARAFINDAN TOPLANAN KAYNAKLAR</h3>
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
    # ADIM 1: ARAŞTIRMACI (Researcher)
    raw_data, raw_links = fetch_news()
    
    # ADIM 2: HAFIZA ÇAĞIRMA
    memory = read_historical_memory()
    
    if len(raw_data) > 20:
        # ADIM 3: ÇOKLU AJAN İŞ AKIŞI (Historian -> Critic -> Editor)
        report = run_agent_workflow(raw_data, memory)
        
        # ADIM 4: GÖRSELLEŞTİRİCİ (Visualizer)
        graph_map = draw_network_graph(raw_data)
        
        # ADIM 5: ARŞİV VE DAĞITIM
        archive(report)
        audio = create_audio(report)
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Veri yok.")
