import streamlit as st
import os
import glob
import json
import base64
import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq
from duckduckgo_search import DDGS
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime
import streamlit.components.v1 as components # HTML Görünümü için
import re # Temizlik için

# ==========================================

# 1. AYARLAR & KURULUM

# ==========================================

st.set_page_config(page_title="Savaş Odası (GUEST & E2EE)", page_icon="🛡️", layout="wide")

# CSS ile Askeri Tema

st.markdown("""
<style>
.stChatMessage { border-radius: 10px; padding: 10px; }
.stButton button { width: 100%; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# -- BURAYA KENDİ SİTE ADRESİNİ YAZ ---

SITE_URL = "[https://siyasi-istihbarat-botu.streamlit.app](https://siyasi-istihbarat-botu.streamlit.app/)"

# ---------------------------------------------------

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

# -- YENİ MANUEL EMBEDDING SINIFI ---

class YerelEmbedder:
def **init**(self):
self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
def **call**(self, input):
return self.model.encode(input).tolist()
def name(self):
return "YerelEmbedder"

# -- ŞİFRELEME FONKSİYONLARI ---

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

# -- SABİT KOORDİNATLAR ---

KOORDINATLAR = {
"Türkiye": [39.9334, 32.8597], "Turkey": [39.9334, 32.8597], "Ankara": [39.9334, 32.8597],
"ABD": [38.9072, -77.0369], "USA": [38.9072, -77.0369], "Washington": [38.9072, -77.0369],
"Rusya": [55.7558, 37.6173], "Russia": [55.7558, 37.6173], "Moskova": [55.7558, 37.6173],
"Ukrayna": [50.4501, 30.5234], "Ukraine": [50.4501, 30.5234], "Kiev": [50.4501, 30.5234],
"Çin": [39.9042, 116.4074], "China": [39.9042, 116.4074], "Pekin": [39.9042, 116.4074],
"İsrail": [31.7683, 35.2137], "Israel": [31.7683, 35.2137], "Tel Aviv": [32.0853, 34.7818],
"Filistin": [31.9522, 35.2332], "Gazze": [31.5017, 34.4668], "Gaza": [31.5017, 34.4668],
"İran": [35.6892, 51.3890], "Iran": [35.6892, 51.3890], "Tahran": [35.6892, 51.3890],
"Suriye": [33.5138, 36.2765], "Syria": [33.5138, 36.2765],
"Azerbaycan": [40.4093, 49.8671], "Azerbaijan": [40.4093, 49.8671],
"Ermenistan": [40.1792, 44.4991], "Armenia": [40.1792, 44.4991]
}

# -- AUTH VE DATABASE FONKSİYONLARI ---

def giris_yap(email, password):
try:
res = supabase.auth.sign_in_with_password({"email": email, "password": password})
return res.user
except Exception as e:
st.error(f"Giriş başarısız: {e}")
return None

def kayit_ol(email, password):
try:
res = supabase.auth.sign_up({
"email": email,
"password": password,
"options": {"email_redirect_to": SITE_URL}
})
if res.user:
try:
supabase.table("abone_listesi").insert({"email": email}).execute()
except: pass
st.success("Kayıt başarılı! Mail listesine eklendiniz. E-postanızı onaylayın.")
return res.user
except Exception as e:
st.error(f"Kayıt hatası: {e}")
return None

def sifre_sifirla(email):
try:
supabase.auth.reset_password_email(email, options={"redirect_to": SITE_URL})
st.success(f"📧 Sıfırlama bağlantısı {email} adresine gönderildi.")
st.warning("⚠️ DİKKAT: Şifrenizi değiştirdiğinizde, eski sohbet geçmişiniz OKUNAMAZ hale gelecektir.")
except Exception as e:
st.error(f"Mail gönderme hatası: {e}")

def buluttan_yukle(user_id, password):
try:
response = supabase.table("chat_logs").select("messages").eq("user_id", user_id).execute()
if response.data:
raw_data = response.data[0]["messages"]
if isinstance(raw_data, dict) and "encrypted_data" in raw_data:
decrypted = sifreyi_coz(raw_data["encrypted_data"], password)
return decrypted
except: pass
return None

def buluta_kaydet(user_id, data_to_save, password):
try:
sifreli_veri = sifrele(data_to_save, password)
data = {"user_id": user_id, "messages": {"encrypted_data": sifreli_veri}}
supabase.table("chat_logs").upsert(data, on_conflict="user_id").execute()
except Exception as e: print(f"Kayıt hatası: {e}")

# -- AI VE HARİTA FONKSİYONLARI ---

@st.cache_resource
def get_chroma_client():
return chromadb.PersistentClient(path="VEKTOR_DB")

@st.cache_resource
def get_embedding_function():
return YerelEmbedder()

def hafizayi_guncelle():
chroma = get_chroma_client()
ef = get_embedding_function()

```
col = chroma.get_or_create_collection(name="savas_odasi", embedding_function=ef)
dosyalar = glob.glob("ARSIV/*.md")
yeni = False
for d in dosyalar:
    adi = os.path.basename(d)
    if not col.get(ids=[adi])['ids']:
        with open(d,"r",encoding="utf-8") as f: col.add(documents=[f.read()], metadatas=[{"source":adi}], ids=[adi])
        yeni = True
return yeni

```

def hafizadan_getir(soru):
try:
ef = get_embedding_function()
col = get_chroma_client().get_collection(name="savas_odasi", embedding_function=ef)
res = col.query(query_texts=[soru], n_results=3)
return "\n".join(res['documents'][0]) if res['documents'] else "Arşivde bilgi yok."
except: return "Hafıza hatası."

def web_ara(soru):
try:
res = DDGS().text(keywords=soru, region='tr-tr', max_results=3)
return "\n".join([f"- {r['title']}: {r['body']}" for r in res]) if res else "İnternette sonuç yok."
except: return "Bağlantı hatası."

def harita_analiz(metin):
prompt = f"JSON formatında coğrafi ilişkiler çıkar: {{'data': [{{'kaynak_ulke':'Rusya','hedef_ulke':'Ukrayna','olay':'Saldırı','risk_puani':80}}]}} Metin: {metin[:3000]}"
try:
res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], response_format={"type":"json_object"})
return json.loads(res.choices[0].message.content)
except: return {"data":[]}

# ==========================================

# UYGULAMA AKIŞI (MAIN)

# ==========================================

# 1. OTURUM DEĞİŞKENLERİ

if "user" not in st.session_state: st.session_state.user = None
if "is_guest" not in st.session_state: st.session_state.is_guest = False
if "password_cache" not in st.session_state: st.session_state.password_cache = None
if "harita_data" not in st.session_state: st.session_state.harita_data = None

# -- ÇOKLU OTURUM BAŞLATMA ---

if "chat_sessions" not in st.session_state:
st.session_state.chat_sessions = {
"Genel Strateji": [{"role": "assistant", "content": "Komutanım, Savaş Odası hazır. Emrinizi bekliyorum."}]
}
if "current_session_name" not in st.session_state:
st.session_state.current_session_name = "Genel Strateji"

# GİRİŞ EKRANI

if not st.session_state.user and not st.session_state.is_guest:
st.title("🔐 SAVAŞ ODASI: GİRİŞ EKRANI")
st.markdown("Verileriniz uçtan uca şifrelidir (E2EE). Misafir girişlerinde veri kaydedilmez.")
# URL'den gelen Şifre Sıfırlama Token Kontrolü
query_params = st.query_params
if "type" in query_params and query_params["type"] == "recovery":
    st.info("🔄 Şifre Sıfırlama Modu")
    new_pass_reset = st.text_input("Yeni Şifrenizi Belirleyin (Sıfırlama)", type="password")
    if st.button("Şifreyi Güncelle"):
        try:
            supabase.auth.update_user({"password": new_pass_reset})
            st.success("Şifre güncellendi! Lütfen yeni şifrenizle soldan giriş yapın.")
        except Exception as e: st.error(f"Hata: {e}")

col1, col2 = st.columns(2)

# --- ÜYE GİRİŞİ ve EKSTRA İŞLEMLER ---
with col1:
    st.subheader("🔑 Üye Girişi")
    email = st.text_input("E-posta")
    password = st.text_input("Şifre", type="password")

    if st.button("Giriş Yap"):
        user = giris_yap(email, password)
        if user:
            st.session_state.user = user
            st.session_state.password_cache = password

            # --- VERİ YÜKLEME VE DÖNÜŞTÜRME (MIGRATION) ---
            yuklenen_veri = buluttan_yukle(user.id, password)

            # Eski veritabanı formatı (Liste) ise Sözlüğe çevir
            if isinstance(yuklenen_veri, list):
                st.session_state.chat_sessions = {"Genel Strateji": yuklenen_veri if yuklenen_veri else []}
            # Yeni format (Sözlük) ise direkt al
            elif isinstance(yuklenen_veri, dict):
                st.session_state.chat_sessions = yuklenen_veri
            else:
                st.session_state.chat_sessions = {"Genel Strateji": []}

            st.rerun()

    # --- GERİ GETİRİLEN ÖZELLİKLER ---
    st.markdown("---")

    # Şifremi Unuttum
    with st.expander("❓ Şifremi Unuttum"):
        st.info("E-posta adresinizi girin, sıfırlama bağlantısı gönderelim.")
        reset_mail = st.text_input("Kayıtlı E-posta Adresi")
        if st.button("Sıfırlama Linki Gönder"):
            if reset_mail:
                sifre_sifirla(reset_mail)
            else:
                st.warning("Lütfen e-posta adresini girin.")

    # Yeni Hesap Oluştur
    with st.expander("📝 Yeni Hesap Oluştur"):
        new_email = st.text_input("Yeni E-posta")
        new_pass = st.text_input("Yeni Şifre", type="password")
        if st.button("Kayıt Ol"):
            if new_email and new_pass:
                kayit_ol(new_email, new_pass)
            else:
                st.warning("Lütfen bilgileri eksiksiz girin.")

with col2:
    st.subheader("🕵️ Misafir Girişi")
    st.info("Kayıt tutulmaz. Sayfa yenilenince tüm veriler silinir.")
    if st.button("Misafir Olarak Devam Et >>"):
        st.session_state.is_guest = True
        st.session_state.chat_sessions = {"Misafir Oturumu": []}
        st.session_state.current_session_name = "Misafir Oturumu"
        st.rerun()
st.stop()
# -- GİRİŞ YAPILDIKTAN SONRAKİ SIDEBAR ---

if st.session_state.is_guest:
st.sidebar.warning("🕵️ MOD: MİSAFİR")
user_id = "guest"
user_pass = None
else:
st.sidebar.success(f"Ajan: {st.session_state.user.email}")
[st.sidebar.info](http://st.sidebar.info/)("🔒 E2EE Şifreleme Aktif")
user_id = st.session_state.user.id
user_pass = st.session_state.password_cache

# -- YENİ SIDEBAR: OTURUM YÖNETİMİ ---

st.sidebar.markdown("---")
st.sidebar.header("🗄️ Operasyon Kayıtları")

# Yeni Sohbet Ekleme

if st.sidebar.button("➕ YENİ SOHBET BAŞLAT", type="primary"):
new_name = f"Operasyon_{datetime.now().strftime('%H%M%S')}"
st.session_state.chat_sessions[new_name] = []
st.session_state.current_session_name = new_name
st.rerun()

# Sohbet Seçimi

session_names = list(st.session_state.chat_sessions.keys())
try:
secili_index = session_names.index(st.session_state.current_session_name)
except: secili_index = 0

selected_session = st.sidebar.selectbox(
"Geçmiş Kayıtlar:",
session_names,
index=secili_index
)

if selected_session != st.session_state.current_session_name:
st.session_state.current_session_name = selected_session
st.rerun()

# Sohbeti Silme

if st.sidebar.button("🗑️ Bu Kaydı İmha Et"):
if len(session_names) > 1:
del st.session_state.chat_sessions[st.session_state.current_session_name]
st.session_state.current_session_name = list(st.session_state.chat_sessions.keys())[0]
# Veritabanını güncelle
if not st.session_state.is_guest:
buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)
st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("Çıkış Yap"):
if not st.session_state.is_guest: supabase.auth.sign_out()
st.session_state.user = None
st.session_state.is_guest = False
st.session_state.chat_sessions = {}
st.rerun()

# Rapor Seçimi

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

st.title("☁️ KÜRESEL SAVAŞ ODASI")
with st.spinner("Sistem Hazırlanıyor..."): hafizayi_guncelle()

t1, t2, t3 = st.tabs(["📄 RAPOR", "🗺️ HARİTA", "🧠 HİBRİT CHAT"])

with t1:
# HTML Temizliği ve Render
if "`" in secilen_icerik:         secilen_icerik = re.sub(r"`html", "", secilen_icerik)
secilen_icerik = re.sub(r"```", "", secilen_icerik)

```
st.info(f"📂 Görüntülenen Rapor: {sec}")
components.html(secilen_icerik, height=800, scrolling=True)

```

with t2:
if st.button("Haritayı Analiz Et ve Çiz"):
with st.spinner("Harita çiziliyor..."):
st.session_state.harita_data = harita_analiz(secilen_icerik)

```
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

```

# -- YENİ GELİŞMİŞ CHAT SEKMESİ ---

with t3:
st.subheader(f"💬 Kanal: {st.session_state.current_session_name}")

```
# Mevcut oturumun mesajlarını al
current_messages = st.session_state.chat_sessions[st.session_state.current_session_name]

for m in current_messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if q := st.chat_input("Emriniz?"):
    # Kullanıcı mesajını ekle
    current_messages.append({"role":"user","content":q})
    with st.chat_message("user"): st.markdown(q)

    # RAG ve Web Araması
    with st.status("İstihbarat toplanıyor...") as s:
        arsiv = hafizadan_getir(q)
        web = web_ara(q)
        s.update(label="Veriler toplandı, analiz ediliyor...", state="complete")

    # Asistan Yanıtı (Fallback Mekanizması)
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # --- TOKEN YÖNETİMİ (Kayan Pencere) ---
        # Sadece son 10 mesajı API'ye gönder (Context limitini korur)
        recent_history = current_messages[-10:]

        # Bağlam bilgisini en son kullanıcı mesajına gizlice ekliyoruz
        enriched_last_message = {
            "role": "user",
            "content": f"SORU: {q}\\n\\n[SİSTEM BİLGİSİ - ARŞİV]:\\n{arsiv}\\n\\n[SİSTEM BİLGİSİ - WEB]:\\n{web}"
        }

        # API'ye gidecek liste: Sistem + Geçmiş + Zenginleştirilmiş Son Mesaj
        api_messages = [
            {"role": "system", "content": "Sen Savaş Odası stratejistisin. Arşiv ve Web verilerini kullanarak derinlikli analiz yap."}
        ] + recent_history[:-1] + [enriched_last_message]

        try:
            # PLAN A: 70B Modeli (Zeki ve Derin)
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=api_messages,
                stream=True,
                temperature=0.6,
                max_tokens=1024
            )
        except Exception as e:
            # PLAN B: 8B Modeli (Yedek Hat - Hızlı ve Kotası Geniş)
            st.warning(f"⚠️ Ana hat meşgul, yedek kanaldan (8B) bağlanılıyor... ({str(e)[:40]}...)")
            try:
                stream = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=api_messages,
                    stream=True,
                    temperature=0.6,
                    max_tokens=1024
                )
            except:
                st.error("❌ Tüm hatlar kesildi.")
                stream = []

        # Akışı Yazdır
        if stream:
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)

            # Yanıtı Kaydet
            current_messages.append({"role":"assistant","content":full_response})

            # Veritabanına Kaydet (Tüm Oturumları)
            if not st.session_state.is_guest:
                buluta_kaydet(user_id, st.session_state.chat_sessions, user_pass)

```
