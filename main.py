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
import trafilatura # <--- YENİ KÜTÜPHANE (TAM METİN İÇİN)
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
    'CNN International': 'http://rss.cnn.com/rss/edition.rss',
    'Voice of America (VOA)': 'https://www.voanews.com/api/zg$oq_et$p',
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
    'Dawn (Pakistan)': 'https://www.dawn.com/feeds/home/',
    'Times of India': 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms'
}

KRITIK_AKTORLER = ["Turkey", "Türkiye", "Erdoğan", "Fidan", "Biden", "Trump", "Putin", "Xi Jinping", "Zelensky", "Netanyahu", "Hamas", "NATO", "EU", "Iran", "China", "Russia", "Pakistan", "India", "Korea"]

# ==========================================
# 2. AJAN 1: RESEARCHER (VERİ TOPLAYICI & SCRAPER) 🕷️
# ==========================================
def calculate_priority_score(title, summary):
    score = 0
    text = (title + " " + summary).lower()
    
    high_priority = ["nuclear", "war", "missile", "attack", "gaza", "ukraine", "taiwan", "terror", "bomb", "sondakika"]
    if any(w in text for w in high_priority): score += 50
    
    med_priority = ["turkey", "erdogan", "nato", "putin", "biden", "trump", "iran", "israel", "defense", "military"]
    if any(w in text for w in med_priority): score += 30
    
    low_priority = ["trade", "economy", "deal", "meeting", "eu", "energy", "oil"]
    if any(w in text for w in low_priority): score += 10
    
    return score

