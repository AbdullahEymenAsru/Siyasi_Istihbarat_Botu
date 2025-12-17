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

st.set_page_config(page_title="Savaş Odası HQ", page_icon="🛡️", layout="wide")

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

# CSS - Görsel Etiketler ve Düzen
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
    
    /* Model Etiketi Tasarımı */
    .model-tag {{
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 1px;
        padding: 3px 8px;
        border-radius: 4px;
        background: {v_accent}; 
        color: white;
        margin-bottom: 5px;
        display: inline-block;
        text-transform: uppercase;
        border: 1px solid rgba(255,255,255,0.2);
    }}
</style>
""", unsafe_allow_html=True)

# -- API KONTROLLERİ VE ROTASYON LİSTESİ --
SITE_URL = "https://siyasi-istihbarat-botu.streamlit.app/"

if "GROQ_API_KEY" not in st.secrets or "SUPABASE_URL" not in st.secrets:
    st.error("API Anahtarları Eksik!")
    st.stop()

# Çift Mühimmat Hattı
GROQ_KEYS = [
    st.secrets.get("GROQ_API_KEY"),
    st.secrets.get("GROQ_API_KEY_2")
]

supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

if not os.path.exists("ARSIV"): os.makedirs("ARSIV")

# ==========================================
# 2. ÇEKİRDEK FONKSİYONLAR
# ==========================================

def ask_ai_with_rotation(messages, model_id):
    """
    Seçilen model ile API çağrısı yapar. Kota dolarsa yedeğe geçer.
    """
    for i, key in enumerate(GROQ_KEYS):
        if not key: continue
        try:
            temp_client = Groq(api_key=key)
            return temp_client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=True
            )
        except Exception as e:
            if "429" in str(e): # Kota Doldu
                st.toast(f"⚠️ {i+1}. Mühimmat Hattı Tükendi, Yedek Hatta Geçiliyor...", icon="🔄")
                continue
            else:
                st.error(f"Sistem Hatası: {e}")
                return None
    st.error("❌ Kritik: Tüm API mühimmatı tükendi!")
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
    try:
        sifreli = sifrele(data, password)
        if sifreli:
            supabase.table("chat_logs").upsert(
                {"user_id": user_id, "messages": {"encrypted_data": sifreli}}, 
                on_conflict="user_id"
            ).execute()
            if not sessiz: st.toast("✅ Veriler Senkronize Edildi", icon="☁️")
    except Exception as e: 
        if not sessiz: st.error(f"Kayıt Hatası: {e}")

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
        return "\n".join(res['documents'][0]) if res['documents'] else ""
    except: return ""

def web_ara(soru):
    try:
        res = DDGS().text(keywords=soru, region='tr-tr', max_results=3)
        return "\n".join([f"- {r['title']}: {r['body']}" for r in res])
    except: return ""

# ==========================================
# 3. UYGULAMA AKIŞI
# ==========================================

if "user" not in st.session_state: st.session_state.user = None
if "is_guest" not in st.session_state: st.session_state.is_guest = False
if "password_cache" not in st.session_state: st.session_state.password_cache = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {"Genel Strateji": []}
if "current_session_name" not in st.session_state: st.session_state.current_session_name = "Genel Strateji"
if "model_mode" not in st.session_state: st.session_state.model_mode = "deep" # Varsayılan: Derin

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

# --- SIDEBAR: ARŞİV VE AYARLAR ---
user_id = st.session_state.user.id if st.session_state.user else "guest"
user_pass = st.session_state.password_cache

st.sidebar.header("⚙️ SİSTEM")
st_theme = st.sidebar.selectbox("Görünüm", ["Karanlık", "Açık"], index=0 if st.session_state.theme=="Karanlık" else 1, key="st")
if st_theme != st.session_state.theme: st.session_state.theme = st_theme; st.rerun()

st.sidebar.divider()

# --- YENİLENEN HİYERARŞİK ARŞİV SİSTEMİ ---
st.sidebar.header("🗄️ STRATEJİK ARŞİV")

# Arama motoru her zaman en üstte
search_query = st.sidebar.text_input("🔍 Hızlı Dosya Ara", "", placeholder="Tarih veya konu...")

# Dosya listesini hazırla
dosyalar = sorted(glob.glob("ARSIV/*.md"), key=os.path.getmtime, reverse=True)

# HİYERARŞİ OLUŞTURMA MANTIĞI
if not search_query:
    # Dosya isimlerinden YIL bilgisini çek (Regex: 4 haneli sayı)
    years = sorted(list(set([re.search(r"\d{4}", os.path.basename(f)).group() for f in dosyalar if re.search(r"\d{4}", os.path.basename(f))])), reverse=True)
    
    if years:
        selected_year = st.sidebar.selectbox("📅 Yıl Seçin", years)
        
        # Seçilen yıla ait AY bilgisini çek (Regex: -dd-)
        months = sorted(list(set([re.search(r"-(\d{2})-", os.path.basename(f)).group(1) for f in dosyalar if selected_year in os.path.basename(f) and re.search(r"-(\d{2})-", os.path.basename(f))])), reverse=True)
        
        if months:
            selected_month = st.sidebar.selectbox("🗓️ Ay Seçin", months)
            # O aya ait dosyaları filtrele
            filtreli_dosyalar = [f for f in dosyalar if f"{selected_year}-{selected_month}" in os.path.basename(f)]
        else: 
            # Ay bulunamazsa sadece yıla göre filtrele
            filtreli_dosyalar = [f for f in dosyalar if selected_year in os.path.basename(f)]
    else: 
        filtreli_dosyalar = dosyalar
else:
    # Arama yapılıyorsa hiyerarşiyi baypas et
    filtreli_dosyalar = [f for f in dosyalar if search_query.lower() in f.lower()]

rep = "Veri Yok"
secilen_icerik = "Görüntülenecek rapor bulunamadı."

if filtreli_dosyalar:
    # Dosya isimlerini temizleyerek göster
    dosya_map = {os.path.basename(f).replace(".md", "").replace("_", " "): f for f in filtreli_dosyalar}
    secilen_isim = st.sidebar.selectbox("📄 Raporlar", list(dosya_map.keys()))
    
    if secilen_isim:
        try:
            with open(dosya_map[secilen_isim], "r", encoding="utf-8") as f: secilen_icerik = f.read()
            rep = secilen_isim
        except: pass
else:
    st.sidebar.caption("Kriterlere uygun kayıt bulunamadı.")

st.sidebar.divider()
st.sidebar.header("💬 SOHBET YÖNETİMİ")

if st.sidebar.button("➕ YENİ SOHBET"):
    n = f"Op_{datetime.now().strftime('%H%M%S')}"
    st.session_state.chat_sessions[n] = []
    st.session_state.current_session_name = n
    if not st.session_state.is_guest: 
        buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
    st.rerun()

sess = list(st.session_state.chat_sessions.keys())
sel = st.sidebar.selectbox("Geçmiş", sess, index=sess.index(st.session_state.current_session_name))
if sel != st.session_state.current_session_name: st.session_state.current_session_name = sel; st.rerun()

if st.sidebar.button("🗑️ İmha Et"):
    current = st.session_state.current_session_name
    if len(st.session_state.chat_sessions) > 1:
        del st.session_state.chat_sessions[current]
        st.session_state.current_session_name = list(st.session_state.chat_sessions.keys())[0]
    else:
        st.session_state.chat_sessions[current] = [] 
        st.toast("Kayıtlar yakıldı.", icon="🔥")
    
    if not st.session_state.is_guest: 
        buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
    st.rerun()

if st.sidebar.button("Çıkış"): st.session_state.clear(); st.rerun()

# --- ANA EKRAN ---
st.title("☁️ KÜRESEL SAVAŞ ODASI")
with st.spinner("Sistem Hazırlanıyor..."): hafizayi_guncelle()

col_sol, col_sag = st.columns([55, 45], gap="medium")

# SOL: RAPOR GÖRÜNTÜLEME
with col_sol:
    st.subheader(f"📄 Dosya: {rep}")
    if rep != "Veri Yok":
        c = re.sub(r"```html|```", "", secilen_icerik)
        components.html(c, height=900, scrolling=True)
    else:
        st.info("İstihbarat kütüphanesinden bir dosya seçin veya arama yapın.")

# SAĞ: ANALİZ VE KOMUTA MERKEZİ
with col_sag:
    st.markdown("### 🧠 ANALİZ BİRİMİ KOMUTASI")
    
    # --- YENİ MODEL SEÇİM PANELİ (ÜSTTE) ---
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.info("**⚡ SERİ MÜDAHALE**\n\nHızlı yanıt, az tüketim. Günlük işler için.")
        if st.button("🚀 Modu Aktif Et", key="btn_fast", use_container_width=True):
            st.session_state.model_mode = "fast"
            st.toast("Hızlı Moda Geçildi.")
            
    with m_col2:
        st.success("**🔬 DERİN STRATEJİ**\n\nDetaylı analiz, yüksek tüketim. Kritik kararlar için.")
        if st.button("🧠 Modu Aktif Et", key="btn_deep", use_container_width=True):
            st.session_state.model_mode = "deep"
            st.toast("Derin Strateji Moduna Geçildi.")

    # Seçili moda göre model ID belirle
    selected_model_id = "llama-3.1-8b-instant" if st.session_state.model_mode == "fast" else "llama-3.3-70b-versatile"
    current_label = "⚡ SERİ MÜDAHALE" if st.session_state.model_mode == "fast" else "🔬 DERİN STRATEJİ"
    
    st.caption(f"Aktif Birim: **{current_label}**")
    st.divider()

    st.subheader(f"📡 Kanal: {st.session_state.current_session_name}")
    chat_container = st.container(height=650)
    msgs = st.session_state.chat_sessions[st.session_state.current_session_name]
    
    with chat_container:
        for m in msgs:
            # Görsel Etiket: Hangi model kullanıldı?
            if m["role"] == "assistant" and "mode" in m:
                st.markdown(f"<div class='model-tag'>{m['mode']}</div>", unsafe_allow_html=True)
            with st.chat_message(m["role"]): st.markdown(m["content"])

    # 4. MESAJ GÖNDERME
    if q := st.chat_input("Analiz emredin..."):
        msgs.append({"role": "user", "content": q})
        chat_container.chat_message("user").markdown(q)
        
        if not st.session_state.is_guest: 
            buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass, sessiz=True)

        with st.status("Veriler işleniyor...") as s:
            arsiv = hafizadan_getir(q)
            web = web_ara(q)
            s.update(label="Stratejik yanıt oluşturuluyor...", state="complete")
        
        with chat_container:
            with st.chat_message("assistant"):
                ph, full = st.empty(), ""
                sys_msg = {"role": "system", "content": "Sen Savaş Odası stratejistisin. Raporu ve verileri kullanarak doktriner analiz yap."}
                enhanced_q = {"role": "user", "content": f"SORU: {q}\n\n[ARŞİV]:\n{arsiv}\n\n[WEB]:\n{web}"}
                
                # Çift API Rotasyonu ile Çağrı
                try:
                    stream = ask_ai_with_rotation(
                        [sys_msg] + msgs[-8:-1] + [enhanced_q], 
                        model_id=selected_model_id
                    )
                    
                    if stream:
                        for chunk in stream:
                            if chunk.choices[0].delta.content:
                                full += chunk.choices[0].delta.content
                                ph.markdown(full + "▌")
                        ph.markdown(full)
                        
                        # Mod etiketiyle kaydet
                        msgs.append({"role": "assistant", "content": full, "mode": current_label})
                        
                        if not st.session_state.is_guest: 
                            buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
                except Exception as e:
                    st.error(f"Operasyon Hatası: {e}")
