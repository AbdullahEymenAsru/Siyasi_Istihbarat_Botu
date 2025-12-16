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
from supabase import create_client, Client

# 1. AYARLAR
st.set_page_config(page_title="Savaş Odası (SECURE)", page_icon="🔐", layout="wide")

# API Anahtarları Kontrolü
if "GROQ_API_KEY" not in st.secrets or "SUPABASE_URL" not in st.secrets:
    st.error("Lütfen Streamlit Secrets ayarlarından GROQ ve SUPABASE anahtarlarını ekleyin.")
    st.stop()

# İstemcileri Başlat
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Klasör Kontrolleri
for folder in ["ARSIV", "VEKTOR_DB"]:
    if not os.path.exists(folder): os.makedirs(folder)

# --- SABİT KOORDİNATLAR ---
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

# --- GÜVENLİK VE VERİTABANI FONKSİYONLARI ---
def giris_yap(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res.user
    except Exception as e:
        st.error(f"Giriş başarısız: {e}")
        return None

def kayit_ol(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("Kayıt başarılı! Giriş yapabilirsiniz.")
        return res.user
    except Exception as e:
        st.error(f"Kayıt hatası: {e}")
        return None

def buluttan_yukle(user_id):
    """Kullanıcının geçmiş sohbetini Supabase'den çeker."""
    try:
        response = supabase.table("chat_logs").select("messages").eq("user_id", user_id).execute()
        if response.data: return response.data[0]["messages"]
    except: pass
    return []

def buluta_kaydet(user_id, messages):
    """Sohbeti Supabase'e kaydeder."""
    try:
        data = {"user_id": user_id, "messages": messages}
        supabase.table("chat_logs").upsert(data, on_conflict="user_id").execute()
    except Exception as e: print(f"Kayıt hatası: {e}")

# --- AI VE HARİTA FONKSİYONLARI ---
@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path="VEKTOR_DB")

def hafizayi_guncelle():
    chroma = get_chroma_client()
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = chroma.get_or_create_collection(name="savas_odasi", embedding_function=ef)
    dosyalar = glob.glob("ARSIV/*.md")
    yeni = False
    for d in dosyalar:
        adi = os.path.basename(d)
        if not col.get(ids=[adi])['ids']:
            with open(d,"r",encoding="utf-8") as f: col.add(documents=[f.read()], metadatas=[{"source":adi}], ids=[adi])
            yeni = True
    return yeni

def hafizadan_getir(soru):
    try:
        col = get_chroma_client().get_collection(name="savas_odasi", embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2"))
        res = col.query(query_texts=[soru], n_results=3)
        return "\n".join(res['documents'][0]) if res['documents'] else "Arşivde bilgi yok."
    except: return "Hafıza hatası."

def web_ara(soru):
    try:
        res = DDGS().text(keywords=soru, region='tr-tr', max_results=5)
        return "\n".join([f"- {r['title']}: {r['body']}" for r in res]) if res else "İnternette sonuç yok."
    except: return "Bağlantı hatası."

def harita_analiz(metin):
    prompt = f"JSON formatında coğrafi ilişkiler çıkar: {{'data': [{{'kaynak_ulke':'Rusya','hedef_ulke':'Ukrayna','olay':'Saldırı','risk_puani':80}}]}} Metin: {metin[:3000]}"
    try:
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], response_format={"type":"json_object"})
        return json.loads(res.choices[0].message.content)
    except: return {"data":[]}

# ==========================================
# UYGULAMA AKIŞI
# ==========================================

# 1. OTURUM KONTROLÜ
if "user" not in st.session_state:
    st.session_state.user = None

# GİRİŞ EKRANI (Eğer kullanıcı giriş yapmamışsa)
if not st.session_state.user:
    st.title("🔐 SAVAŞ ODASI: GÜVENLİ GİRİŞ")
    st.markdown("Verileriniz Supabase Bulutunda uçtan uca şifreli saklanmaktadır.")
    
    tab_giris, tab_kayit = st.tabs(["Giriş Yap", "Kayıt Ol"])
    
    with tab_giris:
        email = st.text_input("E-posta Adresi")
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            user = giris_yap(email, password)
            if user:
                st.session_state.user = user
                st.session_state.messages = buluttan_yukle(user.id)
                st.rerun()

    with tab_kayit:
        new_email = st.text_input("Yeni E-posta Adresi")
        new_pass = st.text_input("Yeni Şifre (En az 6 karakter)", type="password")
        if st.button("Hesap Oluştur"):
            kayit_ol(new_email, new_pass)
            
    st.stop() # Giriş yapılmadıysa kodun geri kalanı çalışmaz.

