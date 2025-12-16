import streamlit as st
import os
import glob
import json
import base64
import chromadb
# Hazır embedding fonksiyonunu kaldırdık, manuel yazacağız
from sentence_transformers import SentenceTransformer 
from groq import Groq
from duckduckgo_search import DDGS
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 1. AYARLAR
st.set_page_config(page_title="Savaş Odası (GUEST & E2EE)", page_icon="🛡️", layout="wide")

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

# --- YENİ MANUEL EMBEDDING SINIFI ---
class YerelEmbedder:
    def __init__(self):
        # device="cpu" diyerek GPU hatasını engelliyoruz
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    def __call__(self, input):
        # ChromaDB bu formatı bekler
        return self.model.encode(input).tolist()
    
    def name(self):
        return "YerelEmbedder"

# --- ŞİFRELEME FONKSİYONLARI ---
def anahtar_turet(password, salt=b'SavasOdasiSabitTuz'):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def sifrele(veri_json, password):
    try:
        key = anahtar_turet(password)
        f = Fernet(key)
        veri_str = json.dumps(veri_json)
        sifreli_byte = f.encrypt(veri_str.encode())
        return base64.urlsafe_b64encode(sifreli_byte).decode()
    except: return None

def sifreyi_coz(sifreli_str, password):
    try:
        key = anahtar_turet(password)
        f = Fernet(key)
        sifreli_byte = base64.urlsafe_b64decode(sifreli_str.encode())
        cozulmus_byte = f.decrypt(sifreli_byte)
        return json.loads(cozulmus_byte.decode())
    except: return []

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

# --- AUTH FONKSİYONLARI ---
def giris_yap(email, password):
    try:
        return supabase.auth.sign_in_with_password({"email": email, "password": password}).user
    except: return None

def kayit_ol(email, password):
    try:
        return supabase.auth.sign_up({"email": email, "password": password}).user
    except Exception as e: st.error(str(e)); return None

def sifre_sifirla(email):
    try:
        site_url = "https://siyasi-istihbarat-botu.streamlit.app"
        supabase.auth.reset_password_email(email, options={"redirect_to": site_url})
        st.success(f"📧 Sıfırlama gönderildi: {email}")
        st.warning("⚠️ Şifre değişince eski sohbetler silinir.")
    except Exception as e: st.error(str(e))

def buluttan_yukle(user_id, password):
    try:
        res = supabase.table("chat_logs").select("messages").eq("user_id", user_id).execute()
        if res.data and "encrypted_data" in res.data[0]["messages"]:
            return sifreyi_coz(res.data[0]["messages"]["encrypted_data"], password)
    except: pass
    return []

def buluta_kaydet(user_id, msgs, password):
    try:
        enc = sifrele(msgs, password)
        supabase.table("chat_logs").upsert({"user_id": user_id, "messages": {"encrypted_data": enc}}, on_conflict="user_id").execute()
    except: pass

# --- AI FONKSİYONLARI ---
@st.cache_resource
def get_chroma_client(): return chromadb.PersistentClient(path="VEKTOR_DB")

@st.cache_resource
def get_embedding_function(): return YerelEmbedder()

def hafizayi_guncelle():
    chroma = get_chroma_client()
    ef = get_embedding_function()
    col = chroma.get_or_create_collection(name="savas_odasi", embedding_function=ef)
    dosyalar = glob.glob("ARSIV/*.md")
    yeni = False
    for d in dosyalar:
        if not col.get(ids=[os.path.basename(d)])['ids']:
            with open(d,"r",encoding="utf-8") as f: col.add(documents=[f.read()], metadatas=[{"source":os.path.basename(d)}], ids=[os.path.basename(d)])
            yeni = True
    return yeni

def hafizadan_getir(soru):
    try:
        ef = get_embedding_function()
        col = get_chroma_client().get_collection(name="savas_odasi", embedding_function=ef)
        res = col.query(query_texts=[soru], n_results=3)
        return "\n".join(res['documents'][0]) if res['documents'] else "Veri yok."
    except: return "Hata."

def web_ara(soru):
    try:
        res = DDGS().text(keywords=soru, region='tr-tr', max_results=5)
        return "\n".join([f"- {r['title']}: {r['body']}" for r in res]) if res else "Sonuç yok."
    except: return "Bağlantı hatası."

