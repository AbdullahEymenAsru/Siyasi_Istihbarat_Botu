import streamlit as st
import os
import glob
from groq import Groq

# 1. AYARLAR VE SAYFA DÜZENİ
st.set_page_config(page_title="Savaş Odası Dashboard", page_icon="🛡️", layout="wide")

# API Anahtarı
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Lütfen Streamlit Secrets ayarlarından GROQ_API_KEY ekleyin.")
    st.stop()

# 2. VERİ YÜKLEME (TÜM ARŞİVİ OKU)
arsiv_yolu = "ARSIV"
if not os.path.exists(arsiv_yolu):
    try: os.makedirs(arsiv_yolu)
    except: pass

# Dosyaları bul
try:
    dosyalar = glob.glob(f"{arsiv_yolu}/*.md")
    dosyalar.sort(key=os.path.getmtime, reverse=True) # En yeniden eskiye
    dosya_isimleri = [os.path.basename(f) for f in dosyalar]
except:
    dosya_isimleri = []

# --- KRİTİK BÖLÜM: TÜM GEÇMİŞİ BİRLEŞTİRME ---
# Yapay zekaya sadece bugünü değil, tüm arşivi veriyoruz.
tum_arsiv_metni = ""
if dosyalar:
    # Token limitini aşmamak için son 10 raporu birleştirelim (Yeterince büyük bir hafıza)
    for dosya in dosyalar[:10]: 
        with open(dosya, "r", encoding="utf-8") as f:
            tarih = os.path.basename(dosya).replace("WarRoom_", "").replace(".md", "")
            tum_arsiv_metni += f"\n\n=== RAPOR TARİHİ: {tarih} ===\n" + f.read()
else:
    tum_arsiv_metni = "Henüz arşivde rapor yok."

# 3. YAN MENÜ (GÖRSEL SEÇİM)
st.sidebar.title("🗄️ RAPOR GÖRÜNTÜLE")
if not dosya_isimleri:
    st.sidebar.warning("Arşiv boş.")
    secilen_dosya_icerigi = "<h3>Veri yok.</h3>"
else:
    secilen_dosya = st.sidebar.radio("Okumak istediğiniz rapor:", dosya_isimleri)
    with open(os.path.join(arsiv_yolu, secilen_dosya), "r", encoding="utf-8") as f:
        secilen_dosya_icerigi = f.read()

# 4. ANA EKRAN DÜZENİ
st.title("🛡️ KÜRESEL SAVAŞ ODASI")
st.markdown("---")

col1, col2 = st.columns([1, 1])

# SOL KOLON: Sadece Seçilen Raporu Gösterir (Okuma Amaçlı)
with col1:
    st.subheader(f"📄 Görüntülenen Rapor")
    st.markdown(secilen_dosya_icerigi, unsafe_allow_html=True)

# SAĞ KOLON: TÜM ARŞİVLE KONUŞAN CHAT (Analiz Amaçlı)
with col2:
    st.subheader("🧠 Baş Stratejist ile Konuş")
    st.info("Yapay Zeka, sol taraftaki rapor dahil **TÜM ARŞİV GEÇMİŞİNİ** bilir. Genel trendleri sorabilirsiniz.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Tüm istihbaratı analiz et..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                # SİSTEM MESAJINI GÜNCELLEDİK: "Tüm Arşiv" vurgusu
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""Sen Savaş Odası'nın Baş Stratejistisin.
                            
                            ELİNDEKİ VERİLER:
                            Aşağıda sana geçmişten bugüne kadar birikmiş TÜM İSTİHBARAT RAPORLARI verilmiştir.
                            
                            GÖREVİN:
                            Kullanıcının sorularını cevaplarken tek bir güne takılı kalma. 
                            Olaylar arasındaki bağlantıları kur, geçmiş raporlardaki trendleri analiz et ve büyük resmi gör.
                            
                            TÜM İSTİHBARAT ARŞİVİ:
                            {tum_arsiv_metni[:60000]}  # Karakter limiti (Context Window)
                            """
                        },
                        *st.session_state.messages
                    ],
                    stream=True,
                )

                # Temizleme Filtresi (Kodları gizler, metni gösterir)
                def stream_data_generator():
                    for chunk in stream:
                        content = chunk.choices[0].delta.content
                        if content:
                            yield content

                response = st.write_stream(stream_data_generator())
                st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                st.error(f"Hata: {e}")
