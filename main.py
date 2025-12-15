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

# --- DEVASA STRATEJİK KAYNAK HAVUZU (v21.0) ---
rss_sources = {
    # --- BATI VE AVRUPA (NATO MERKEZLİ) ---
    'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'CNN International': 'http://rss.cnn.com/rss/edition.rss',
    'Voice of America (VOA)': 'https://www.voanews.com/api/zg$oq_et$p',
    'Foreign Policy': 'https://foreignpolicy.com/feed/',
    'Deutsche Welle (Germany)': 'https://rss.dw.com/xml/rss-en-all', # YENİ (Avrupa'nın Sesi)
    
    # --- TÜRKİYE VE ORTADOĞU ---
    'TRT World': 'https://www.trtworld.com/rss',
    'Turkiye Arastirmalari Vakfi': 'https://tav.org.tr/feed/',
    'SETA Vakfi': 'https://www.setav.org/feed/',
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'Times of Israel': 'https://www.timesofisrael.com/feed/', # YENİ (Tel Aviv Perspektifi)
    'Tehran Times (Iran)': 'https://www.tehrantimes.com/rss', # YENİ (Tahran/Direniş Ekseni)
    
    # --- ASYA - PASİFİK VE DOĞU BLOKU ---
    'TASS (Russia)': 'https://tass.com/rss/v2.xml',
    'China Daily': 'https://www.chinadaily.com.cn/rss/world_rss.xml',
    'Yonhap (South Korea)': 'https://en.yna.co.kr/RSS/news.xml', # YENİ (Seul/Teknoloji/Kuzey Kore)
    'Dawn (Pakistan)': 'https://www.dawn.com/feeds/home/',
    'Times of India': 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms' # YENİ (Yeni Süper Güç)
}

# Kritik Aktör listesini de genişlettik (Seul, Tahran, Delhi vb. için)
KRITIK_AKTORLER = ["Turkey", "Türkiye", "Erdoğan", "Fidan", "Biden", "Trump", "Putin", "Xi Jinping", "Zelensky", "Netanyahu", "Hamas", "Hezbollah", "NATO", "EU", "Iran", "China", "Russia", "Pakistan", "India", "Greece", "South Korea", "North Korea", "Kim Jong Un"]

# ==========================================
# 2. AJAN 1: RESEARCHER (VERİ TOPLAYICI)
# ==========================================
def calculate_priority_score(title, summary):
    score = 0
    text = (title + " " + summary).lower()
    
    # 1. SEVİYE: KRİTİK TEHDİTLER (+50 Puan)
    high_priority = ["nuclear", "nükleer", "war", "savaş", "missile", "füze", "attack", "saldırı", "gaza", "gazze", "ukraine", "ukrayna", "taiwan", "terror", "terör", "bomb"]
    if any(w in text for w in high_priority): score += 50
    
    # 2. SEVİYE: STRATEJİK İLGİ (+30 Puan)
    med_priority = ["turkey", "türkiye", "erdogan", "nato", "putin", "biden", "trump", "xi jinping", "kim jong un", "iran", "israel", "defense", "savunma", "s-400", "f-16", "f-35"]
    if any(w in text for w in med_priority): score += 30
    
    # 3. SEVİYE: EKONOMİ VE DİPLOMASİ (+10 Puan)
    low_priority = ["trade", "ticaret", "economy", "ekonomi", "deal", "anlaşma", "meeting", "toplantı", "eu", "ab", "energy", "enerji", "oil", "petrol", "chip"]
    if any(w in text for w in low_priority): score += 10
    
    return score

