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

# Dil Ayarı (Varsayılan)
if "lang" not in st.session_state:
    st.session_state.lang = "Türkçe"

# Dinamik Dil Sözlüğü
L = {
    "Türkçe": {
        "title": "KÜRESEL SAVAŞ ODASI",
        "archive": "🗄️ STRATEJİK ARŞİV",
        "search": "🔍 Hızlı Ara",
        "year": "📅 Yıl",
        "month": "🗓️ Ay",
        "day": "📆 Gün",
        "records": "📄 Kayıtlar",
        "new_chat": "➕ YENİ SOHBET",
        "history": "Sohbet Geçmişi",
        "destroy": "🗑️ İmha Et",
        "logout": "🚪 Çıkış",
        "report_view": "📄 Rapor Görünümü",
        "analysis_center": "### 🧠 ANALİZ MERKEZİ",
        "fast_mode": "🚀 SERİ MÜDAHALE\n(Hızlı & Az Mühimmat)",
        "deep_mode": "🔬 DERİN STRATEJİ\n(Detaylı & Çok Mühimmat)",
        "input_placeholder": "Analiz emredin...",
        "system_prompt": "Sen Savaş Odası stratejistisin. Yanıtlarını Türkçe ver.",
        "status": "Küresel veriler analiz ediliyor...",
        "settings": "⚙️ AYARLAR",
        "panel": "📊 ANA PANEL"
    },
    "English": {
        "title": "GLOBAL WAR ROOM",
        "archive": "🗄️ STRATEGIC ARCHIVE",
        "search": "🔍 Quick Search",
        "year": "📅 Year",
        "month": "🗓️ Month",
        "day": "📆 Day",
        "records": "📄 Records",
        "new_chat": "➕ NEW CHAT",
        "history": "Chat History",
        "destroy": "🗑️ Destroy",
        "logout": "🚪 Logout",
        "report_view": "📄 Report View",
        "analysis_center": "### 🧠 ANALYSIS CENTER",
        "fast_mode": "🚀 RAPID RESPONSE\n(Fast & Low Ammo)",
        "deep_mode": "🔬 DEEP STRATEGY\n(Detailed & High Ammo)",
        "input_placeholder": "Command an analysis...",
        "system_prompt": "You are a War Room strategist. Always provide responses in English.",
        "status": "Analyzing global data...",
        "settings": "⚙️ SETTINGS",
        "panel": "📊 MAIN PANEL"
    }
}

curr = L[st.session_state.lang]

# Renk Paletleri
if st.session_state.theme == "Karanlık":
    v_bg, v_text, v_sidebar = "#0E1117", "#FFFFFF", "#161B22"
    v_chat_bg, v_input_bg = "#1A1C24", "#262730"
    v_border, v_accent = "#30363D", "#4CAF50"
else:
    v_bg, v_text, v_sidebar = "#FFFFFF", "#121212", "#F8F9FA"
    v_chat_bg, v_input_bg = "#F0F2F6", "#FFFFFF"
    v_border, v_accent = "#DCDDE1", "#2E7D32"

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
# 2. YARDIMCI ARAÇLAR VE FONKSİYONLAR
# ==========================================

AYLAR = {
    "01": "Ocak", "02": "Şubat", "03": "Mart", "04": "Nisan", 
    "05": "Mayıs", "06": "Haziran", "07": "Temmuz", "08": "Ağustos", 
    "09": "Eylül", "10": "Ekim", "11": "Kasım", "12": "Aralık"
}

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

def ask_ai_with_rotation(messages, model_id):
    """Kota dolduğunda otomatik olarak diğer anahtara geçer."""
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
            if "429" in str(e): 
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
        if res.user: 
            # Kayıt anında varsayılan olarak Türkçe ekle (Sonra değiştirilebilir)
            supabase.table("abone_listesi").insert({"email": email, "aktif_dil": "Türkçe", "aktif": True}).execute()
        return res.user
    except: return None

def sifre_sifirla(email):
    try:
        supabase.auth.reset_password_email(email, options={"redirect_to": SITE_URL})
        st.success("Bağlantı e-posta adresinize gönderildi.")
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

