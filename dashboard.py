import streamlit as st
import os
import glob
import json
import chromadb
from chromadb.utils import embedding_functions
from groq import Groq

# 1. AYARLAR
st.set_page_config(page_title="Savaş Odası RAG", page_icon="🧠", layout="wide")

# API Anahtarı
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Lütfen Streamlit Secrets ayarlarından GROQ_API_KEY ekleyin.")
    st.stop()

# Klasör Kontrolleri
if not os.path.exists("ARSIV"): os.makedirs("ARSIV")
if not os.path.exists("LOGS"): os.makedirs("LOGS")
if not os.path.exists("VEKTOR_DB"): os.makedirs("VEKTOR_DB")

# --- VEKTÖR VERİTABANI (BEYİN) KURULUMU ---
@st.cache_resource
def get_chroma_client():
    """Veritabanını başlatır ve hafızada tutar"""
    return chromadb.PersistentClient(path="VEKTOR_DB")

def hafizayi_guncelle():
    """
    Arşivdeki yeni raporları okur, parçalar ve Vektör Veritabanına kaydeder.
    Bu işlem, yapay zekanın 'Öğrenmesini' sağlar.
    """
    chroma_client = get_chroma_client()
    
    # Embedding Modeli (Metni Sayıya Çeviren Yapı - Ücretsiz)
    # Bu model arka planda indirilecektir, ilk çalışmada 10-20sn sürebilir.
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
    # Koleksiyonu (Tabloyu) Getir veya Oluştur
    collection = chroma_client.get_or_create_collection(name="savas_odasi_hafiza", embedding_function=sentence_transformer_ef)
    
    dosyalar = glob.glob("ARSIV/*.md")
    yeni_veri_eklendi = False
    
    for dosya_yolu in dosyalar:
        dosya_adi = os.path.basename(dosya_yolu)
        
        # Dosya zaten veritabanında var mı? (ID = Dosya Adı)
        mevcut = collection.get(ids=[dosya_adi])
        if len(mevcut['ids']) > 0:
            continue # Zaten öğrenilmiş, geç.
            
        # Dosyayı Oku
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            icerik = f.read()
            
        # Veritabanına Ekle (ID, Metin, Metadata)
        # ChromaDB metni otomatik olarak vektöre çevirir
        collection.add(
            documents=[icerik],
            metadatas=[{"source": dosya_adi}],
            ids=[dosya_adi]
        )
        yeni_veri_eklendi = True
        
    return yeni_veri_eklendi

def hafizadan_bilgi_getir(soru):
    """
    Kullanıcının sorusuyla en alakalı 3 rapor parçasını getirir.
    RAG (Retrieval Augmented Generation) tam olarak budur.
    """
    chroma_client = get_chroma_client()
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_collection(name="savas_odasi_hafiza", embedding_function=sentence_transformer_ef)
    
    # Soruyu veritabanında arat
    results = collection.query(
        query_texts=[soru],
        n_results=3 # En alakalı 3 parça
    )
    
    # Gelen parçaları birleştir
    baglam = ""
    if results['documents']:
        for doc in results['documents'][0]:
            baglam += doc + "\n\n---\n\n"
    
    return baglam if baglam else "Arşivde ilgili bilgi bulunamadı."

# Sayfa Yüklenince Hafızayı Tazele
with st.spinner('Beyin güncelleniyor... Yeni raporlar taranıyor...'):
    if hafizayi_guncelle():
        st.toast("🧠 Yeni bilgiler hafızaya işlendi!", icon="✅")

# --- STANDART FONKSİYONLAR (LOGLAMA vs.) ---
def gecmisi_yukle(kullanici_adi):
    dosya_yolu = f"LOGS/{kullanici_adi}.json"
    if os.path.exists(dosya_yolu):
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def gecmisi_kaydet(kullanici_adi, mesajlar):
    dosya_yolu = f"LOGS/{kullanici_adi}.json"
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        json.dump(mesajlar, f, ensure_ascii=False, indent=4)

# 2. YAN MENÜ: GİRİŞ
st.sidebar.title("🔐 GÜVENLİK GİRİŞİ")
ajan_kodu = st.sidebar.text_input("Ajan Kod Adı / Parola:", value="", placeholder="Örn: Eymen007", help="Sohbet geçmişi bu isme kaydedilir.")

if st.sidebar.button("🧹 Sohbeti Sıfırla"):
    if ajan_kodu:
        st.session_state.messages = []
        gecmisi_kaydet(ajan_kodu, [])
        st.rerun()
    else:
        st.sidebar.error("Önce giriş yapmalısınız!")

st.sidebar.markdown("---")
st.sidebar.title("🗄️ RAPOR GÖRÜNTÜLE")

# Rapor Seçimi
try:
    dosyalar = glob.glob("ARSIV/*.md")
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    dosya_isimleri = [os.path.basename(f) for f in dosyalar]
except: dosya_isimleri = []

if not dosya_isimleri:
    st.sidebar.warning("Arşiv boş.")
    secilen_dosya_icerigi = "<h3>Veri yok.</h3>"
else:
    secilen_dosya = st.sidebar.radio("Okumak istediğiniz rapor:", dosya_isimleri)
    with open(os.path.join("ARSIV", secilen_dosya), "r", encoding="utf-8") as f:
        secilen_dosya_icerigi = f.read()

# 3. ANA EKRAN
st.title("🧠 SAVAŞ ODASI (RAG DESTELİ)")

if not ajan_kodu:
    st.warning("⚠️ LÜTFEN GİRİŞ YAPINIZ")
    st.info("Sol menüden kod adınızı girerek sisteme bağlanın.")
    st.stop()

# Oturum Yönetimi
if "messages" not in st.session_state:
    st.session_state.messages = gecmisi_yukle(ajan_kodu)
if "last_user" not in st.session_state:
    st.session_state.last_user = ajan_kodu
elif st.session_state.last_user != ajan_kodu:
    st.session_state.messages = gecmisi_yukle(ajan_kodu)
    st.session_state.last_user = ajan_kodu

st.success(f"✅ Oturum Açıldı: **{ajan_kodu}** | 🧠 Vektör Hafıza Aktif")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader(f"📄 Seçilen Rapor")
    st.markdown(secilen_dosya_icerigi, unsafe_allow_html=True)

with col2:
    st.subheader("🤖 Yapay Zeka (Tüm Arşiv Uzmanı)")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Arşivden ne öğrenmek istersiniz?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        gecmisi_kaydet(ajan_kodu, st.session_state.messages)

        # --- KRİTİK NOKTA: RAG MEKANİZMASI ---
        # 1. Önce veritabanından alakalı bilgiyi çek
        alakali_bilgi = hafizadan_bilgi_getir(prompt)
        
        # 2. Sonra LLM'e bu bilgiyi ver
        with st.chat_message("assistant"):
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""Sen Savaş Odası'nın Baş Stratejistisin.
                            
                            KULLANICI SORUSU: {prompt}
                            
                            KÜTÜPHANEDEN BULUNAN İLGİLİ İSTİHBARAT BELGELERİ:
                            {alakali_bilgi}
                            
                            GÖREVİN:
                            Yukarıdaki istihbarat belgelerini kullanarak kullanıcının sorusunu cevapla.
                            Eğer belgelerde bilgi yoksa "Arşivlerimde bu konuda bilgi bulamadım" de.
                            Cevabın net, stratejik ve Türkçe olsun.
                            """
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
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                gecmisi_kaydet(ajan_kodu, st.session_state.messages)

            except Exception as e:
                st.error(f"Hata: {e}")
