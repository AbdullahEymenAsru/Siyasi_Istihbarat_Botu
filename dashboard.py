import streamlit as st
import os
import glob
from groq import Groq

# 1. AYARLAR VE SAYFA DÜZENİ
st.set_page_config(page_title="Savaş Odası Dashboard", page_icon="🛡️", layout="wide")

# API Anahtarı (Streamlit Secrets'tan alacak)
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Lütfen Streamlit Secrets ayarlarından GROQ_API_KEY ekleyin.")
    st.stop()

# 2. YAN MENÜ: RAPOR SEÇİMİ
st.sidebar.title("🗄️ İSTİHBARAT ARŞİVİ")
arsiv_yolu = "ARSIV"

# Arşiv klasörü yoksa oluştur (Hata vermemesi için)
if not os.path.exists(arsiv_yolu):
    try:
        os.makedirs(arsiv_yolu)
    except:
        pass # Streamlit Cloud bazen yazma izni vermez, sorun değil

# Dosyaları bul ve sırala (En yeniden eskiye)
try:
    dosyalar = glob.glob(f"{arsiv_yolu}/*.md")
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    dosya_isimleri = [os.path.basename(f) for f in dosyalar]
except:
    dosya_isimleri = []

if not dosya_isimleri:
    st.warning("Henüz hiç rapor oluşturulmamış veya arşiv boş.")
    # Demo amaçlı boş bir içerik gösterelim ki kod patlamasın
    secilen_dosya = "Demo"
    rapor_icerigi = "<h3>Henüz rapor yok.</h3>"
else:
    secilen_dosya = st.sidebar.radio("Rapor Tarihi Seçin:", dosya_isimleri)
    # Seçilen dosyanın içeriğini oku
    secilen_yol = os.path.join(arsiv_yolu, secilen_dosya)
    with open(secilen_yol, "r", encoding="utf-8") as f:
        rapor_icerigi = f.read()

# 3. ANA EKRAN: RAPOR GÖRÜNTÜLEME
st.title("🛡️ KÜRESEL SAVAŞ ODASI")
st.markdown("---")

# İki sütunlu yapı: Sol (Rapor), Sağ (Chat)
col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader(f"📄 Rapor: {secilen_dosya}")
    st.markdown(rapor_icerigi, unsafe_allow_html=True)

# 4. CHAT ARAYÜZÜ (RAG - Retrieval Augmented Generation)
with col2:
    st.subheader("💬 İstihbarat Subayı ile Konuş")
    st.info("Bu rapor hakkında detaylı soru sorabilirsiniz. Örn: 'Bu durum Türkiye'yi nasıl etkiler?'")

    # Sohbet geçmişini tut
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Geçmiş mesajları göster
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Kullanıcıdan soru al
    if prompt := st.chat_input("Sorunuzu yazın..."):
        # Kullanıcı mesajını ekle
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI Yanıtı Hazırla
        with st.chat_message("assistant"):
            try:
                # 1. Groq'a İsteği Gönder (Stream Modunda)
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"Sen Savaş Odası'nın kıdemli analistisin. Kullanıcı sana şu rapor hakkında sorular soracak:\n\nRAPOR İÇERİĞİ:\n{rapor_icerigi}\n\nKullanıcının sorusuna bu rapora dayanarak stratejik, net ve Türkçe cevaplar ver."
                        },
                        *st.session_state.messages
                    ],
                    stream=True,
                )

                # 2. ÖZEL SÜZGEÇ FONKSİYONU (SORUNU ÇÖZEN KISIM) 🛠️
                # Gelen ham JSON verisini ayıklar ve sadece metni verir
                def stream_data_generator():
                    for chunk in stream:
                        content = chunk.choices[0].delta.content
                        if content:
                            yield content

                # 3. Ekrana Yazdır (Streamlit'e temizlenmiş veriyi veriyoruz)
                response = st.write_stream(stream_data_generator())
                
                # 4. Cevabı hafızaya kaydet
                st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                st.error(f"Bir hata oluştu: {e}")
