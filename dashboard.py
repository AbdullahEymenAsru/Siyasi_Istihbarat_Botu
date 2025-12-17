import streamlit as st
import os
import glob
import json
import base64
import time 
import shutil
import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq
from duckduckgo_search import DDGS
from supabase import create_client, Client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime
import streamlit.components.v1 as components 
import re 

# ==========================================
# 1. AYARLAR, TEMA VE CSS
# ==========================================

st.set_page_config(page_title="Savaş Odası (GUEST & E2EE)", page_icon="🛡️", layout="wide")

if "theme" not in st.session_state:
    st.session_state.theme = "Karanlık"

# Renk Paletleri
if st.session_state.theme == "Karanlık":
    v_bg, v_text, v_sidebar = "#0E1117", "#FFFFFF", "#161B22"
    v_chat_bg, v_input_bg = "#1A1C24", "#262730"
    v_border, v_accent = "#30363D", "#4CAF50"
else:
    v_bg, v_text, v_sidebar = "#FFFFFF", "#121212", "#F8F9FA"
    v_chat_bg, v_input_bg = "#F0F2F6", "#FFFFFF"
    v_border, v_accent = "#DCDDE1", "#2E7D32"

# CSS
st.markdown(f"""
<style>
    .stApp {{ background-color: {v_bg} !important; color: {v_text} !important; }}
    h1, h2, h3, h4, h5, h6, p, span, label, div, li, .stMarkdown, .stText {{ color: {v_text} !important; }}
    section[data-testid="stSidebar"] {{ background-color: {v_sidebar} !important; border-right: 1px solid {v_border} !important; }}
    section[data-testid="stSidebar"] * {{ color: {v_text} !important; }}
    .stTextInput input, .stTextArea textarea, [data-baseweb="select"] div {{ 
        background-color: {v_input_bg} !important; color: {v_text} !important; border: 1px solid {v_accent} !important; 
        border-radius: 5px !important; -webkit-text-fill-color: {v_text} !important;
    }}
    [data-testid="stChatMessage"] {{ background-color: {v_chat_bg} !important; border: 1px solid {v_border} !important; border-radius: 10px; margin-bottom: 10px !important; }}
    .stButton button {{ background-color: {v_accent} !important; color: white !important; border: none !important; }}
    .stButton button p {{ color: white !important; font-weight: bold !important; }}
    button[data-baseweb="tab"] p {{ color: {v_text} !important; }}
    [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
    a {{ color: {v_accent} !important; text-decoration: none; }}
    .stHtmlContainer {{ color: {v_text} !important; background-color: transparent !important; }}
    svg {{ fill: {v_text} !important; }}
</style>
""", unsafe_allow_html=True)

# -- API KONTROLLERİ VE ROTASYON LİSTESİ --
SITE_URL = "https://siyasi-istihbarat-botu.streamlit.app/"

if "GROQ_API_KEY" not in st.secrets or "SUPABASE_URL" not in st.secrets:
    st.error("API Anahtarları Eksik!")
    st.stop()

# Çift Mühimmat Hattı (Anahtarlar)
GROQ_KEYS = [
    st.secrets.get("GROQ_API_KEY"),
    st.secrets.get("GROQ_API_KEY_2") # Yedek Anahtar
]

supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

if not os.path.exists("ARSIV"): os.makedirs("ARSIV")

# ==========================================
# 2. ÇEKİRDEK FONKSİYONLAR
# ==========================================

# --- ROTASYONEL AI MOTORU ---
def ask_ai_with_rotation(messages, model_id):
    """
    Seçilen model ile API çağrısı yapar. 
    Eğer aktif anahtarın kotası dolarsa (429), otomatik olarak yedeğe geçer.
    """
    for i, key in enumerate(GROQ_KEYS):
        if not key: continue # Anahtar tanımlı değilse atla
        try:
            # Geçici istemci oluştur
            temp_client = Groq(api_key=key)
            return temp_client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=True
            )
        except Exception as e:
            if "429" in str(e): # Kota Doldu Hatası
                st.toast(f"⚠️ {i+1}. Mühimmat Hattı Tükendi, Yedek Hatta Geçiliyor...", icon="🔄")
                continue # Döngüdeki bir sonraki anahtara geç
            else:
                st.error(f"Sistem Hatası: {e}")
                return None
    
    st.error("❌ Kritik: Tüm mühimmat (API Anahtarları) tükendi! Yeni anahtar ekleyin.")
    return None