def fetch_news():
    print("🕵️‍♂️ AJAN 1 (RESEARCHER): Genişletilmiş ağdan veri topluyor...")
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for source, url in rss_sources.items():
        try:
            # Zaman aşımını 25 saniyeye çıkardık (Kaynak sayısı arttı)
            resp = requests.get(url, headers=headers, timeout=25)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                # Her kaynaktan 3 haber çek (Kaynak çok olduğu için sayı 3 ideal)
                for entry in feed.entries[:3]:
                    title = entry.title
                    link = entry.link
                    summary = entry.summary[:200] if hasattr(entry, 'summary') else ""
                    score = calculate_priority_score(title, summary)
                    all_news.append({"source": source, "title": title, "link": link, "summary": summary, "score": score})
        except Exception as e:
            print(f"⚠️ {source} hatası: {e}")
            continue

    # En yüksek puanlıları seç
    all_news.sort(key=lambda x: x['score'], reverse=True)
    top_news = all_news[:7] # Kritik haber sayısını 6'dan 7'ye çıkardık (Daha fazla veri)
    
    buffer = ""
    raw_links_html = "<ul>"
    for news in top_news:
        icon = "🚨" if news['score'] >= 50 else "🔹"
        buffer += f"[{news['source']}] {icon} {news['title']} | URL: {news['link']}\n"
        raw_links_html += f"<li><b>{news['source']} ({news['score']} Puan):</b> <a href='{news['link']}'>{news['title']}</a></li>"
    raw_links_html += "</ul>"
    
    return buffer, raw_links_html

# ==========================================
# 3. HAFIZA MODÜLÜ
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
# 4. GÖRSELLEŞTİRME
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
# 5. AJANLI SİMÜLASYON (MULTI-AGENT)
# ==========================================
def run_agent_workflow(current_data, historical_memory):
    
    print("⏳ AJAN 2 (HISTORIAN): Geçmişi tarıyor...")
    historian_prompt = f"""
    Sen uzman bir Tarihçisin. Görevin bugünkü haberlerle geçmiş raporları kıyaslamak.
    BUGÜN: {current_data}
    GEÇMİŞ: {historical_memory}
    GÖREV: Sadece BENZERLİKLERİ veya ÇELİŞKİLERİ maddeler halinde yaz.
    """
    history_analysis = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": historian_prompt}]
    ).choices[0].message.content

    print("⚖️ AJAN 3 (THE CRITIC): Analizi denetliyor...")
    critic_prompt = f"""
    Sen 'Kızıl Takım' (Red Team) liderisin. 
    VERİLER: {current_data}
    GÖREV: Batı (CNN/VOA/BBC) ile Doğu/Asya (TASS/China Daily/Tehran Times) kaynakları arasındaki propaganda farkını bul.
    Hangi taraf neyi gizliyor? İsrail ve İran kaynakları ne diyor? Sert bir dille yaz.
    """
    critic_analysis = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": critic_prompt}]
    ).choices[0].message.content

    print("✍️ AJAN 4 (CHIEF EDITOR): Nihai raporu yazıyor...")
    final_system_prompt = """Sen Savaş Odası'nın Başkanısın. 
    NİHAİ STRATEJİK RAPORU yaz.
    
    FORMAT: HTML kullan.
    BÖLÜMLER:
    1. REALİST KANAT (Güvenlik odaklı)
    2. LİBERAL KANAT (Diplomasi odaklı)
    3. PROPAGANDA SAVAŞI (Denetçi Notları - Batı vs Doğu/İran/İsrail)
    4. TARİHSEL TESPİT (Tarihçi Notları)
    5. BAŞKANIN KARARI
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
    print(f"📧 Dağıtım Başlıyor: {len(ALICI_LISTESI)} Kişi")
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        
        for alici in ALICI_LISTESI:
            print(f"   -> Gönderiliyor: {alici}")
            
            msg = MIMEMultipart('related')
            msg['From'] = GMAIL_USER
            msg['To'] = alici 
            msg['Subject'] = f"🧠 KİŞİSEL İSTİHBARAT RAPORU - {datetime.date.today()}"
            
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            html_content = f"""
            <html><body style='font-family: Arial, sans-serif; color:#333;'>
                <h1 style="color:#c0392b; text-align:center;">🛡️ SAVAŞ ODASI (GENİŞLETİLMİŞ AĞ)</h1>
                <p style="text-align:center;"><i>"Sayın Üye İçin Özel Hazırlanmıştır"</i></p>
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
            
            server.sendmail(GMAIL_USER, alici, msg.as_string())
        
        server.quit()
        print("✅ Tüm dağıtım başarıyla tamamlandı!")
        
    except Exception as e:
        print(f"❌ Dağıtım Hatası: {e}")

if __name__ == "__main__":
    raw_data, raw_links = fetch_news()
    memory = read_historical_memory()
    
    if len(raw_data) > 20:
        report = run_agent_workflow(raw_data, memory)
        graph_map = draw_network_graph(raw_data)
        archive(report)
        audio = create_audio(report)
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Veri yok.")
