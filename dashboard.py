import streamlit as st
import os
import glob
import json
import chromadb
from chromadb.utils import embedding_functions
from groq import Groq
from duckduckgo_search import DDGS
import folium
from streamlit_folium import st_folium

# 1. AYARLAR
st.set_page_config(page_title="Savaş Odası v5.0", page_icon="🌍", layout="wide")

# API Anahtarı
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Lütfen Streamlit Secrets ayarlarından GROQ_API_KEY ekleyin.")
    st.stop()

# Klasör Kontrolleri
for folder in ["ARSIV", "LOGS", "VEKTOR_DB"]:
    if not os.path.exists(folder): os.makedirs(folder)

# --- SABİT KOORDİNATLAR (Hız ve Doğruluk İçin) ---
# AI bazen saçmalayabilir, bu yüzden başkentleri sabitledik.
KOORDINATLAR = {
    "Türkiye": [39.9334, 32.8597], "Turkey": [39.9334, 32.8597], "Ankara": [39.9334, 32.8597],
    "ABD": [38.9072, -77.0369], "USA": [38.9072, -77.0369], "Washington": [38.9072, -77.0369],
    "Rusya": [55.7558, 37.6173], "Russia": [55.7558, 37.6173], "Moskova": [55.7558, 37.6173],
    "Ukrayna": [50.4501, 30.5234], "Ukraine": [50.4501, 30.5234], "Kiev": [50.4501, 30.5234],
    "Çin": [39.9042, 116.4074], "China": [39.9042, 116.4074], "Pekin": [39.9042, 116.4074],
    "İsrail": [31.7683, 35.2137], "Israel": [31.7683, 35.2137], "Tel Aviv": [32.0853, 34.7818],
    "Filistin": [31.9522, 35.2332], "Gazze": [31.5017, 34.4668], "Gaza": [31.5017, 34.4668],
    "İran": [35.6892, 51.3890], "Iran": [35.6892, 51.3890], "Tahran": [35.6892, 51.3890],
    "Avrupa Birliği": [50.8503, 4.3517], "EU": [50.8503, 4.3517], "Brussels": [50.8503, 4.3517],
    "NATO": [50.8798, 4.4258],
    "Almanya": [52.5200, 13.4050], "Germany": [52.5200, 13.4050],
    "Fransa": [48.8566, 2.3522], "France": [48.8566, 2.3522],
    "İngiltere": [51.5074, -0.1278], "UK": [51.5074, -0.1278],
    "Yunanistan": [37.9838, 23.7275], "Greece": [37.9838, 23.7275],
    "Suriye": [33.5138, 36.2765], "Syria": [33.5138, 36.2765],
    "Azerbaycan": [40.4093, 49.8671], "Azerbaijan": [40.4093, 49.8671],
    "Ermenistan": [40.1792, 44.4991], "Armenia": [40.1792, 44.4991]
}

# --- FONKSİYONLAR ---
@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path="VEKTOR_DB")

def hafizayi_guncelle():
    chroma_client = get_chroma_client()
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_or_create_collection(name="savas_odasi_hafiza", embedding_function=sentence_transformer_ef)
    
    dosyalar = glob.glob("ARSIV/*.md")
    yeni_veri = False
    
    for dosya_yolu in dosyalar:
        dosya_adi = os.path.basename(dosya_yolu)
        if len(collection.get(ids=[dosya_adi])['ids']) == 0:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                collection.add(documents=[f.read()], metadatas=[{"source": dosya_adi}], ids=[dosya_adi])
            yeni_veri = True
    return yeni_veri

def hafizadan_bilgi_getir(soru):
    try:
        chroma_client = get_chroma_client()
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        collection = chroma_client.get_collection(name="savas_odasi_hafiza", embedding_function=sentence_transformer_ef)
        results = collection.query(query_texts=[soru], n_results=3)
        baglam = ""
        if results['documents']:
            for doc in results['documents'][0]: baglam += doc + "\n\n---\n\n"
        return baglam if baglam else "Arşivde bilgi yok."
    except: return "Hafıza hatası."

def internette_ara(sorgu):
    try:
        results = DDGS().text(keywords=sorgu, region='tr-tr', safesearch='off', max_results=5)
        ozet = ""
        if results:
            for r in results: ozet += f"- {r['title']}: {r['body']} (Link: {r['href']})\n"
        return ozet if ozet else "Sonuç bulunamadı."
    except Exception as e: return f"Bağlantı hatası: {e}"