class YerelEmbedder:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    def __call__(self, input): return self.model.encode(input).tolist()
    def name(self): return "YerelEmbedder"

def anahtar_turet(password):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'SavasOdasiSabitTuz', iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def sifrele(data, password):
    try:
        f = Fernet(anahtar_turet(password))
        return base64.urlsafe_b64encode(f.encrypt(json.dumps(data).encode())).decode()
    except: return None

def sifreyi_coz(data_str, password):
    try:
        f = Fernet(anahtar_turet(password))
        return json.loads(f.decrypt(base64.urlsafe_b64decode(data_str.encode())).decode())
    except: return {}

def giris_yap(email, password):
    try: return supabase.auth.sign_in_with_password({"email": email, "password": password}).user
    except: return None

def kayit_ol(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password, "options": {"email_redirect_to": SITE_URL}})
        if res.user: supabase.table("abone_listesi").insert({"email": email}).execute()
        return res.user
    except: return None

def sifre_sifirla(email):
    try:
        supabase.auth.reset_password_email(email, options={"redirect_to": SITE_URL})
        st.success("Bağlantı gönderildi.")
    except Exception as e: st.error(f"Hata: {e}")

def buluttan_yukle(user_id, password):
    try:
        res = supabase.table("chat_logs").select("messages").eq("user_id", user_id).execute()
        if res.data:
            raw = res.data[0]["messages"]
            if "encrypted_data" in raw: return sifreyi_coz(raw["encrypted_data"], password)
            return raw
        return {}
    except: return {}

def buluta_kaydet(user_id, data, password, sessiz=False):
    """Veriyi şifreler ve buluta zorla yazar."""
    try:
        sifreli = sifrele(data, password)
        if sifreli:
            supabase.table("chat_logs").upsert(
                {"user_id": user_id, "messages": {"encrypted_data": sifreli}}, 
                on_conflict="user_id"
            ).execute()
            if not sessiz:
                st.toast("✅ Veriler Buluta Senkronize Edildi", icon="☁️")
    except Exception as e: 
        if not sessiz: st.error(f"Kayıt Hatası: {e}")

# --- EPHEMERAL HAFIZA (v4) ---
@st.cache_resource
def get_chroma_v4(): return chromadb.EphemeralClient()
@st.cache_resource
def get_embedder_v4(): return YerelEmbedder()

def hafizayi_guncelle():
    try:
        chroma = get_chroma_v4()
        ef = get_embedder_v4()
        col = chroma.get_or_create_collection(name="savas_odasi_ram_v4", embedding_function=ef)
        for d in glob.glob("ARSIV/*.md"):
            try:
                adi = os.path.basename(d)
                if not col.get(ids=[adi])['ids']:
                    with open(d, "r", encoding="utf-8") as f: 
                        col.add(documents=[f.read()], ids=[adi], metadatas=[{"source": adi}])
            except: pass
    except: pass

def hafizadan_getir(soru):
    try:
        res = get_chroma_v4().get_collection(name="savas_odasi_ram_v4", embedding_function=get_embedder_v4()).query(query_texts=[soru], n_results=3)
        return "\n".join(res['documents'][0]) if res['documents'] else "Arşivde veri yok."
    except: return "Hafıza verisi yok."

def web_ara(soru):
    try:
        res = DDGS().text(keywords=soru, region='tr-tr', max_results=3)
        return "\n".join([f"- {r['title']}: {r['body']}" for r in res])
    except: return "Web arama hatası."

# ==========================================
# 3. UYGULAMA AKIŞI
# ==========================================

if "user" not in st.session_state: st.session_state.user = None
if "is_guest" not in st.session_state: st.session_state.is_guest = False
if "password_cache" not in st.session_state: st.session_state.password_cache = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {"Genel Strateji": []}
if "current_session_name" not in st.session_state: st.session_state.current_session_name = "Genel Strateji"