# --- HİBRİT ARAMA MOTORU (YENİ) ---
def web_ara_kuresel(soru):
    """Her koşulda hem Türkçe hem İngilizce (Küresel) arama yapar."""
    try:
        combined_results = []
        with DDGS() as ddgs:
            # 1. Küresel (İngilizce) Arama
            res_en = ddgs.text(keywords=soru, region='wt-wt', max_results=2)
            combined_results.extend([f"[Global-EN] {r['title']}: {r['body']}" for r in res_en])
            
            # 2. Bölgesel (Türkçe) Arama
            res_tr = ddgs.text(keywords=soru, region='tr-tr', max_results=2)
            combined_results.extend([f"[Regional-TR] {r['title']}: {r['body']}" for r in res_tr])
            
        return "\n".join(combined_results)
    except: return "Arama yapılamadı."

# --- RAPOR DÜZELTME (SABİT TEMA) ---
def rapor_duzelt(html_content):
    """
    Raporu Streamlit temasından tamamen bağımsız hale getirir.
    Beyaz zemin üzerine siyah yazı zorlar ve AI'nın renkli kutularını (div)
    açık renge dönüştürerek okunurluğu %100 garanti eder.
    """
    temiz_html = re.sub(r"```html|```", "", html_content)
    
    # İframe içine gömülecek stiller (Streamlit dışı, izole ortam)
    sabit_stil = """
    <style>
        body { 
            background-color: #ffffff !important; 
            color: #000000 !important; 
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif !important; 
            padding: 20px !important;
            margin: 0 !important;
        }
        /* AI'nın oluşturduğu koyu renkli kutuları açık renge zorla */
        div[style*="background-color"] { 
            background-color: #fffafa !important; /* Çok açık kırmızı/beyaz */
            color: #000000 !important; /* Metni Siyah Yap */
            border: 2px solid #cc0000 !important; /* Çerçeveyi koru */
            padding: 15px !important;
            border-radius: 8px !important;
            margin-bottom: 20px !important;
        }
        h1, h2, h3 { color: #cc0000 !important; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        p, li, span, div { color: #1a1a1a !important; line-height: 1.6 !important; }
        a { color: #0066cc !important; text-decoration: underline !important; }
        strong, b { color: #000000 !important; font-weight: 700 !important; }
        
        /* Genel Kutu Görünümü */
        .report-container {
            background-color: #fdfdfd;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
    </style>
    """
    
    return f"{sabit_stil}<div class='report-container'>{temiz_html}</div>"

# --- AYARLAR MENÜSÜ FONKSİYONU (YENİ EKLENDİ) ---
def ayarlar_sayfasi():
    st.title("⚙️ " + ( "KARARGAH AYARLARI" if st.session_state.lang == "Türkçe" else "HQ SETTINGS" ))
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📧 Mail & Dil / Language")
        user_email = st.session_state.user.email
        
        # Mevcut dili Supabase'den çek
        try:
            res = supabase.table("abone_listesi").select("aktif_dil").eq("email", user_email).execute()
            mevcut_db_dil = res.data[0]['aktif_dil'] if res.data else "Türkçe"
        except:
            mevcut_db_dil = "Türkçe"
            
        yeni_dil = st.selectbox(
            "Rapor Dili / Report Language", 
            ["Türkçe", "English"], 
            index=0 if mevcut_db_dil == "Türkçe" else 1
        )
        
        if st.button("💾 Kaydet / Save Language"):
            try:
                # Veritabanını güncelle
                supabase.table("abone_listesi").update({"aktif_dil": yeni_dil}).eq("email", user_email).execute()
                # Oturumu güncelle
                st.session_state.lang = yeni_dil
                st.success(f"Dil {yeni_dil} olarak güncellendi! / Language updated to {yeni_dil}!")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Hata/Error: {e}")

    with col2:
        st.subheader("🔑 Güvenlik / Security")
        yeni_sifre = st.text_input("Yeni Şifre / New Password", type="password")
        
        if st.button("🔐 Şifreyi Değiştir / Update Password"):
            if len(yeni_sifre) >= 6:
                try:
                    supabase.auth.update_user({"password": yeni_sifre})
                    st.success("Şifreniz başarıyla güncellendi. / Password updated successfully.")
                except Exception as e:
                    st.error(f"Hata: {e}")
            else:
                st.error("Şifre en az 6 karakter olmalıdır. / Password must be at least 6 characters.")


# ==========================================
# 3. UYGULAMA AKIŞI
# ==========================================

if "user" not in st.session_state: st.session_state.user = None
if "is_guest" not in st.session_state: st.session_state.is_guest = False
if "password_cache" not in st.session_state: st.session_state.password_cache = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {"Genel Strateji": []}
if "current_session_name" not in st.session_state: st.session_state.current_session_name = "Genel Strateji"
if "model_mode" not in st.session_state: st.session_state.model_mode = "deep" # Varsayılan: Derin
# Navigasyon Durumu
if "page_nav" not in st.session_state: st.session_state.page_nav = "Ana Panel"