def harita_verisi_olustur(rapor_metni):
    """
    Rapor metnini okur ve harita için JSON formatında ilişki verisi çıkarır.
    """
    prompt = f"""
    Aşağıdaki istihbarat raporunu analiz et ve harita üzerinde göstermek için coğrafi ilişkileri çıkar.
    Sadece JSON formatında cevap ver. Başka hiçbir şey yazma.
    
    Format şu olmalı:
    {{
        "data": [
            {{"kaynak_ulke": "Rusya", "hedef_ulke": "Ukrayna", "olay": "Füze saldırısı", "risk_puani": 85}},
            {{"kaynak_ulke": "ABD", "hedef_ulke": "İsrail", "olay": "Diplomatik destek", "risk_puani": 30}}
        ]
    }}
    
    Kullanılacak Ülkeler (Sadece bunlardan seç): Türkiye, ABD, Rusya, Ukrayna, Çin, İsrail, Gazze, İran, Avrupa Birliği, Yunanistan, Suriye, Azerbaycan, Ermenistan.
    
    RAPOR:
    {rapor_metni[:4000]}
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except:
        return {"data": []}

# --- GİRİŞ VE AYARLAR ---
def gecmisi_yukle(kullanici_adi):
    path = f"LOGS/{kullanici_adi}.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return []

def gecmisi_kaydet(kullanici_adi, mesajlar):
    with open(f"LOGS/{kullanici_adi}.json", "w", encoding="utf-8") as f:
        json.dump(mesajlar, f, ensure_ascii=False, indent=4)

# YAN MENÜ
st.sidebar.title("🔐 GİRİŞ")
ajan_kodu = st.sidebar.text_input("Ajan Kodu:", placeholder="Örn: Eymen007")

if st.sidebar.button("🧹 Sohbeti Sıfırla"):
    if ajan_kodu:
        gecmisi_kaydet(ajan_kodu, [])
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("🗄️ RAPORLAR")

try:
    dosyalar = glob.glob("ARSIV/*.md")
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    dosya_isimleri = [os.path.basename(f) for f in dosyalar]
except: dosya_isimleri = []

if dosya_isimleri:
    secilen_dosya = st.sidebar.radio("Seçiniz:", dosya_isimleri)
    with open(f"ARSIV/{secilen_dosya}", "r", encoding="utf-8") as f:
        secilen_dosya_icerigi = f.read()
else:
    secilen_dosya_icerigi = "Arşiv boş."

# Hafıza Güncelleme
with st.spinner('Sistem yükleniyor...'):
    if hafizayi_guncelle(): st.toast("Arşiv Güncellendi!", icon="🧠")

# ANA EKRAN
st.title("🌍 KÜRESEL SAVAŞ ODASI (Level 5)")

if not ajan_kodu:
    st.warning("⚠️ Lütfen sol menüden Ajan Kodunuzu giriniz.")
    st.stop()

# Oturum Başlat
if "messages" not in st.session_state: st.session_state.messages = gecmisi_yukle(ajan_kodu)
if "last_user" not in st.session_state: st.session_state.last_user = ajan_kodu
elif st.session_state.last_user != ajan_kodu:
    st.session_state.messages = gecmisi_yukle(ajan_kodu)
    st.session_state.last_user = ajan_kodu

st.success(f"✅ Ajan: **{ajan_kodu}** Aktif")

# --- SEKMELİ YAPI (TABS) ---
tab1, tab2, tab3 = st.tabs(["📄 GÜNLÜK RAPOR", "🗺️ CANLI SAVAŞ HARİTASI", "🧠 HİBRİT CHAT"])

with tab1:
    st.markdown(secilen_dosya_icerigi, unsafe_allow_html=True)

with tab2:
    st.subheader("📍 İnteraktif Operasyon Haritası")
    st.info("Bu harita, sol menüde seçilen rapordaki olaylara göre anlık çizilir.")
    
    if st.button("🗺️ Haritayı Çiz"):
        with st.spinner("Yapay Zeka raporu analiz ediyor..."):
            harita_json = harita_verisi_olustur(secilen_dosya_icerigi)
            
            # Harita Başlangıcı
            m = folium.Map(location=[39.0, 35.0], zoom_start=3, tiles="CartoDB dark_matter")
            
            # Verileri İşle
            if "data" in harita_json:
                for olay in harita_json["data"]:
                    k_ulke = olay.get("kaynak_ulke")
                    h_ulke = olay.get("hedef_ulke")
                    aciklama = olay.get("olay")
                    risk = olay.get("risk_puani", 50)
                    
                    if k_ulke in KOORDINATLAR and h_ulke in KOORDINATLAR:
                        k_loc = KOORDINATLAR[k_ulke]
                        h_loc = KOORDINATLAR[h_ulke]
                        
                        # Kaynak Marker
                        folium.Marker(k_loc, popup=f"<b>{k_ulke}</b><br>{aciklama}", icon=folium.Icon(color="red", icon="crosshairs", prefix='fa')).add_to(m)
                        
                        # Hedef Marker
                        folium.Marker(h_loc, popup=f"<b>{h_ulke}</b><br>Hedef", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
                        
                        # Çizgi
                        renk = "red" if risk > 70 else ("orange" if risk > 40 else "green")
                        folium.PolyLine([k_loc, h_loc], color=renk, weight=2.5, tooltip=f"{k_ulke} -> {h_ulke}").add_to(m)
            
            st_folium(m, width="100%", height=500)

with tab3:
    st.subheader("💬 Hibrit İstihbarat Analisti")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
        
    if prompt := st.chat_input("Emriniz?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        gecmisi_kaydet(ajan_kodu, st.session_state.messages)
        
        with st.status("🕵️‍♂️ Analiz yapılıyor...") as s:
            st.write("📂 Arşiv taranıyor...")
            arsiv = hafizadan_bilgi_getir(prompt)
            st.write("🌐 İnternet taranıyor...")
            web = internette_ara(prompt)
            s.update(label="✅ Tamamlandı", state="complete")
            
        with st.chat_message("assistant"):
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{
                        "role": "system", 
                        "content": f"""Sen Stratejistsin. 
                        ARŞİV BİLGİSİ: {arsiv}
                        WEB BİLGİSİ: {web}
                        SORU: {prompt}
                        
                        Arşiv ve Web bilgisini birleştirerek cevapla."""
                    }] + st.session_state.messages,
                    stream=True
                )
                def gen():
                    for chunk in stream:
                        if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
                res = st.write_stream(gen())
                st.session_state.messages.append({"role": "assistant", "content": res})
                gecmisi_kaydet(ajan_kodu, st.session_state.messages)
            except Exception as e: st.error(str(e))