def get_full_text(url):
    """Linke gider ve haberin tamamını indirir (Scraping)"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text:
                # Çok uzunsa kırp (Token limitini korumak için)
                return text[:2500] 
    except:
        pass
    return None

def fetch_news():
    print("🕵️‍♂️ AJAN 1: Genişletilmiş ağ taranıyor ve KRİTİK haberler okunuyor...")
    all_news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. ADIM: RSS TARAMA VE PUANLAMA
    for source, url in rss_sources.items():
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            feed = feedparser.parse(resp.content)
            if feed.entries:
                for i, entry in enumerate(feed.entries[:3]):
                    title = entry.title
                    link = entry.link
                    summary = entry.summary[:200] if hasattr(entry, 'summary') else ""
                    
                    score = calculate_priority_score(title, summary)
                    if i == 0: score += 10 
                    
                    all_news.append({"source": source, "title": title, "link": link, "summary": summary, "score": score})
        except: continue

    # 2. ADIM: EN KRİTİK HABERLERİ SEÇME
    all_news.sort(key=lambda x: x['score'], reverse=True)
    top_news = all_news[:6] # En önemli 6 haberi seç
    
    buffer = ""
    raw_links_html = "<ul>"
    
    # 3. ADIM: SEÇİLENLER İÇİN TAM METİN İNDİRME (SCRAPING)
    print("🕷️  AJAN 1: Seçilen haberlerin detaylarına iniliyor (Deep Dive)...")
    
    current_keywords = [] # Hafıza araması için anahtar kelimeler biriktiriyoruz

    for news in top_news:
        full_text = get_full_text(news['link'])
        
        # Eğer tam metin çekebildiysek onu kullan, yoksa özeti kullan
        content_to_use = full_text if full_text else news['summary']
        content_type = "TAM METİN" if full_text else "ÖZET"
        
        icon = "🚨" if news['score'] >= 50 else "🔹"
        buffer += f"[{news['source']}] {icon} {news['title']} ({content_type})\nİÇERİK: {content_to_use[:1000]}...\nURL: {news['link']}\n\n"
        
        raw_links_html += f"<li><b>{news['source']}:</b> <a href='{news['link']}'>{news['title']}</a></li>"
        
        # Başlıktaki kelimeleri hafıza için sakla
        current_keywords.extend(news['title'].lower().split())
    
    raw_links_html += "</ul>"
    
    return buffer, raw_links_html, current_keywords

# ==========================================
# 3. AKILLI HAFIZA (CONTEXT-AWARE MEMORY) 🧠
# ==========================================
def read_historical_memory(current_keywords):
    print("🧠 HAFIZA MODÜLÜ: Geçmişte bugüne benzer olaylar aranıyor...")
    
    memory_buffer = ""
    files = glob.glob("ARSIV/*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    
    # Gereksiz kelimeleri temizle
    stop_words = ["the", "in", "at", "on", "for", "to", "and", "a", "of", "is", "with", "haber", "son", "dakika"]
    keywords = [k for k in current_keywords if len(k) > 4 and k not in stop_words]
    keywords = list(set(keywords))[:5] # En önemli 5 kelime
    
    print(f"   -> Aranan Kavramlar: {keywords}")

    found_count = 0
    total_chars = 0
    SAFE_LIMIT = 12000 
    
    for file_path in files:
        if total_chars > SAFE_LIMIT: break
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            filename = os.path.basename(file_path)
            
            # RELEVANCE PUANI: Dosyada anahtar kelimeler geçiyor mu?
            relevance = sum(content.lower().count(k) for k in keywords)
            
            # Eğer alakalıysa veya çok yeniyse (son 2 gün) hafızaya al
            is_recent = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(file_path))).days < 2
            
            if relevance > 0 or is_recent:
                # İlgili kısımları al (Tamamını değil)
                short_content = content[:2000]
                memory_buffer += f"\n--- GEÇMİŞ RAPOR ({filename}) [Alaka: {relevance}] ---\n{short_content}...\n"
                total_chars += len(short_content)
                found_count += 1
                
    if not memory_buffer: return "Arşivde ilgili kayıt bulunamadı."
    print(f"   -> {found_count} adet ilgili geçmiş rapor bulundu.")
    return memory_buffer

# ==========================================
# 4. YENİ: YAPAY ZEKA TABANLI HARİTA 🗺️ (AJAN 5)
# ==========================================
def draw_network_graph(text_data):
    print("🗺️ AJAN 5: İlişkileri analiz edip harita çiziyor...")
    
    prompt = f"""
    Aşağıdaki haber metnini analiz et ve ülkeler/liderler arasındaki ilişkileri çıkar.
    Sadece şu formatta çıktı ver: "Aktör1,Aktör2"
    Örnek:
    USA,China
    Turkey,Greece
    Putin,Biden
    
    METİN:
    {text_data[:4000]}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        relations = completion.choices[0].message.content.split('\n')
    except:
        relations = ["Türkiye,Dünya"] 

    G = nx.Graph()
    for line in relations:
        if "," in line:
            parts = line.split(',')
            if len(parts) >= 2:
                source = parts[0].strip()
                target = parts[1].strip()
                if len(source) < 20 and len(target) < 20:
                    G.add_edge(source, target)
    
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
# 5. AJANLI SİMÜLASYON
# ==========================================
def run_agent_workflow(current_data, historical_memory):
    
    print("⏳ AJAN 2 (HISTORIAN): Çalışıyor...")
    historian_prompt = f"""
    Sen Tarihçisin. Bugünün haberleri: {current_data[:5000]}
    Geçmiş (Arşivden Bulunanlar): {historical_memory}
    Görevin: Geçmişteki benzer olaylarla bugünü kıyasla. Trendleri yaz.
    """
    history_analysis = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": historian_prompt}]
    ).choices[0].message.content

    print("⚖️ AJAN 3 (THE CRITIC): Çalışıyor...")
    critic_prompt = f"""
    Sen 'Kızıl Takım' liderisin. Veriler: {current_data[:5000]}
    Batı ve Doğu medyası arasındaki farkları sertçe eleştir.
    """
    critic_analysis = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": critic_prompt}]
    ).choices[0].message.content

    print("✍️ AJAN 4 (CHIEF EDITOR): Nihai rapor yazılıyor...")
    
    final_system_prompt = """Sen Savaş Odası Başkanısın. NİHAİ STRATEJİK RAPORU yaz.
    
    KURALLAR:
    1. LİNK ZORUNLU: Olayların yanına (<a href='URL'>Kaynak</a>) ekle.
    2. PROFESYONEL DİL: "Realist Kanat" yerine "JEOPOLİTİK RİSK ANALİZİ" gibi terimler kullan.
    
    BÖLÜMLER:
    1. 🔥 JEOPOLİTİK RİSK VE TEHDİTLER (Eski Realist Kanat)
    2. 🤝 DİPLOMASİ VE EKONOMİK FIRSATLAR (Eski Liberal Kanat)
    3. 👁️ İSTİHBARAT SAVAŞLARI (Propaganda Analizi)
    4. 📜 TARİHSEL HAFIZA (Arşiv Analizi)
    5. 🇹🇷 ANKARA İÇİN STRATEJİK TAVSİYE
    6. 🎲 GELECEK SENARYOLARI (% Olasılıklar)
    """
    
    final_user_prompt = f"""
    HAM VERİLER (TAM METİN İÇERİR): 
    {current_data[:7000]}
    
    TARİHÇİ VE DENETÇİ NOTLARI: 
    {history_analysis}
    {critic_analysis}
    """
    
    final_report = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": final_user_prompt}
        ],
        temperature=0.5
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
    script = "Sayın Konsey Üyeleri. Küresel İstihbarat Raporu arz edilir. " + clean_text[:900]
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
            msg['Subject'] = f"🧠 KÜRESEL İSTİHBARAT RAPORU - {datetime.date.today()}"
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            html_content = f"""
            <html><body style='font-family: Arial, sans-serif; color:#333;'>
                <h1 style="color:#2c3e50; text-align:center;">🛡️ SAVAŞ ODASI</h1>
                <p style="text-align:center;"><i>"Büyük Veri Analizli Stratejik Rapor"</i></p>
                <hr>
                <center>
                    <h3>🕸️ GÜNLÜK ETKİLEŞİM AĞI</h3>
                    <img src="cid:network_map" style="width:100%; max-width:700px; border:1px solid #ddd; padding:5px; border-radius:10px;">
                    <p style="font-size:10px; color:gray;">(Yapay Zeka tarafından haberlerden otomatik çıkarılmıştır)</p>
                </center>
                <br>
                {report_body}
                <br><hr>
                <div style="font-size:12px; color:#555; background:#f9f9f9; padding:10px;">
                    <h3>📚 ANALİZ EDİLEN KAYNAKLAR</h3>
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
        print("✅ Dağıtım tamamlandı!")
    except Exception as e:
        print(f"❌ Hata: {e}")

if __name__ == "__main__":
    # 1. Haberleri Çek (Tam Metin Scraping ile) ve Anahtar Kelimeleri Al
    raw_data, raw_links, current_keywords = fetch_news()
    
    # 2. Akıllı Hafızayı Çalıştır (Bugünün kelimelerine göre arşiv tara)
    memory = read_historical_memory(current_keywords)
    
    if len(raw_data) > 20:
        report = run_agent_workflow(raw_data, memory)
        graph_map = draw_network_graph(raw_data)
        archive(report)
        audio = create_audio(report)
        send_email_to_council(report, raw_links, audio, graph_map)
    else:
        print("Veri yok.")
