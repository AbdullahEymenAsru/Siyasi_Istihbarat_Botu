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

# -- TEMA YÖNETİMİ BAŞLANGICI --
if "theme" not in st.session_state:
    st.session_state.theme = "Karanlık"

# Tema Renk Paletleri (Python Kontrollü)
if st.session_state.theme == "Karanlık":
    v_bg = "#0E1117"
    v_text = "#E0E0E0"
    v_sidebar = "#161B22"
    v_chat = "rgba(255, 255, 255, 0.05)"
    v_input = "#262730"
    v_border = "rgba(128, 128, 128, 0.2)"
    v_accent = "#4CAF50"
else:
    v_bg = "#FFFFFF"
    v_text = "#1A1A1A"
    v_sidebar = "#F8F9FA"
    v_chat = "rgba(0, 0, 0, 0.05)"
    v_input = "#FFFFFF"
    v_border = "#DCDDE1"
    v_accent = "#2E7D32"

# Nihai CSS: Her iki modda da kusursuz görünüm sağlar
st.markdown(f"""
<style>
    /* Ana Uygulama */
    .stApp {{ background-color: {v_bg} !important; color: {v_text} !important; }}
    
    /* Tüm Yazılar */
    h1, h2, h3, h4, h5, h6, p, span, label, div, li, .stMarkdown {{ 
        color: {v_text} !important; 
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{ 
        background-color: {v_sidebar} !important; 
        border-right: 1px solid {v_border}; 
    }}
    [data-testid="stSidebar"] * {{ color: {v_text} !important; }}
    
    /* Input Alanları ve Seçim Kutuları */
    .stTextInput input, .stTextArea textarea, [data-baseweb="select"] div {{ 
        background-color: {v_input} !important; 
        color: {v_text} !important; 
        border: 1px solid {v_accent} !important; 
        border-radius: 5px !important; 
    }}
    
    /* Chat Mesaj Kutuları */
    [data-testid="stChatMessage"] {{ 
        background-color: {v_chat} !important; 
        border: 1px solid {v_border} !important; 
        border-radius: 10px; 
        margin-bottom: 10px !important; 
    }}
    
    /* Butonlar */
    .stButton button {{ background-color: {v_accent} !important; border: none !important; transition: 0.3s; }}
    .stButton button p {{ color: white !important; font-weight: bold !important; }}
    .stButton button:hover {{ opacity: 0.9; }}
    
    /* Tablar ve Linkler */
    button[data-baseweb="tab"] p {{ color: {v_text} !important; }}
    [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
    a {{ color: {v_accent} !important; text-decoration: none; }}
</style>
""", unsafe_allow_html=True)

# -- URL & API KONTROLLERİ --
SITE_URL = "https://siyasi-istihbarat-botu.streamlit.app/"

if "GROQ_API_KEY" not in st.secrets or "SUPABASE_URL" not in st.secrets:
    st.error("API Anahtarları Eksik! Lütfen Secrets ayarlarını kontrol edin.")
    st.stop()