# --- ŞİFRE SIFIRLAMA YAKALAYICI (YENİ - EKRANI KİLİTLER) ---
# Linkten gelen recovery isteğini yakalar ve araya girer
if "type" in st.query_params and st.query_params["type"] == "recovery":
    st.title("🔐 SAVAŞ ODASI: ŞİFRE YENİLEME")
    st.info("Güvenlik protokolü devreye girdi. Lütfen yeni şifrenizi belirleyin.")
    
    with st.form("recovery_form"):
        new_pw = st.text_input("Yeni Şifre", type="password")
        confirm_pw = st.text_input("Yeni Şifre (Tekrar)", type="password")
        submit = st.form_submit_button("Şifreyi Güncelle")
        
        if submit:
            if new_pw == confirm_pw and len(new_pw) >= 6:
                try:
                    supabase.auth.update_user({"password": new_pw})
                    st.success("Şifreniz başarıyla güncellendi! Giriş ekranına yönlendiriliyorsunuz...")
                    time.sleep(2)
                    st.query_params.clear() # URL Parametrelerini temizle
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")
            else:
                st.warning("Şifreler uyuşmuyor veya 6 karakterden kısa.")
    st.stop() # Ana giriş ekranını gösterme

# --- GİRİŞ VE KAYIT EKRANI ---
if not st.session_state.user and not st.session_state.is_guest:
    st.title("🛡️ SAVAŞ ODASI HQ: ERİŞİM PANELİ")
    
    tab1, tab2, tab3 = st.tabs(["🔑 Giriş Yap", "👤 Personel Kaydı", "🔒 Şifremi Unuttum"])
    
    with tab1:
        e = st.text_input("E-posta", key="le")
        p = st.text_input("Şifre", type="password", key="lp")
        if st.button("Giriş Yap"):
            try:
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                if res.user:
                    # Kullanıcının dil tercihini veritabanından çek
                    try:
                        u_pref = supabase.table("abone_listesi").select("aktif_dil").eq("email", e).execute()
                        if u_pref.data and u_pref.data[0]["aktif_dil"]: 
                            st.session_state.lang = u_pref.data[0]["aktif_dil"]
                    except: pass
                    
                    st.session_state.user = res.user
                    st.session_state.password_cache = p
                    d = buluttan_yukle(res.user.id, p)
                    if d: st.session_state.chat_sessions = d; st.session_state.current_session_name = list(d.keys())[0]
                    st.rerun()
            except: st.error("Hatalı giriş.")

    with tab2:
        ne = st.text_input("Personel E-postası")
        np = st.text_input("Güvenlik Şifresi", type="password")
        # --- KRİTİK: DİL TERCİHİ KAYITTA ALINIYOR ---
        nlang = st.radio("Rapor ve Mail Dil Tercihi", ["Türkçe", "English"], horizontal=True)
        
        if st.button("Kaydı Tamamla"):
            try:
                res = supabase.auth.sign_up({"email": ne, "password": np, "options": {"email_redirect_to": SITE_URL}})
                if res.user:
                    # Dil tercihini veritabanına işle
                    supabase.table("abone_listesi").insert({
                        "email": ne, 
                        "aktif_dil": nlang,
                        "aktif": True
                    }).execute()
                    st.success("Kayıt başarılı! Lütfen giriş yapın.")
            except Exception as ex: st.error(f"Kayıt Hatası: {ex}")

    # --- ŞİFREMİ UNUTTUM SEKME İÇERİĞİ ---
    with tab3:
        st.subheader("Şifre Kurtarma")
        fe = st.text_input("Sistemde Kayıtlı E-posta")
        if st.button("Kurtarma Bağlantısı Gönder"):
            sifre_sifirla(fe)

    if st.button("🕵️ Misafir Olarak Devam Et"):
        st.session_state.is_guest = True; st.rerun()
    st.stop()

# --- SIDEBAR: ULTRA ESNEK ARŞİV SİSTEMİ & NAVİGASYON ---
user_id = st.session_state.user.id if st.session_state.user else "guest"
user_pass = st.session_state.password_cache