def harita_analiz(metin):
    prompt = f"JSON formatında coğrafi ilişkiler: {{'data': [{{'kaynak_ulke':'Rusya','hedef_ulke':'Ukrayna','olay':'Saldırı','risk_puani':80}}]}} Metin: {metin[:3000]}"
    try:
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], response_format={"type":"json_object"})
        return json.loads(res.choices[0].message.content)
    except: return {"data":[]}

# ================= MAIN =================
if "user" not in st.session_state: st.session_state.user = None
if "is_guest" not in st.session_state: st.session_state.is_guest = False
if "password_cache" not in st.session_state: st.session_state.password_cache = None
# --- HARİTA İÇİN STATE ---
if "harita_data" not in st.session_state: st.session_state.harita_data = None

# GİRİŞ EKRANI
if not st.session_state.user and not st.session_state.is_guest:
    st.title("🔐 SAVAŞ ODASI: GİRİŞ")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Üye Girişi")
        email = st.text_input("E-posta")
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            u = giris_yap(email, password)
            if u:
                st.session_state.user = u
                st.session_state.password_cache = password
                st.session_state.messages = buluttan_yukle(u.id, password)
                st.rerun()
        with st.expander("Şifremi Unuttum / Kayıt Ol"):
            ne = st.text_input("Yeni/Unutulan E-posta")
            np = st.text_input("Yeni Şifre", type="password")
            if st.button("Kayıt Ol"): kayit_ol(ne, np)
            if st.button("Sıfırlama Linki Gönder"): sifre_sifirla(ne)
    with col2:
        st.subheader("Misafir")
        if st.button("Misafir Girişi >>"):
            st.session_state.is_guest = True
            st.session_state.messages = []
            st.rerun()
    st.stop()

# --- ANA EKRAN ---
if st.session_state.is_guest:
    user_id = "guest"
    st.sidebar.warning("🕵️ Misafir Modu")
else:
    user_id = st.session_state.user.id
    st.sidebar.success(f"Ajan: {st.session_state.user.email}")

if st.sidebar.button("Çıkış"):
    if not st.session_state.is_guest: supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.is_guest = False
    st.session_state.password_cache = None
    st.rerun()

if st.sidebar.button("Temizle"):
    st.session_state.messages = []
    if not st.session_state.is_guest: buluta_kaydet(user_id, [], st.session_state.password_cache)
    st.rerun()

try:
    files = glob.glob("ARSIV/*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    sec = st.sidebar.radio("Rapor", [os.path.basename(f) for f in files])
    with open(f"ARSIV/{sec}","r",encoding="utf-8") as f: txt = f.read()
except: txt = "Veri yok"

st.title("☁️ SAVAŞ ODASI")
with st.spinner("Yükleniyor..."): hafizayi_guncelle()

t1, t2, t3 = st.tabs(["📄 Rapor", "🗺️ Harita", "💬 Chat"])

with t1: st.markdown(txt, unsafe_allow_html=True)

with t2:
    # --- HARİTA DÜZELTMESİ ---
    if st.button("Haritayı Analiz Et ve Çiz"):
        with st.spinner("Harita çiziliyor..."):
            st.session_state.harita_data = harita_analiz(txt)
    
    # Veri varsa haritayı çiz (Sayfa yenilense de kaybolmaz)
    if st.session_state.harita_data:
        data = st.session_state.harita_data
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
    for m in st.session_state.messages: st.chat_message(m["role"]).markdown(m["content"])
    if q := st.chat_input("..."):
        st.session_state.messages.append({"role":"user","content":q})
        st.chat_message("user").markdown(q)
        if not st.session_state.is_guest: buluta_kaydet(user_id, st.session_state.messages, st.session_state.password_cache)
        
        with st.chat_message("assistant"):
            s = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":f"RAG:{hafizadan_getir(q)} WEB:{web_ara(q)} SORU:{q}"}] + st.session_state.messages, stream=True)
            def gen():
                for c in s: 
                    if c.choices[0].delta.content: yield c.choices[0].delta.content
            res = st.write_stream(gen())
            st.session_state.messages.append({"role":"assistant","content":res})
            if not st.session_state.is_guest: buluta_kaydet(user_id, st.session_state.messages, st.session_state.password_cache)