# --- GİRİŞ ---
if not st.session_state.user and not st.session_state.is_guest:
    col_lt1, col_lt2 = st.columns([8, 2])
    with col_lt2:
        lt = st.selectbox("🌓 Görünüm", ["Karanlık", "Açık"], index=0 if st.session_state.theme=="Karanlık" else 1, key="login_theme")
        if lt != st.session_state.theme: st.session_state.theme = lt; st.rerun()

    st.title("🔐 SAVAŞ ODASI: GİRİŞ")
    
    if "type" in st.query_params and st.query_params["type"] == "recovery":
        st.info("🔄 Şifre Sıfırlama")
        new_pass_reset = st.text_input("Yeni Şifre", type="password")
        if st.button("Güncelle"):
            try:
                supabase.auth.update_user({"password": new_pass_reset})
                st.success("Güncellendi!")
            except Exception as e: st.error(f"Hata: {e}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔑 Personel Girişi")
        e = st.text_input("E-posta", key="le")
        p = st.text_input("Şifre", type="password", key="lp")
        if st.button("Giriş Yap"):
            u = giris_yap(e, p)
            if u:
                st.session_state.user = u
                st.session_state.password_cache = p
                d = buluttan_yukle(u.id, p)
                if d: st.session_state.chat_sessions = d; st.session_state.current_session_name = list(d.keys())[0]
                st.rerun()
        with st.expander("Kayıt / Şifre"):
            ne, np = st.text_input("E-posta"), st.text_input("Şifre", type="password")
            if st.button("Kayıt Ol"): kayit_ol(ne, np)
            if st.button("Şifremi Unuttum"): sifre_sifirla(ne)

    with col2:
        st.subheader("🕵️ Misafir")
        if st.button("Devam Et >>"): st.session_state.is_guest = True; st.rerun()
    st.stop()

# --- SIDEBAR ---
user_id = st.session_state.user.id if st.session_state.user else "guest"
user_pass = st.session_state.password_cache

st.sidebar.header("⚙️ OPERASYONEL AYARLAR")

# AI MODEL SEÇİMİ
model_secimi = st.sidebar.radio(
    "Analiz Birimi Seçin:",
    [
        "🚀 HIZLI (Llama 8B) - Az Token",
        "🧠 KAPSAMLI (Llama 70B) - Derin Analiz"
    ],
    index=1,
    help="Hızlı model anlık sorgular, Kapsamlı model detaylı raporlar içindir."
)
selected_model_id = "llama-3.1-8b-instant" if "HIZLI" in model_secimi else "llama-3.3-70b-versatile"

st.sidebar.divider()
st_theme = st.sidebar.selectbox("Görünüm", ["Karanlık", "Açık"], index=0 if st.session_state.theme=="Karanlık" else 1, key="st")
if st_theme != st.session_state.theme: st.session_state.theme = st_theme; st.rerun()

st.sidebar.header("🗄️ Arşiv Yönetimi")

# 1. YENİ SOHBET
if st.sidebar.button("➕ YENİ SOHBET"):
    n = f"Op_{datetime.now().strftime('%H%M%S')}"
    st.session_state.chat_sessions[n] = []
    st.session_state.current_session_name = n
    if not st.session_state.is_guest: 
        buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
    st.rerun()

sess = list(st.session_state.chat_sessions.keys())
sel = st.sidebar.selectbox("Geçmiş Sohbetler", sess, index=sess.index(st.session_state.current_session_name))
if sel != st.session_state.current_session_name: st.session_state.current_session_name = sel; st.rerun()

# 2. İSİM DEĞİŞTİRME
new_n = st.sidebar.text_input("İsim Değiştir", value=st.session_state.current_session_name)
if new_n != st.session_state.current_session_name and new_n:
    data = st.session_state.chat_sessions.pop(st.session_state.current_session_name)
    st.session_state.chat_sessions[new_n] = data
    st.session_state.current_session_name = new_n
    if not st.session_state.is_guest: 
        buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
    st.rerun()

# --- SOHBET SIFIRLAMA ---
if st.sidebar.button("🗑️ İmha Et"):
    current = st.session_state.current_session_name
    if len(st.session_state.chat_sessions) > 1:
        del st.session_state.chat_sessions[current]
        st.session_state.current_session_name = list(st.session_state.chat_sessions.keys())[0]
    else:
        st.session_state.chat_sessions[current] = [] 
        st.toast("Kayıtlar yakıldı, sayfa temizlendi.", icon="🔥")
    
    if not st.session_state.is_guest: 
        buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
    st.rerun()

if st.sidebar.button("Çıkış"): st.session_state.clear(); st.rerun()

