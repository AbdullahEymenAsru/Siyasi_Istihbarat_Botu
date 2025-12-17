import flet as ft
import os
from groq import Groq
from supabase import create_client

# --- AYARLAR (Replit Secrets'tan gelecek) ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# İstemcileri Başlat
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None

# --- ANA UYGULAMA (FLET) ---
def main(page: ft.Page):
    page.title = "KÜRESEL SAVAŞ ODASI"
    page.theme_mode = ft.ThemeMode.DARK # Askeri Tema
    page.scroll = "adaptive"
    
    # 1. BAŞLIK PARÇASI
    # DÜZELTME: ft.icons.SHIELD yerine name="shield" kullanıldı.
    header = ft.Container(
        content=ft.Row([
            ft.Icon(name="shield", color="red", size=40),
            ft.Column([
                ft.Text("SAVAŞ ODASI", size=25, weight="bold"),
                ft.Text("Flet Destekli İstihbarat Portalı", size=12, color="grey")
            ])
        ], alignment=ft.MainAxisAlignment.CENTER),
        padding=20,
        bgcolor="#111",
        border_radius=10
    )

    # 2. CHAT FONKSİYONU
    def send_message(e):
        if not user_input.value: return
        
        # Kullanıcı Mesajını Ekrana Ekle
        chat_list.controls.append(
            ft.Row([
                ft.Container(
                    content=ft.Text(f"SİZ: {user_input.value}", color="white"),
                    padding=10,
                    bgcolor="#34495e",
                    border_radius=10
                )
            ], alignment=ft.MainAxisAlignment.END)
        )
        page.update()

        # AI Cevabı (Groq)
        try:
            prompt = user_input.value
            user_input.value = "" # Kutuyu temizle
            
            if client:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                response = completion.choices[0].message.content
            else:
                response = "HATA: API Anahtarı bulunamadı! Secrets ayarlarını kontrol edin."

            # Asistan Mesajını Ekrana Ekle
            chat_list.controls.append(
                ft.Row([
                    ft.Container(
                        content=ft.Markdown(response),
                        padding=10,
                        bgcolor="#2c3e50",
                        border_radius=10,
                        width=300 # Mobilde taşmasın
                    )
                ], alignment=ft.MainAxisAlignment.START)
            )
            page.update()
            
        except Exception as err:
            page.snack_bar = ft.SnackBar(ft.Text(f"Hata: {err}"))
            page.snack_bar.open = True
            page.update()

    # 3. ARAYÜZ ELEMANLARI
    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    user_input = ft.TextField(hint_text="Emriniz?", expand=True, on_submit=send_message)
    # DÜZELTME: ft.icons.SEND yerine icon="send" kullanıldı.
    send_btn = ft.IconButton(icon="send", icon_color="red", on_click=send_message)

    # 4. SAYFA DÜZENİ (LAYOUT)
    layout = ft.Column([
        header,
        ft.Divider(),
        ft.Container(content=chat_list, expand=True, padding=10, border=ft.border.all(1, "grey"), border_radius=10),
        ft.Row([user_input, send_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    ], expand=True)

    page.add(layout)

# --- UYGULAMAYI BAŞLAT (Replit Konfigürasyonu) ---
if __name__ == "__main__":
    # Replit'te 'view=ft.AppView.WEB_BROWSER' ve 'port=8080' olması kritik öneme sahiptir.
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8080)
