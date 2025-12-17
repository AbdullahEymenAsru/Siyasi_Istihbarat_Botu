import flet as ft
import os
from groq import Groq
from supabase import create_client

# --- AYARLAR ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None

# --- ANA UYGULAMA ---
def main(page: ft.Page):
    # 1. SAYFA AYARLARI (GÖRÜNÜRLÜK İÇİN)
    page.title = "SAVAŞ ODASI"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#050505"  # Simsiyah Arka Plan
    page.padding = 20
    
    # 2. ÜST BAŞLIK (HEADER)
    header = ft.Container(
        content=ft.Row([
            ft.Icon(name="shield", color="#00ff00", size=40), # Neon Yeşil İkon
            ft.Column([
                ft.Text("SAVAŞ ODASI", size=24, weight="bold", color="#ffffff"),
                ft.Text("Taktik İstihbarat Terminali", size=12, color="#cccccc")
            ])
        ], alignment=ft.MainAxisAlignment.CENTER),
        padding=15,
        bgcolor="#1a1a1a", # Koyu Gri Kutu
        border=ft.border.all(1, "#00ff00"), # Yeşil Çerçeve
        border_radius=10
    )

    # 3. MESAJ LİSTESİ (CHAT GEÇMİŞİ)
    chat_list = ft.ListView(
        expand=True, 
        spacing=10, 
        auto_scroll=True,
        padding=10
    )

    # 4. MESAJ GÖNDERME FONKSİYONU
    def send_message(e):
        if not user_input.value: return

        # --- Kullanıcı Mesajı (Sağda, Mavi) ---
        chat_list.controls.append(
            ft.Row([
                ft.Container(
                    content=ft.Text(f"KOMUTAN: {user_input.value}", color="white", weight="bold"),
                    padding=12,
                    bgcolor="#0d47a1", # Koyu Mavi
                    border_radius=ft.border_radius.only(top_left=15, top_right=15, bottom_left=15, bottom_right=0),
                    border=ft.border.all(1, "#42a5f5"), # Açık Mavi Çerçeve
                )
            ], alignment=ft.MainAxisAlignment.END)
        )
        
        prompt = user_input.value
        user_input.value = "" # Kutuyu temizle
        page.update()

        # --- AI Cevabı (Solda, Yeşil/Gri) ---
        try:
            response_text = "İstihbarat analiz ediliyor..."
            
            if client:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = completion.choices[0].message.content
            else:
                response_text = "HATA: API Anahtarı bulunamadı!"

            chat_list.controls.append(
                ft.Row([
                    ft.Container(
                        content=ft.Markdown(
                            response_text, 
                            extension_set="gitHubWeb", 
                            code_theme="atom-one-dark"
                        ),
                        padding=12,
                        bgcolor="#212121", # Koyu Gri
                        border_radius=ft.border_radius.only(top_left=15, top_right=15, bottom_left=0, bottom_right=15),
                        border=ft.border.all(1, "#00ff00"), # Neon Yeşil Çerçeve
                        width=350 # Genişlik sınırı
                    )
                ], alignment=ft.MainAxisAlignment.START)
            )
            page.update()

        except Exception as err:
            chat_list.controls.append(ft.Text(f"SİSTEM HATASI: {err}", color="red"))
            page.update()

    # 5. GİRİŞ ALANI (INPUT AREA)
    user_input = ft.TextField(
        hint_text="Emrinizi girin...",
        hint_style=ft.TextStyle(color="#666666"),
        color="white",
        cursor_color="#00ff00",
        border_color="#00ff00", # Yeşil Çerçeve
        bgcolor="#111111",
        expand=True,
        on_submit=send_message
    )

    send_btn = ft.IconButton(
        icon="send", 
        icon_color="#00ff00", 
        tooltip="Gönder",
        on_click=send_message
    )

    # 6. DÜZENİ BİRLEŞTİRME
    layout = ft.Column([
        header,
        ft.Divider(color="#333333"),
        ft.Container(
            content=chat_list,
            expand=True, # Ekranı doldurması için kritik
            bgcolor="#0a0a0a", # Sohbet alanı arka planı
            border=ft.border.all(1, "#333333"),
            border_radius=10
        ),
        ft.Row([user_input, send_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    ], expand=True) # Ana sütunun da genişlemesi şart

    page.add(layout)

# --- BAŞLATMA ---
if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8080)