with st.sidebar:
    # DİL SEÇİMİ (ANLIK DEĞİŞTİRME)
    st.header("🌐 DİL / LANGUAGE")
    st.session_state.lang = st.radio("Sistem Dili", ["Türkçe", "English"], index=0 if st.session_state.lang=="Türkçe" else 1, label_visibility="collapsed")
    curr = L[st.session_state.lang]

    st.divider()
    
    # --- MENÜ NAVİGASYONU (YENİ EKLENDİ) ---
    if not st.session_state.is_guest:
        st.header("🧭 MENÜ")
        nav_options = [curr["panel"], curr["settings"]]
        selected_nav = st.radio("Git", nav_options, label_visibility="collapsed")
        
        # Seçimi session state'e işle
        if selected_nav == curr["settings"]:
            st.session_state.page_nav = "Ayarlar"
        else:
            st.session_state.page_nav = "Ana Panel"
        
        st.divider()

    # --- SADECE ANA PANELDEYKEN ARŞİV GÖSTER ---
    if st.session_state.page_nav == "Ana Panel":
        st.header(curr["archive"])
        search_q = st.text_input(curr["search"], "")
        
        # Tüm dosyaları oku ve tarihe (oluşturulma zamanına) göre sırala
        dosyalar = sorted(glob.glob("ARSIV/*.md"), key=os.path.getmtime, reverse=True)
        rep = "Veri Yok"
        secilen_icerik = "Seçili rapor yok."

        # --- GELİŞMİŞ TARİH AYIKLAMA (ÖN EK FARK ETMEKSİZİN) ---
        all_data = []
        for f in dosyalar:
            # Dosya adındaki her türlü YYYY-MM-DD formatını yakala
            match = re.search(r"(\d{4})-(\d{2})-(\d{2})", os.path.basename(f))
            if match:
                all_data.append({
                    "y": match.group(1),
                    "m": match.group(2),
                    "d": match.group(3),
                    "path": f,
                    "name": os.path.basename(f)
                })

        if not search_q and all_data:
            # 1. YIL SEÇİMİ
            years = sorted(list(set([d["y"] for d in all_data])), reverse=True)
            s_y = st.selectbox(curr["year"], years)
            
            # 2. AY SEÇİMİ (İSİMLİ)
            months = sorted(list(set([d["m"] for d in all_data if d["y"]==s_y])), reverse=True)
            m_names = [AYLAR.get(m, m) for m in months]
            s_m_name = st.selectbox(curr["month"], m_names)
            s_m_val = [k for k,v in AYLAR.items() if v==s_m_name][0]
            
            # 3. GÜN SEÇİMİ (İSİMLİ)
            days = sorted(list(set([d["d"] for d in all_data if d["y"]==s_y and d["m"]==s_m_val])), reverse=True)
            
            def gun_formatla(d_str):
                try:
                    dt = datetime.strptime(f"{s_y}-{s_m_val}-{d_str}", "%Y-%m-%d")
                    return f"{d_str} {GUNLER[dt.weekday()]}"
                except: return d_str
                
            d_opts = {gun_formatla(d): d for d in days}
            s_d_name = st.selectbox(curr["day"], list(d_opts.keys()))
            s_d_val = d_opts[s_d_name]
            
            # 4. RAPOR SEÇİMİ (SAAT VE ÖN EK FARK ETMEKSİZİN)
            final_files = [d for d in all_data if d["y"]==s_y and d["m"]==s_m_val and d["d"]==s_d_val]
            
            def okunakli_ad(fname):
                m_saat = re.search(r"_(\d{2})-(\d{2})", fname)
                label = "📄 " + fname.split("_")[0] # Analiz, Rapor veya WarRoom kısmını al
                if m_saat:
                    saat = int(m_saat.group(1))
                    periyot = "🌅 Sabah" if saat < 13 else "🌙 Akşam"
                    return f"{label} | {periyot} ({m_saat.group(1)}:{m_saat.group(2)})"
                return label + " | " + fname

            f_map = {okunakli_ad(d["name"]): d["path"] for d in final_files}
            s_r = st.selectbox(curr["records"], list(f_map.keys()))
            
            if s_r:
                with open(f_map[s_r], "r", encoding="utf-8") as f:
                    secilen_icerik = f.read()
                    rep = f"{s_d_name} {s_m_name} {s_y} | {s_r}"
        
        elif search_q:
            filt = [f for f in dosyalar if search_q.lower() in f.lower()]
            if filt:
                s_f = st.selectbox("Arama Sonuçları", filt, format_func=lambda x: os.path.basename(x))
                if s_f:
                    with open(s_f, "r", encoding="utf-8") as f:
                        secilen_icerik = f.read()
                        rep = os.path.basename(s_f)
            else:
                st.warning("Sonuç bulunamadı.")

        st.divider()
        st.header("💬 SOHBET YÖNETİMİ")
        if st.button(curr["new_chat"]):
            n = f"Op_{datetime.now().strftime('%H%M%S')}"
            st.session_state.chat_sessions[n] = []
            st.session_state.current_session_name = n
            st.rerun()
        
        sess_list = list(st.session_state.chat_sessions.keys())
        sel_sess = st.selectbox(curr["history"], sess_list, index=sess_list.index(st.session_state.current_session_name))
        if sel_sess != st.session_state.current_session_name: st.session_state.current_session_name = sel_sess; st.rerun()
        
        if st.button(curr["destroy"]):
            if len(st.session_state.chat_sessions) > 1: del st.session_state.chat_sessions[st.session_state.current_session_name]; st.session_state.current_session_name = list(st.session_state.chat_sessions.keys())[0]
            else: st.session_state.chat_sessions[st.session_state.current_session_name] = []
            st.rerun()
    
    if st.button(curr["logout"]): st.session_state.clear(); st.rerun()

