import streamlit as st
import os
import glob
import json
from groq import Groq

# 1. AYARLAR
st.set_page_config(page_title="Savaş Odası Dashboard", page_icon="🛡️", layout="wide")

# API Anahtarı
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Lütfen Streamlit Secrets ayarlarından GROQ_API_KEY ekleyin.")
    st.stop()

# Klasör Kontrolleri
if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
if not os.path.exists("LOGS"): os.makedirs("LOGS") # Sohbet kayıtları burada tutulacak

# --- FONKSİYONLAR ---
def gecmisi_yukle(kullanici_adi):
    """Kullanıcıya özel sohbet geçmişini dosyadan yükler"""
    dosya_yolu = f"LOGS/{kullanici_adi}.json"
    if os.path.exists(dosya_yolu):
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def gecmisi_kaydet(kullanici_adi, mesajlar):
    """Sohbet geçmişini dosyaya kaydeder"""
    dosya_yolu = f"LOGS/{kullanici_adi}.json"
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        json.dump(mesajlar, f, ensure_ascii=False, indent=4)

# 2. YAN MENÜ: KİMLİK DOĞRULAMA VE DOSYA SEÇİMİ
st.sidebar.title("🔐 GÜVENLİK GİRİŞİ")

# Kullanıcı Kimliği (Buraya ne yazarsan sohbet o isme kaydedilir)
ajan_kodu = st.sidebar.text_input("Ajan Kod Adı / Parola:", value="Misafir", help="Sohbet geçmişinizin saklanması için benzersiz bir ad girin.")

# Sohbeti Temizle Butonu
if st.sidebar.button("🧹 Sohbeti Sıfırla"):
    st.session_state.messages = []
    gecmisi_kaydet(ajan_kodu, [])
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("🗄️ İSTİHBARAT ARŞİVİ")

# Raporları Listele
try:
    dosyalar = glob.glob("ARSIV/*.md")
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    dosya_isimleri = [os.path.basename(f) for f in dosyalar]
except: dosya_isimleri = []

# Tüm Arşiv Metni (AI Hafızası)
tum_arsiv_metni = ""
if dosyalar:
    for dosya in dosyalar[:10]: 
        with open(dosya, "r", encoding="utf-8") as f:
            tarih = os.path.basename(dosya).replace("WarRoom_", "").replace(".md", "")
            tum_arsiv_metni += f"\n\n=== RAPOR TARİHİ: {tarih} ===\n" + f.read()
else:
    tum_arsiv_metni = "Henüz arşivde rapor yok."

# Dosya Seçimi
if not dosya_isimleri:
    st.sidebar.warning("Arşiv boş.")
    secilen_dosya_icerigi = "<h3>Veri yok.</h3>"
else:
    secilen_dosya = st.sidebar.radio("Okumak istediğiniz rapor:", dosya_isimleri)
    with open(os.path.join("ARSIV", secilen_dosya), "r", encoding="utf-8") as f:
        secilen_dosya_icerigi = f.read()

# 3. OTURUM YÖNETİMİ (Session State)
# Sayfa yenilendiğinde önce dosyadan geçmişi çekmeye çalış
if "messages" not in st.session_state:
    st.session_state.messages = gecmisi_yukle(ajan_kodu)

# Eğer kullanıcı adını değiştirirse geçmişi güncelle
if "last_user" not in st.session_state:
    st.session_state.last_user = ajan_kodu
elif st.session_state.last_user != ajan_kodu:
    st.session_state.messages = gecmisi_yukle(ajan_kodu)
    st.session_state.last_user = ajan_kodu

# 4. ANA EKRAN
st.title("🛡️ KÜRESEL SAVAŞ ODASI")
st.markdown(f"**Aktif Oturum:** `{ajan_kodu}` | *Geçmiş otomatik kaydediliyor...*")
st.markdown("---")

col1, col2 = st.columns([1, 1])

# SOL KOLON (Rapor)
with col1:
    st.subheader(f"📄 Görüntülenen Rapor")
    st.markdown(secilen_dosya_icerigi, unsafe_allow_html=True)

# SAĞ KOLON (Chat)
with col2:
    st.subheader("🧠 Baş Stratejist ile Konuş")
    
    # Mesajları Ekrana Bas
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Yeni Soru Al
    if prompt := st.chat_input("Analiz emriniz nedir komutanım?"):
        # 1. Kullanıcı Mesajını Ekle ve Kaydet
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        gecmisi_kaydet(ajan_kodu, st.session_state.messages) # Anlık Kayıt

        # 2. AI Cevabı
        with st.chat_message("assistant"):
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""Sen Savaş Odası'nın Baş Stratejistisin.
                            GÖREVİN: Kullanıcının sorularını, aşağıdaki TÜM ARŞİV verisine dayanarak cevapla.
                            TÜM İSTİHBARAT ARŞİVİ: {tum_arsiv_metni[:60000]}"""
                        },
                        *st.session_state.messages
                    ],
                    stream=True,
                )

                def stream_data_generator():
                    for chunk in stream:
                        content = chunk.choices[0].delta.content
                        if content: yield content

                response = st.write_stream(stream_data_generator())
                
                # 3. AI Cevabını Ekle ve Kaydet
                st.session_state.messages.append({"role": "assistant", "content": response})
                gecmisi_kaydet(ajan_kodu, st.session_state.messages) # Anlık Kayıt

            except Exception as e:
                st.error(f"Hata: {e}")