# --- BURADAN SONRASI SADECE GİRİŞ YAPANLARA GÖZÜKÜR ---

user_email = st.session_state.user.email
user_id = st.session_state.user.id

# YAN MENÜ
st.sidebar.success(f"Aktif Ajan: {user_email}")
if st.sidebar.button("Güvenli Çıkış"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🧹 Geçmişi Temizle"):
    buluta_kaydet(user_id, [])
    st.session_state.messages = []
    st.rerun()

# Rapor Listesi
try:
    dosyalar = glob.glob("ARSIV/*.md")
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    files = [os.path.basename(f) for f in dosyalar]
except: files = []

secilen_icerik = "Veri yok"
if files:
    sec = st.sidebar.radio("🗄️ Rapor Arşivi", files)
    with open(f"ARSIV/{sec}", "r", encoding="utf-8") as f: secilen_icerik = f.read()

# ANA EKRAN
st.title("☁️ KÜRESEL SAVAŞ ODASI (Level 7)")
with st.spinner("Beyin güncelleniyor..."): hafizayi_guncelle()

# SEKMELER
t1, t2, t3 = st.tabs(["📄 RAPOR", "🗺️ HARİTA", "🧠 HİBRİT CHAT"])

with t1: 
    st.markdown(secilen_icerik, unsafe_allow_html=True)

with t2:
    st.subheader("📍 İnteraktif Operasyon Haritası")
    if st.button("🗺️ Haritayı Analiz Et ve Çiz"):
        data = harita_analiz(secilen_icerik)
        m = folium.Map([39,35], zoom_start=3, tiles="CartoDB dark_matter")
        if "data" in data:
            for i in data["data"]:
                k, h, r = i.get("kaynak_ulke"), i.get("hedef_ulke"), i.get("risk_puani",50)
                if k in KOORDINATLAR and h in KOORDINATLAR:
                    folium.Marker(KOORDINATLAR[k], popup=k, icon=folium.Icon(color="red",icon="crosshairs", prefix='fa')).add_to(m)
                    folium.Marker(KOORDINATLAR[h], popup=h, icon=folium.Icon(color="blue",icon="info-sign")).add_to(m)
                    folium.PolyLine([KOORDINATLAR[k],KOORDINATLAR[h]], color="red" if r>70 else "orange").add_to(m)
        st_folium(m, width="100%")

with t3:
    st.subheader("💬 Hibrit İstihbarat Analisti")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if q := st.chat_input("Emriniz nedir komutanım?"):
        st.session_state.messages.append({"role":"user","content":q})
        with st.chat_message("user"): st.markdown(q)
        buluta_kaydet(user_id, st.session_state.messages) # Anlık Kayıt
        
        with st.status("🕵️‍♂️ Analiz yapılıyor...") as s:
            st.write("📂 Arşiv taranıyor (RAG)...")
            arsiv = hafizadan_getir(q)
            st.write("🌐 İnternet taranıyor (Web)...")
            web = web_ara(q)
            s.update(label="✅ Tamamlandı", state="complete")
        
        with st.chat_message("assistant"):
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":f"Sen Stratejistsin.\n\nARŞİV BİLGİSİ:\n{arsiv}\n\nCANLI WEB BİLGİSİ:\n{web}\n\nSORU: {q}\n\nBunları birleştir ve cevapla."}] + st.session_state.messages,
                stream=True
            )
            def gen():
                for c in stream:
                    if c.choices[0].delta.content: yield c.choices[0].delta.content
            res = st.write_stream(gen())
            st.session_state.messages.append({"role":"assistant","content":res})
            buluta_kaydet(user_id, st.session_state.messages) # Anlık Kayıt
