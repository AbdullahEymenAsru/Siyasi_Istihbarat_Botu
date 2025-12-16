import streamlit as st
import os
import glob
import json
import chromadb
from chromadb.utils import embedding_functions
from groq import Groq
from duckduckgo_search import DDGS  # <--- İNTERNET ARAMA MODÜLÜ

# 1. AYARLAR
st.set_page_config(page_title="Savaş Odası v3.0", page_icon="🌐", layout="wide")

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

# --- WEB ARAMA ARACI (TOOL) ---
def internette_ara(sorgu):
    """
    DuckDuckGo üzerinden canlı internet araması yapar.
    Anlık borsa, son dakika haberleri vb. için kullanılır.
    """
    try:
        # Türkiye bölgesinde (tr-tr), son 5 sonucu getir
        results = DDGS().text(keywords=sorgu, region='tr-tr', safesearch='off', max_results=5)
        if results:
            ozet = ""
            for r in results:
                ozet += f"- {r['title']}: {r['body']} (Kaynak: {r['href']})\n"
            return ozet
    except Exception as e:
        return f"İnternet bağlantı hatası: {e}"
    return "İnternette güncel bilgi bulunamadı."

# --- VEKTÖR VERİTABANI (BEYİN) ---
@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path="VEKTOR_DB")

def hafizayi_guncelle():
    chroma_client = get_chroma_client()
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_or_create_collection(name="savas_odasi_hafiza", embedding_function=sentence_transformer_ef)
    
    dosyalar = glob.glob("ARSIV/*.md")
    yeni_veri_eklendi = False
    
    for dosya_yolu in dosyalar:
        dosya_adi = os.path.basename(dosya_yolu)
        mevcut = collection.get(ids=[dosya_adi])
        if len(mevcut['ids']) > 0: continue 
            
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            icerik = f.read()
            
        collection.add(
            documents=[icerik],
            metadatas=[{"source": dosya_adi}],
            ids=[dosya_adi]
        )
        yeni_veri_eklendi = True
    return yeni_veri_eklendi

def hafizadan_bilgi_getir(soru):
    """RAG: Arşivden bilgi çeker"""
    chroma_client = get_chroma_client()
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = chroma_client.get_collection(name="savas_odasi_hafiza", embedding_function=sentence_transformer_ef)
    
    results = collection.query(query_texts=[soru], n_results=3)
    baglam = ""
    if results['documents']:
        for doc in results['documents'][0]:
            baglam += doc + "\n\n---\n\n"
    return baglam if baglam else "Arşivde ilgili bilgi bulunamadı."

# Sayfa Yüklenince Hafızayı Tazele
with st.spinner('Sistem başlatılıyor... Arşiv ve İnternet modülleri yükleniyor...'):
    if hafizayi_guncelle():
        st.toast("🧠 Arşiv güncellendi!", icon="✅")

# --- LOGLAMA (Sohbet Geçmişi) ---
def gecmisi_yukle(kullanici_adi):
    dosya_yolu = f"LOGS/{kullanici_adi}.json"
    if os.path.exists(dosya_yolu):
        with open(dosya_yolu, "r", encoding="utf-8") as f: return json.load(f)
    return []

def gecmisi_kaydet(kullanici_adi, mesajlar):
    with open(f"LOGS/{kullanici_adi}.json", "w", encoding="utf-8") as f:
        json.dump(mesajlar, f, ensure_ascii=False, indent=4)

# 2. YAN MENÜ: GÜVENLİK
st.sidebar.title("🔐 GÜVENLİK GİRİŞİ")
ajan_kodu = st.sidebar.text_input("Ajan Kod Adı:", value="", placeholder="Örn: Eymen007")

if st.sidebar.button("🧹 Sohbeti Sıfırla"):
    if ajan_kodu:
        st.session_state.messages = []
        gecmisi_kaydet(ajan_kodu, [])
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("🗄️ İSTİHBARAT ARŞİVİ")

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
st.title("🌐 KÜRESEL SAVAŞ ODASI (LIVE)")

if not ajan_kodu:
    st.warning("⚠️ LÜTFEN GİRİŞ YAPINIZ")
    st.info("Sol menüden kod adınızı girerek sisteme bağlanın.")
    st.stop()

# Oturum Yönetimi
if "messages" not in st.session_state: st.session_state.messages = gecmisi_yukle(ajan_kodu)
if "last_user" not in st.session_state: st.session_state.last_user = ajan_kodu
elif st.session_state.last_user != ajan_kodu:
    st.session_state.messages = gecmisi_yukle(ajan_kodu)
    st.session_state.last_user = ajan_kodu

st.success(f"✅ Ajan: **{ajan_kodu}** | 🧠 Arşiv + 🌐 İnternet Aktif")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader(f"📄 Seçilen Rapor")
    st.markdown(secilen_dosya_icerigi, unsafe_allow_html=True)

with col2:
    st.subheader("🤖 Hibrit İstihbarat Analisti")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Arşivi tara veya İnterneti araştır..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        gecmisi_kaydet(ajan_kodu, st.session_state.messages)

        # --- HİBRİT ZEKA: ARŞİV + İNTERNET ---
        with st.status("🕵️‍♂️ İstihbarat toplanıyor...", expanded=True) as status:
            # 1. Adım: Arşivi Tara (RAG)
            st.write("📂 Arşiv taranıyor...")
            arsiv_bilgisi = hafizadan_bilgi_getir(prompt)
            
            # 2. Adım: İnternete Çık (Tool Use)
            st.write("🌐 İnternet sorgulanıyor...")
            internet_bilgisi = internette_ara(prompt)
            
            status.update(label="✅ Veriler toplandı!", state="complete", expanded=False)

        # 3. Adım: Hepsini Yapay Zekaya Ver
        with st.chat_message("assistant"):
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""Sen Savaş Odası'nın Baş Stratejistisin.
                            
                            Sana iki kaynaktan bilgi verildi:
                            1. 📂 GEÇMİŞ ARŞİV (İç Raporlar):
                            {arsiv_bilgisi}
                            
                            2. 🌐 CANLI İNTERNET BİLGİSİ (Dış Kaynaklar):
                            {internet_bilgisi}
                            
                            GÖREVİN:
                            Kullanıcının sorusunu cevaplarken, hem arşivdeki derin bilgiyi hem de internetten gelen taze bilgiyi birleştir.
                            - Eğer soru borsa/kur/son dakika ise İnternet verisine güven.
                            - Eğer soru strateji/tarihçe ise Arşiv verisine güven.
                            - Kaynak belirtmeyi unutma (Örn: "İnternet kaynaklarına göre...").
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