client = Groq(api_key=st.secrets["GROQ_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Klasör Kontrolleri
for folder in ["ARSIV", "VEKTOR_DB"]:
    if not os.path.exists(folder): os.makedirs(folder)

# ==========================================
# 2. YARDIMCI SINIFLAR VE FONKSİYONLAR
# ==========================================

# -- EMBEDDING SINIFI --
class YerelEmbedder:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    def __call__(self, input):
        return self.model.encode(input).tolist()
    def name(self):
        return "YerelEmbedder"

# -- ŞİFRELEME --
def anahtar_turet(password, salt=b'SavasOdasiSabitTuz'):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def sifrele(veri_json, password):
    try:
        f = Fernet(anahtar_turet(password))
        veri_str = json.dumps(veri_json)
        return base64.urlsafe_b64encode(f.encrypt(veri_str.encode())).decode()
    except: return None

def sifreyi_coz(sifreli_str, password):
    try:
        f = Fernet(anahtar_turet(password))
        sifreli_byte = base64.urlsafe_b64decode(sifreli_str.encode())
        return json.loads(f.decrypt(sifreli_byte).decode())
    except: return {}

# -- VERİTABANI İŞLEMLERİ --
def giris_yap(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res.user
    except Exception as e:
        st.error(f"Giriş Başarısız: {e}")
        return None

def kayit_ol(email, password):
    try:
        res = supabase.auth.sign_up({
            "email": email, "password": password, "options": {"email_redirect_to": SITE_URL}
        })
        if res.user:
            try: supabase.table("abone_listesi").insert({"email": email}).execute()
            except: pass
            st.success("Kayıt Başarılı! Onay mailini kontrol edin.")
        return res.user
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return None

def sifre_sifirla(email):
    try:
        supabase.auth.reset_password_email(email, options={"redirect_to": SITE_URL})
        st.success("Sıfırlama bağlantısı gönderildi.")
    except Exception as e:
        st.error(f"Hata: {e}")

def buluttan_yukle(user_id, password):
    print(f"📥 Veri çekiliyor... ID: {user_id}")
    try:
        res = supabase.table("chat_logs").select("messages").eq("user_id", user_id).execute()
        if res.data:
            raw = res.data[0]["messages"]
            if isinstance(raw, dict) and "encrypted_data" in raw:
                return sifreyi_coz(raw["encrypted_data"], password)
            elif isinstance(raw, dict):
                return raw
        return {}
    except Exception as e:
        print(f"Yükleme hatası: {e}")
        return {}

def buluta_kaydet(user_id, data, password):
    try:
        sifreli = sifrele(data, password)
        if sifreli:
            supabase.table("chat_logs").upsert(
                {"user_id": user_id, "messages": {"encrypted_data": sifreli}}, 
                on_conflict="user_id"
            ).execute()
    except Exception as e: print(f"Kayıt hatası: {e}")

# -- AI VE RAG FONKSİYONLARI --
@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path="VEKTOR_DB")

@st.cache_resource
def get_embedding_function():
    return YerelEmbedder()

def hafizayi_guncelle():
    chroma = get_chroma_client()
    ef = get_embedding_function()
    col = chroma.get_or_create_collection(name="savas_odasi", embedding_function=ef)
    for d in glob.glob("ARSIV/*.md"):
        adi = os.path.basename(d)
        if not col.get(ids=[adi])['ids']:
            with open(d,"r",encoding="utf-8") as f: col.add(documents=[f.read()], metadatas=[{"source":adi}], ids=[adi])

def hafizadan_getir(soru):
    try:
        ef = get_embedding_function()
        col = get_chroma_client().get_collection(name="savas_odasi", embedding_function=ef)
        res = col.query(query_texts=[soru], n_results=3)
        return "\n".join(res['documents'][0]) if res['documents'] else "Arşivde veri yok."
    except: return "Hafıza hatası."

def web_ara(soru):
    try:
        res = DDGS().text(keywords=soru, region='tr-tr', max_results=3)
        return "\n".join([f"- {r['title']}: {r['body']}" for r in res]) if res else "Sonuç yok."
    except: return "Bağlantı hatası."

# ==========================================
# 3. UYGULAMA AKIŞI (MAIN LOOP)
# ==========================================

# Oturum Değişkenleri
if "user" not in st.session_state: st.session_state.user = None
if "is_guest" not in st.session_state: st.session_state.is_guest = False
if "password_cache" not in st.session_state: st.session_state.password_cache = None
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {"Genel Strateji": [{"role": "assistant", "content": "Komutanım, Savaş Odası hazır. Emrinizi bekliyorum."}]}
if "current_session_name" not in st.session_state:
    st.session_state.current_session_name = "Genel Strateji"

# --- GİRİŞ EKRANI ---
if not st.session_state.user and not st.session_state.is_guest:
    # Giriş Ekranı Tema Seçici (Sağ Üst)
    c_t1, c_t2 = st.columns([8, 2])
    with c_t2:
        l_theme = st.selectbox("🌓 Mod", ["Karanlık", "Açık"], 
                               index=0 if st.session_state.theme == "Karanlık" else 1,
                               key="login_theme_selector")
        if l_theme != st.session_state.theme:
            st.session_state.theme = l_theme
            st.rerun()

    st.title("🔐 SAVAŞ ODASI: GİRİŞ EKRANI")
    st.markdown("Verileriniz uçtan uca şifrelidir (E2EE). Misafir girişlerinde veri kaydedilmez.")
    
    # URL'den gelen Şifre Sıfırlama Token Kontrolü
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
        st.subheader("🔑 Üye Girişi")
        email = st.text_input("E-posta")
        password = st.text_input("Şifre", type="password") 

        if st.button("Giriş Yap"):
            if not email or not password:
                st.warning("E-posta ve şifre gereklidir.")
                st.stop()

            user = giris_yap(email, password)
            if user:
                st.session_state.user = user
                st.session_state.password_cache = password
                
                with st.spinner("Kriptolu arşiv çözülüyor..."):
                    yuklenen_veri = buluttan_yukle(user.id, password)

                if yuklenen_veri and len(yuklenen_veri) > 0:
                    st.session_state.chat_sessions = yuklenen_veri
                    st.session_state.current_session_name = list(yuklenen_veri.keys())[0]
                    st.success(f"✅ {len(yuklenen_veri)} adet şifreli sohbet yüklendi.")
                    time.sleep(1)
                else:
                    st.warning("Kayıtlı veri bulunamadı veya şifre değişikliği nedeniyle erişilemiyor.")
                    st.session_state.chat_sessions = {"Genel Strateji": [{"role": "assistant", "content": "Komutanım, Savaş Odası hazır."}]}
                    st.session_state.current_session_name = "Genel Strateji"
                st.rerun()

        st.markdown("---")
        with st.expander("❓ Şifremi Unuttum"):
            reset_mail = st.text_input("Kayıtlı E-posta")
            if st.button("Sıfırlama Linki Gönder"):
                if reset_mail: sifre_sifirla(reset_mail)

        with st.expander("📝 Yeni Hesap"):
            new_email = st.text_input("Yeni E-posta")
            new_pass = st.text_input("Yeni Şifre", type="password")
            if st.button("Kayıt Ol"):
                if new_email and new_pass: kayit_ol(new_email, new_pass)

    with col2:
        st.subheader("🕵️ Misafir")
        st.info("Kayıt tutulmaz.")
        if st.button("Misafir Olarak Devam Et >>"):
            st.session_state.is_guest = True
            st.rerun()
    st.stop()

# --- İÇERİK EKRANI (SIDEBAR & MAIN) ---

# Sidebar: Kullanıcı Bilgisi
if st.session_state.is_guest:
    st.sidebar.warning("🕵️ MOD: MİSAFİR")
    user_id = "guest"
    user_pass = None
else:
    st.sidebar.success(f"Ajan: {st.session_state.user.email}")
    st.sidebar.info("🔒 E2EE Şifreleme Aktif")
    user_id = st.session_state.user.id
    user_pass = st.session_state.password_cache

st.sidebar.markdown("---")

# Sidebar: Tema Seçici (Senkronize)
st.sidebar.header("⚙️ SİSTEM AYARLARI")
s_theme = st.sidebar.selectbox("Görünüm Modu", ["Karanlık", "Açık"], 
                               index=0 if st.session_state.theme == "Karanlık" else 1,
                               key="sidebar_theme_selector")
if s_theme != st.session_state.theme:
    st.session_state.theme = s_theme
    st.rerun()

st.sidebar.header("🗄️ Operasyon Kayıtları")

# Yeni Sohbet
if st.sidebar.button("➕ YENİ SOHBET BAŞLAT", type="primary"):
    new_name = f"Operasyon_{datetime.now().strftime('%H%M%S')}"
    st.session_state.chat_sessions[new_name] = []
    st.session_state.current_session_name = new_name
    if not st.session_state.is_guest:
        buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
    st.rerun()

# Sohbet Seçimi
session_names = list(st.session_state.chat_sessions.keys())
try: secili_index = session_names.index(st.session_state.current_session_name)
except: secili_index = 0

selected_session = st.sidebar.selectbox(
    "Geçmiş Kayıtlar:", session_names, index=secili_index, key="session_select"
)

if selected_session != st.session_state.current_session_name:
    st.session_state.current_session_name = selected_session
    st.rerun()

# İsim Düzenleme
new_session_name = st.sidebar.text_input("📝 Sohbet Adını Düzenle", value=st.session_state.current_session_name)
if new_session_name != st.session_state.current_session_name:
    if new_session_name and new_session_name not in st.session_state.chat_sessions:
        data = st.session_state.chat_sessions.pop(st.session_state.current_session_name)
        st.session_state.chat_sessions[new_session_name] = data
        st.session_state.current_session_name = new_session_name
        if not st.session_state.is_guest:
            buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
        st.rerun()

# Silme ve Çıkış
if st.sidebar.button("🗑️ Bu Kaydı İmha Et"):
    if len(session_names) > 1:
        del st.session_state.chat_sessions[st.session_state.current_session_name]
        st.session_state.current_session_name = list(st.session_state.chat_sessions.keys())[0]
        if not st.session_state.is_guest:
            buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("Çıkış Yap"):
    if not st.session_state.is_guest: supabase.auth.sign_out()
    st.session_state.clear()
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

# --- ANA EKRAN (YAN YANA DÜZEN) ---
st.title("☁️ KÜRESEL SAVAŞ ODASI")
with st.spinner("Sistem Hazırlanıyor..."): hafizayi_guncelle()

# Ekranı iki ana sütuna bölüyoruz: %55 Rapor, %45 Chat
col_rapor, col_chat = st.columns([55, 45], gap="medium")

# --- SOL SÜTUN: RAPOR GÖRÜNÜMÜ ---
with col_rapor:
    st.subheader(f"📄 İstihbarat Raporu: {sec if files else 'Veri Yok'}")
    if secilen_icerik != "Veri yok":
        # HTML temizliği
        clean_html = re.sub(r"```html|```", "", secilen_icerik)
        # Raporu kaydırılabilir bir kutu içinde göster
        st.components.v1.html(clean_html, height=1000, scrolling=True)
    else:
        st.info("Arşivde görüntülenecek rapor bulunamadı.")

# --- SAĞ SÜTUN: STRATEJİK CHAT ---
with col_chat:
    st.subheader(f"🧠 Kanal: {st.session_state.current_session_name}")
    
    # Sohbet geçmişini göstermek için bir konteyner
    chat_container = st.container(height=850)
    
    current_messages = st.session_state.chat_sessions[st.session_state.current_session_name]

    with chat_container:
        for m in current_messages:
            with st.chat_message(m["role"]): 
                st.markdown(m["content"])

    # Chat girişi
    if q := st.chat_input("Rapor hakkında analiz isteyin veya emredin..."):
        # Kullanıcı mesajını ekle ve göster
        current_messages.append({"role": "user", "content": q})
        with chat_container:
            with st.chat_message("user"): st.markdown(q)
        
        # Kayıt (Ziyaretçi değilse)
        if not st.session_state.is_guest:
             buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)

        # Bilgi toplama aşaması
        with st.status("İstihbarat toplanıyor...") as s:
            arsiv = hafizadan_getir(q)
            web = web_ara(q)
            s.update(label="Analiz ediliyor...", state="complete")

        # Asistan yanıtı
        with chat_container:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                recent_history = current_messages[-10:]
                enriched_last_message = {
                    "role": "user",
                    "content": f"SORU: {q}\n\n[SİSTEM BİLGİSİ - ARŞİV]:\n{arsiv}\n\n[SİSTEM BİLGİSİ - WEB]:\n{web}"
                }
                api_messages = [
                    {"role": "system", "content": "Sen Savaş Odası stratejistisin. Yan taraftaki raporu ve arşiv verilerini kullanarak derinlemesine analiz yap."}
                ] + recent_history[:-1] + [enriched_last_message]

                try:
                    stream = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=api_messages,
                        stream=True,
                        temperature=0.6,
                        max_tokens=1024
                    )
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                    
                    current_messages.append({"role": "assistant", "content": full_response})

                    # Final Kayıt
                    if not st.session_state.is_guest:
                        buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")
