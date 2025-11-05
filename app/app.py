import customtkinter as ctk
from tkinter import messagebox
import queue
import threading
import os
from PIL import Image
from process_email.ler_email import iniciar_monitoramento

# Configuração inicial do CustomTkinter
ctk.set_appearance_mode("Dark")  # Modo: "System", "Dark" ou "Light"
ctk.set_default_color_theme("dark-blue")  # Tema: "blue", "dark-blue", "green"

log_queue = queue.Queue()
running_event = threading.Event()

class QueueOutput:
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, message):
        if message.strip():  # Adiciona apenas mensagens não vazias
            self.log_queue.put(message)

    def flush(self):
        pass

# Atualiza a interface com as mensagens do log
def update_text_widget(text_widget, log_queue):
    try:
        while True:
            message = log_queue.get_nowait()
            text_widget.configure(state='normal')
            text_widget.insert(ctk.END, message + '\n')
            text_widget.configure(state='disabled')
            text_widget.see(ctk.END)
    except queue.Empty:
        pass
    text_widget.after(500, update_text_widget, text_widget, log_queue)

def iniciar_sistema():
    messagebox.showinfo("Informação", f"Iniciando monitoramento de E-mail.")
    threading.Thread(target=iniciar_monitoramento, args=("pasta/anexo/email", log_queue), daemon=True).start()

# Criar a janela principal
janela = ctk.CTk()
janela.geometry("700x500")
janela.title("KADRIX SEFAZ")
janela.minsize(600, 400)

# Centralizar a janela principal
largura_tela = janela.winfo_screenwidth()
altura_tela = janela.winfo_screenheight()
largura_janela = 600
altura_janela = 400
pos_x = (largura_tela // 2) - (largura_janela // 2)
pos_y = (altura_tela // 2) - (altura_janela // 2)
janela.geometry(f"{largura_janela}x{altura_janela}+{pos_x}+{pos_y}")
# Imagem de fundo
bg_image = None
background_label = None

# Layout principal
janela.grid_columnconfigure(0, weight=1)   # Centraliza elementos na coluna
janela.grid_rowconfigure(1, weight=1)      # Área do log cresce

# Botão de análise
botao_analise = ctk.CTkButton(
    janela,
    text="EMISSÃO SEFA",
    fg_color="#1f538d",
    hover_color="#14375e",
    height=40,
    width=200,
    command=iniciar_sistema
)
botao_analise.grid(row=0, column=0, pady=(30, 10), sticky="n")

# Área de log
log_frame = ctk.CTkFrame(
    janela,
    fg_color="gray20",
    corner_radius=8,
    border_width=1,
    border_color="gray40"
)
log_frame.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")

log_frame.grid_columnconfigure(0, weight=1)
log_frame.grid_rowconfigure(0, weight=1)

# Caixa de log
log_box = ctk.CTkTextbox(
    log_frame,
    state="disabled",
    fg_color="transparent",
    text_color="white",
    font=("Arial", 12),
    wrap="word",
    border_width=0,
    scrollbar_button_color="gray30"
)
log_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

# Redimensionamento da imagem
def resize_background(event):
    if bg_image and hasattr(janela, "label_img"):
        new_width, new_height = event.width, event.height
        bg_image.configure(size=(new_width, new_height))
        janela.label_img.configure(image=bg_image)

janela.bind("<Configure>", resize_background)

# Atualização do log
update_text_widget(log_box, log_queue)

janela.mainloop()