import streamlit as st
import os
import glob
import json
import base64
import time 
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
# 1. AYARLAR, TEMA MOTORU & KUSURSUZ CSS
# ==========================================

st.set_page_config(page_title="Savaş Odası (GUEST & E2EE)", page_icon="🛡️", layout="wide")

# -- TEMA YÖNETİMİ --
if "theme" not in st.session_state:
    st.session_state.theme = "Karanlık"

# Tema Renk Paletleri - Kesin Karşıtlık (Contrast)
if st.session_state.theme == "Karanlık":
    v_bg = "#0E1117"        # Derin Siyah
    v_text = "#FFFFFF"      # Saf Beyaz
    v_sidebar = "#161B22"   # Sidebar
    v_chat_bg = "#1A1C24"   # Chat Balonu
    v_input_bg = "#262730"  # Input Alanı
    v_border = "#30363D"    # Çerçeveler
    v_accent = "#4CAF50"    # Vurgu Yeşili
else:
    v_bg = "#FFFFFF"        # Beyaz
    v_text = "#121212"      # Koyu Siyah
    v_sidebar = "#F8F9FA"   # Açık Gri Sidebar
    v_chat_bg = "#F0F2F6"   # Açık Gri Chat
    v_input_bg = "#FFFFFF"  # Beyaz Input
    v_border = "#DCDDE1"    # Gri Çerçeve
    v_accent = "#2E7D32"    # Koyu Yeşil

# Nihai CSS: Streamlit'in varsayılanlarını ezer
st.markdown(f"""
<style>
    /* 1. Ana Uygulama */
    .stApp {{ background-color: {v_bg} !important; color: {v_text} !important; }}
    
    /* 2. Tüm Yazılar */
    h1, h2, h3, h4, h5, h6, p, span, label, div, li, .stMarkdown, .stText {{ 
        color: {v_text} !important; 
    }}
    
    /* 3. Sidebar */
    section[data-testid="stSidebar"] {{ 
        background-color: {v_sidebar} !important; 
        border-right: 1px solid {v_border} !important; 
    }}
    section[data-testid="stSidebar"] * {{ color: {v_text} !important; }}
    
    /* 4. Input Alanları */
    .stTextInput input, .stTextArea textarea, [data-baseweb="select"] div {{ 
        background-color: {v_input_bg} !important; 
        color: {v_text} !important; 
        border: 1px solid {v_accent} !important; 
        border-radius: 5px !important;
        -webkit-text-fill-color: {v_text} !important;
    }}
    
    /* 5. Chat Mesaj Kutuları */
    [data-testid="stChatMessage"] {{ 
        background-color: {v_chat_bg} !important; 
        border: 1px solid {v_border} !important; 
        border-radius: 10px; 
        margin-bottom: 10px !important; 
    }}
    
    /* 6. Butonlar */
    .stButton button {{ 
        background-color: {v_accent} !important; 
        color: white !important;
        border: none !important; 
        transition: 0.3s; 
    }}
    .stButton button p {{ color: white !important; font-weight: bold !important; }}
    .stButton button:hover {{ opacity: 0.9; }}
    
    /* 7. Tablar ve Linkler */
    button[data-baseweb="tab"] p {{ color: {v_text} !important; }}
    [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
    a {{ color: {v_accent} !important; text-decoration: none; font-weight: bold; }}
    
    /* 8. Rapor Alanı */
    .stHtmlContainer {{ color: {v_text} !important; background-color: transparent !important; }}
    svg {{ fill: {v_text} !important; }}
</style>
""", unsafe_allow_html=True)

# -- URL & API --
SITE_URL = "https://siyasi-istihbarat-botu.streamlit.app/"

if "GROQ_API_KEY" not in st.secrets or "SUPABASE_URL" not in st.secrets:
    st.error("API Anahtarları Eksik!")
    st.stop()