# --- ANA EKRAN YÖNETİMİ ---

if st.session_state.page_nav == "Ayarlar" and not st.session_state.is_guest:
    # --- AYARLAR SAYFASINI GÖSTER ---
    ayarlar_sayfasi()

else:
    # --- ANA PANEL (RAPOR VE SOHBET) GÖSTER ---
    st.title(curr["title"])
    with st.spinner("Hafıza Güncelleniyor..."): hafizayi_guncelle()

    col_sol, col_sag = st.columns([55, 45], gap="medium")

    with col_sol:
        st.subheader(curr["report_view"])
        st.caption(rep)
        # --- KRİTİK OKUNURLUK DÜZELTMESİ (RENK ZORLAMA) ---
        c_clean = rapor_duzelt(secilen_icerik)
        components.html(c_clean, height=900, scrolling=True)

    with col_sag:
        st.markdown(curr["analysis_center"])
        m1, m2 = st.columns(2)
        with m1:
            if st.button(curr["fast_mode"], use_container_width=True):
                st.session_state.model_mode = "fast"; st.toast("Hızlı Moda Geçildi.")
        with m2:
            if st.button(curr["deep_mode"], use_container_width=True):
                st.session_state.model_mode = "deep"; st.toast("Derin Strateji Aktif.")
        
        # --- MODEL DEĞİŞKENİNİ GÜVENLİ OLUŞTURMA ---
        if st.session_state.model_mode == "fast":
            selected_model_id = "llama-3.1-8b-instant"
            current_mode_label = "⚡ SERİ MÜDAHALE"
        else:
            selected_model_id = "llama-3.3-70b-versatile"
            current_mode_label = "🔬 DERİN STRATEJİ"
        
        st.caption(f"Aktif Birim: **{current_mode_label}**")
        st.divider()
        
        chat_box = st.container(height=650)
        msgs = st.session_state.chat_sessions[st.session_state.current_session_name]
        
        with chat_box:
            for m in msgs:
                if m["role"] == "assistant" and "mode" in m:
                    st.markdown(f"<div class='model-tag'>{m['mode']}</div>", unsafe_allow_html=True)
                with st.chat_message(m["role"]): st.markdown(m["content"])

        if q := st.chat_input(curr["input_placeholder"]):
            msgs.append({"role": "user", "content": q})
            chat_box.chat_message("user").markdown(q)
            
            with chat_box.chat_message("assistant"):
                ph, full = st.empty(), ""
                with st.status(curr["status"]) as s:
                    arsiv_context = hafizadan_getir(q)
                    # HİBRİT ARAMA KULLANIMI
                    web_context = web_ara_kuresel(q)
                    s.update(label="Stratejik yanıt hazırlanıyor...", state="complete")
                
                # SİSTEM PROMPTUNA DİL AYARINI EKLE
                prompt_context = f"SYSTEM: {curr['system_prompt']}\n\nCONTEXT:\n[ARCHIVE]: {arsiv_context}\n[WEB]: {web_context}\n\nQUESTION: {q}"
                
                stream = ask_ai_with_rotation([{"role": "system", "content": curr['system_prompt']}, {"role": "user", "content": prompt_context}], selected_model_id)
                
                if stream:
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            full += chunk.choices[0].delta.content
                            ph.markdown(full + "▌")
                    ph.markdown(full)
                    msgs.append({"role": "assistant", "content": full, "mode": current_mode_label})
                    if not st.session_state.is_guest: buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass, sessiz=True)
                    st.rerun()
