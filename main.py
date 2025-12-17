import flet as ft
import os
from groq import Groq
from supabase import create_client

# --- AYARLAR ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None

# --- ANA UYGULAMA ---
def main(page: ft.Page):
    # 1. GÖRÜNÜRLÜK AYARLARI (Karanlık ama Net)
    page.title = "KÜRESEL SAVAŞ ODASI"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#050505"  # Derin Siyah Zemin
    page.scroll = "adaptive"
    page.padding = 20

    # 2. BAŞLIK (HEADER)
    header = ft.Container(
        content=ft.Row([
            # İKON DÜZELTMESİ: name="shield"
            ft.Icon(name="shield", color="#00ff00", size=40), 
            ft.Column([
                ft.Text("SAVAŞ ODASI", size=24, weight="bold", color="white"),
                ft.Text("Flet Destekli İstihbarat Portalı", size=12, color="#cccccc")
            ])
        ], alignment=ft.MainAxisAlignment.CENTER),
        padding=15,
        bgcolor="#1a1a1a",
        border=ft.border.all(1, "#00ff00"), # Yeşil Çerçeve (Görünürlük için)
        border_radius=10
    )

    # 3. CHAT FONKSİYONU
    def send_message(e):
        if not user_input.value: return
        
        # Kullanıcı Mesajı (Sağ - Mavi)
        chat_list.controls.append(
            ft.Row([
                ft.Container(
                    content=ft.Text(f"SİZ: {user_input.value}", color="white", weight="bold"),
                    padding=12,
                    bgcolor="#0d47a1", # Belirgin Mavi
                    border_radius=10,
                    border=ft.border.all(1, "#42a5f5")
                )
            ], alignment=ft.MainAxisAlignment.END)
        )
        page.update()

        # AI Cevabı
        try:
            prompt = user_input.value
            user_input.value = "" 
            
            if client:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                response = completion.choices[0].message.content
            else:
                response = "HATA: API Anahtarı bulunamadı! Secrets kısmını kontrol edin."

            # Asistan Mesajı (Sol - Gri/Yeşil)
            chat_list.controls.append(
                ft.Row([
                    ft.Container(
                        content=ft.Markdown(response),
                        padding=12,
                        bgcolor="#212121",
                        border_radius=10,
                        border=ft.border.all(1, "#00ff00"), # Yeşil Sınır
                        width=350 
                    )
                ], alignment=ft.MainAxisAlignment.START)
            )
            page.update()
            
        except Exception as err:
            page.snack_bar = ft.SnackBar(ft.Text(f"Hata: {err}"))
            page.snack_bar.open = True
            page.update()

    # 4. ARAYÜZ ELEMANLARI
    chat_list = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=10)
    
    user_input = ft.TextField(
        hint_text="Emriniz?", 
        hint_style=ft.TextStyle(color="#666"),
        color="white",
        border_color="#00ff00", # Giriş kutusu çerçevesi
        expand=True, 
        on_submit=send_message
    )
    
    # İKON DÜZELTMESİ: icon="send"
    send_btn = ft.IconButton(icon="send", icon_color="#00ff00", on_click=send_message)

    # 5. SAYFA DÜZENİ
    layout = ft.Column([
        header,
        ft.Divider(color="#333"),
        ft.Container(
            content=chat_list, 
            expand=True, 
            padding=5, 
            border=ft.border.all(1, "#333"), # Chat alanı sınırları
            border_radius=10,
            bgcolor="#0a0a0a"
        ),
        ft.Row([user_input, send_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    ], expand=True)

    page.add(layout)

# --- KRİTİK BAŞLATMA AYARI ---
if __name__ == "__main__":
    # host="0.0.0.0" -> Replit'in dışarıya yayın yapmasını sağlar.
    # port=8080 -> Replit'in dinlediği standart porttur.
    # view=WEB_BROWSER -> Tarayıcı modunda açar.
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8080, host="0.0.0.0")