client = Groq(api_key=st.secrets["GROQ_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

for folder in ["ARSIV", "VEKTOR_DB"]:
    if not os.path.exists(folder): os.makedirs(folder)

# ==========================================
# 2. ÇEKİRDEK FONKSİYONLAR
# ==========================================

class YerelEmbedder:
    def __init__(self): self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    def __call__(self, input): return self.model.encode(input).tolist()

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
        st.success("Sıfırlama bağlantısı gönderildi.")
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

def buluta_kaydet(user_id, data, password):
    encrypted = sifrele(data, password)
    if encrypted: supabase.table("chat_logs").upsert({"user_id": user_id, "messages": {"encrypted_data": encrypted}}, on_conflict="user_id").execute()

@st.cache_resource
def get_chroma(): return chromadb.PersistentClient(path="VEKTOR_DB")
@st.cache_resource
def get_embedder(): return YerelEmbedder()

def hafizayi_guncelle():
    col = get_chroma().get_or_create_collection(name="savas_odasi", embedding_function=get_embedder())
    for d in glob.glob("ARSIV/*.md"):
        if not col.get(ids=[os.path.basename(d)])['ids']:
            with open(d,"r",encoding="utf-8") as f: col.add(documents=[f.read()], ids=[os.path.basename(d)])

def hafizadan_getir(soru):
    try:
        res = get_chroma().get_collection(name="savas_odasi", embedding_function=get_embedder()).query(query_texts=[soru], n_results=3)
        return "\n".join(res['documents'][0])
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

# --- GİRİŞ EKRANI ---
if not st.session_state.user and not st.session_state.is_guest:
    col_lt1, col_lt2 = st.columns([8, 2])
    with col_lt2:
        lt = st.selectbox("🌓 Görünüm", ["Karanlık", "Açık"], index=0 if st.session_state.theme=="Karanlık" else 1, key="login_theme")
        if lt != st.session_state.theme: st.session_state.theme = lt; st.rerun()

    st.title("🔐 SAVAŞ ODASI: GİRİŞ")
    
    if "type" in st.query_params and st.query_params["type"] == "recovery":
        st.info("🔄 Şifre Sıfırlama Modu")
        new_pass_reset = st.text_input("Yeni Şifre", type="password")
        if st.button("Şifreyi Güncelle"):
            try:
                supabase.auth.update_user({"password": new_pass_reset})
                st.success("Şifre güncellendi! Giriş yapabilirsiniz.")
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
        
        with st.expander("Şifremi Unuttum"):
            rm = st.text_input("Mail Adresi")
            if st.button("Sıfırlama Gönder"): sifre_sifirla(rm)

        with st.expander("Yeni Kayıt"):
            ne = st.text_input("Yeni E-posta", key="ne")
            np = st.text_input("Yeni Şifre", type="password", key="np")
            if st.button("Kayıt Ol"): kayit_ol(ne, np)

    with col2:
        st.subheader("🕵️ Misafir")
        if st.button("Kayıtsız Devam Et >>"): st.session_state.is_guest = True; st.rerun()
    st.stop()

# --- SIDEBAR ---
user_id = st.session_state.user.id if st.session_state.user else "guest"
user_pass = st.session_state.password_cache

st.sidebar.header("⚙️ SİSTEM")
st_theme = st.sidebar.selectbox("Görünüm Modu", ["Karanlık", "Açık"], index=0 if st.session_state.theme=="Karanlık" else 1, key="st")
if st_theme != st.session_state.theme: st.session_state.theme = st_theme; st.rerun()

st.sidebar.header("🗄️ Kayıtlar")
if st.sidebar.button("➕ YENİ SOHBET"):
    n = f"Op_{datetime.now().strftime('%H%M%S')}"
    st.session_state.chat_sessions[n] = []
    st.session_state.current_session_name = n
    st.rerun()

sess = list(st.session_state.chat_sessions.keys())
sel = st.sidebar.selectbox("Geçmiş", sess, index=sess.index(st.session_state.current_session_name))
if sel != st.session_state.current_session_name: st.session_state.current_session_name = sel; st.rerun()

new_n = st.sidebar.text_input("İsim Değiştir", value=st.session_state.current_session_name)
if new_n != st.session_state.current_session_name and new_n:
    st.session_state.chat_sessions[new_n] = st.session_state.chat_sessions.pop(st.session_state.current_session_name)
    st.session_state.current_session_name = new_n
    if not st.session_state.is_guest: buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
    st.rerun()

if st.sidebar.button("🗑️ İmha Et"):
    if len(sess) > 1:
        del st.session_state.chat_sessions[st.session_state.current_session_name]
        st.session_state.current_session_name = list(st.session_state.chat_sessions.keys())[0]
        if not st.session_state.is_guest: buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
        st.rerun()

if st.sidebar.button("Çıkış"): st.session_state.clear(); st.rerun()

# --- KRİTİK DÜZELTME: NameError (rep) ENGELLEME BLOĞU ---
# Değişkenleri varsayılan olarak tanımlıyoruz ki hata almasın
rep = "Veri Yok"
secilen_icerik = "Görüntülenecek rapor bulunamadı."

try:
    dosyalar = glob.glob("ARSIV/*.md")
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    
    if dosyalar:
        files = [os.path.basename(f) for f in dosyalar]
        rep = st.sidebar.radio("📁 Rapor Arşivi", files)
        
        # Dosya seçildiyse içeriğini oku
        try:
            with open(f"ARSIV/{rep}", "r", encoding="utf-8") as f:
                secilen_icerik = f.read()
        except:
            secilen_icerik = "Dosya okunamadı."
except Exception as e:
    st.sidebar.error(f"Arşiv hatası: {e}")

# --- ANA EKRAN (SPLIT-SCREEN) ---
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
        st.info(secilen_icerik)

# SAĞ: CHAT
with col_sag:
    st.subheader(f"🧠 Kanal: {st.session_state.current_session_name}")
    chat_container = st.container(height=850)
    msgs = st.session_state.chat_sessions[st.session_state.current_session_name]
    
    with chat_container:
        for m in msgs:
            with st.chat_message(m["role"]): st.markdown(m["content"])

    if q := st.chat_input("Analiz emredin..."):
        msgs.append({"role": "user", "content": q})
        with chat_container:
            with st.chat_message("user"): st.markdown(q)
        
        if not st.session_state.is_guest:
             buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)

        with st.status("Veriler analiz ediliyor...") as s:
            arsiv = hafizadan_getir(q)
            web = web_ara(q)
            s.update(label="Stratejik yanıt hazırlanıyor...", state="complete")
        
        with chat_container:
            with st.chat_message("assistant"):
                ph = st.empty()
                full = ""
                sys_msg = {"role": "system", "content": "Sen Savaş Odası stratejistisin. Raporu ve verileri kullanarak derin analiz yap."}
                enhanced_q = {"role": "user", "content": f"SORU: {q}\n\nARŞİV: {arsiv}\n\nWEB: {web}"}
                
                try:
                    stream = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[sys_msg] + msgs[-10:-1] + [enhanced_q], stream=True)
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            full += chunk.choices[0].delta.content
                            ph.markdown(full + "▌")
                    ph.markdown(full)
                    msgs.append({"role": "assistant", "content": full})
                    if not st.session_state.is_guest: buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
                except Exception as e: st.error(f"Hata: {e}")