# --- GELİŞMİŞ RAPOR ARAMA SİSTEMİ (DÜZENLİ ARŞİV) ---
rep = "Veri Yok"
secilen_icerik = "Görüntülenecek rapor bulunamadı."

try:
    st.sidebar.divider()
    st.sidebar.subheader("📂 İstihbarat Kütüphanesi")
    
    # 1. Arama Çubuğu
    search_query = st.sidebar.text_input("🔍 Raporlarda Ara", "", placeholder="Tarih veya kelime...")
    
    # 2. Tüm dosyaları çek
    dosyalar = glob.glob("ARSIV/*.md")
    # Yeniden eskiye sırala
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    
    # 3. Filtreleme
    if search_query:
        filtreli_dosyalar = [f for f in dosyalar if search_query.lower() in f.lower()]
    else:
        filtreli_dosyalar = dosyalar
        
    # 4. Temiz Liste Gösterimi (Dropdown)
    if filtreli_dosyalar:
        # Dosya yollarını temiz isimlere çevirerek göster
        dosya_isimleri = {os.path.basename(f).replace(".md", "").replace("_", " "): f for f in filtreli_dosyalar}
        secilen_isim = st.sidebar.selectbox("Mevcut Raporlar", list(dosya_isimleri.keys()))
        rep_path = dosya_isimleri[secilen_isim]
        
        # Seçilen raporu oku
        try:
            with open(rep_path, "r", encoding="utf-8") as f: secilen_icerik = f.read()
            rep = secilen_isim # Başlık için
        except: pass
    else:
        st.sidebar.warning("Kriterlere uygun rapor bulunamadı.")
        
except Exception as e: st.sidebar.error(f"Arşiv Hatası: {e}")

# --- ANA EKRAN ---
st.title("☁️ KÜRESEL SAVAŞ ODASI")
with st.spinner("İstihbarat Hazırlanıyor..."): hafizayi_guncelle()

col_sol, col_sag = st.columns([55, 45], gap="medium")

# SOL: RAPOR
with col_sol:
    st.subheader(f"📄 Rapor: {rep}")
    if rep != "Veri Yok":
        c = re.sub(r"```html|```", "", secilen_icerik)
        components.html(c, height=1000, scrolling=True)
    else:
        st.info("Arşivden bir rapor seçin veya arama yapın.")

# SAĞ: CHAT
with col_sag:
    st.subheader(f"🧠 Kanal: {st.session_state.current_session_name}")
    chat_container = st.container(height=850)
    msgs = st.session_state.chat_sessions[st.session_state.current_session_name]
    
    with chat_container:
        for m in msgs:
            with st.chat_message(m["role"]): st.markdown(m["content"])

    # 4. MESAJ GÖNDERME
    if q := st.chat_input("Analiz emredin..."):
        msgs.append({"role": "user", "content": q})
        with chat_container:
            with st.chat_message("user"): st.markdown(q)
        
        if not st.session_state.is_guest: 
            buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass, sessiz=True)

        with st.status(f"Analiz ediliyor ({'Hızlı' if '8B' in selected_model_id else 'Kapsamlı'} Model)...") as s:
            arsiv = hafizadan_getir(q)
            web = web_ara(q)
            s.update(label="Stratejik yanıt hazırlanıyor...", state="complete")
        
        with chat_container:
            with st.chat_message("assistant"):
                ph, full = st.empty(), ""
                sys_msg = {"role": "system", "content": "Sen Savaş Odası stratejistisin. Raporu ve verileri kullanarak derin analiz yap."}
                enhanced_q = {"role": "user", "content": f"SORU: {q}\n\n[ARŞİV]:\n{arsiv}\n\n[WEB]:\n{web}"}
                
                # --- ROTASYONEL FONKSİYON VE SEÇİLEN MODEL ---
                try:
                    stream = ask_ai_with_rotation(
                        [sys_msg] + msgs[-10:-1] + [enhanced_q], 
                        model_id=selected_model_id
                    )
                    
                    if stream:
                        for chunk in stream:
                            if chunk.choices[0].delta.content:
                                full += chunk.choices[0].delta.content
                                ph.markdown(full + "▌")
                        ph.markdown(full)
                        msgs.append({"role": "assistant", "content": full})
                        
                        if not st.session_state.is_guest: 
                            buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
                except Exception as e:
                    st.error(f"Kritik Hata: {e}")
