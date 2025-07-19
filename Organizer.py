import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import shutil
import json
import sys
from PIL import Image, ImageTk # Importa Pillow para manipulação de imagens

# Define o caminho base para a pasta de arquivos do aplicativo
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".gdd_organizer_data")
ASSETS_GDD_DIR = os.path.join(APP_DATA_DIR, "Assets - GDD")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")

# Tamanho padrão para miniaturas de preview
PREVIEW_THUMB_SIZE = (100, 75)

class GDDOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Organizador de GDDs")
        self.root.geometry("1000x700") # Aumenta o tamanho inicial para acomodar os cards

        os.makedirs(ASSETS_GDD_DIR, exist_ok=True)

        self.gdds_data = {}
        # Dicionário para mapear o nome da aba ao seu frame de conteúdo (onde os cards serão exibidos)
        self.tab_content_frames = {} 
        # Mantém uma referência às imagens para evitar que o garbage collector as apague
        self.photo_images = {} 

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self._setup_main_layout()
        self._load_data()
        self._setup_context_menu()

    def _setup_main_layout(self):
        """Configura o layout principal da janela, incluindo o notebook e os botões globais."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(expand=True, fill="both")

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(expand=True, fill="both")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        add_tab_button = ttk.Button(button_frame, text="Adicionar Aba", command=self._add_tab_dialog)
        add_tab_button.pack(side="left", padx=5)

        remove_tab_button = ttk.Button(button_frame, text="Remover Aba Atual", command=self._remove_current_tab)
        remove_tab_button.pack(side="left", padx=5)

        # Atualiza a exibição de GDDs quando a aba muda
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _add_tab(self, tab_name, select_tab=True):
        """Adiciona uma nova aba ao notebook e configura seu conteúdo para exibir cards."""
        # Verifica se a aba já existe na UI do notebook
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == tab_name:
                if select_tab:
                    self.notebook.select(tab_id)
                return

        tab_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_frame, text=tab_name)
        
        self.gdds_data.setdefault(tab_name, []) 

        # Frame para os botões dentro de cada aba
        tab_buttons_frame = ttk.Frame(tab_frame)
        tab_buttons_frame.pack(pady=5, fill="x")

        load_button = ttk.Button(tab_buttons_frame, text="Carregar GDD", command=lambda: self._load_gdd_dialog(tab_name))
        load_button.pack(side="left", padx=5)

        # Frame para os cards com scrollbar
        canvas = tk.Canvas(tab_frame, borderwidth=0, background="#f0f0f0")
        vscrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        hscrollbar = ttk.Scrollbar(tab_frame, orient="horizontal", command=canvas.xview)
        self.tab_content_frames[tab_name] = inner_frame = ttk.Frame(canvas, padding="5") # Frame que conterá os cards

        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=vscrollbar.set, xscrollcommand=hscrollbar.set)

        vscrollbar.pack(side="right", fill="y")
        hscrollbar.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        # Configura o scrollbar para atualizar quando o tamanho do frame interno muda
        inner_frame.bind("<Configure>", lambda event, canvas=canvas: canvas.configure(
            scrollregion=canvas.bbox("all")
        ))
        # Ajusta o canvas para o tamanho da janela
        tab_frame.bind("<Configure>", lambda event, canvas=canvas: canvas.config(width=event.width, height=event.height))


        if select_tab:
            self.notebook.select(tab_frame)
        
        self._update_gdd_display(tab_name) # Atualiza a exibição dos cards para a nova aba

    def _on_tab_changed(self, event):
        """Chamado quando a aba selecionada muda para atualizar a exibição dos GDDs."""
        current_tab_id = self.notebook.select()
        if current_tab_id:
            current_tab_name = self.notebook.tab(current_tab_id, "text")
            self._update_gdd_display(current_tab_name)

    def _add_tab_dialog(self):
        """Abre uma caixa de diálogo para o usuário digitar o nome da nova aba."""
        tab_name = simpledialog.askstring("Nova Aba", "Digite o nome da nova aba:")
        if tab_name and tab_name.strip():
            tab_name = tab_name.strip()
            if tab_name in self.gdds_data:
                messagebox.showwarning("Aba Existente", f"A aba '{tab_name}' já existe.")
                return
            self._add_tab(tab_name)
            self._save_data()

    def _remove_current_tab(self):
        """Remove a aba atualmente selecionada."""
        current_tab_id = self.notebook.select()
        if not current_tab_id:
            messagebox.showinfo("Nenhuma Aba Selecionada", "Não há aba selecionada para remover.")
            return

        tab_name = self.notebook.tab(current_tab_id, "text")

        if messagebox.askyesno("Remover Aba", f"Tem certeza que deseja remover a aba '{tab_name}' e todos os seus GDDs associados (os arquivos não serão excluídos)?"):
            self.notebook.forget(current_tab_id)
            if tab_name in self.gdds_data:
                del self.gdds_data[tab_name]
            if tab_name in self.tab_content_frames:
                del self.tab_content_frames[tab_name]
            self._save_data()

    def _load_gdd_dialog(self, tab_name):
        """Abre a caixa de diálogo para selecionar um arquivo GDD e o processa."""
        file_path = filedialog.askopenfilename(
            title="Selecione um Arquivo GDD",
            filetypes=[("Todos os Arquivos", "*.*")]
        )
        if file_path:
            self._process_gdd_file(file_path, tab_name)

    def _process_gdd_file(self, original_file_path, tab_name):
        """Copia o arquivo GDD para a pasta de assets e o adiciona à lista."""
        file_name = os.path.basename(original_file_path)
        destination_path = os.path.join(ASSETS_GDD_DIR, file_name)

        for gdd in self.gdds_data[tab_name]:
            if os.path.basename(gdd["file_path"]) == file_name:
                messagebox.showwarning("GDD Duplicado", f"Um GDD com o nome de arquivo '{file_name}' já existe nesta aba.")
                return

        try:
            shutil.copy2(original_file_path, destination_path)
            messagebox.showinfo("Sucesso", f"Arquivo '{file_name}' copiado para 'Assets - GDD'.")

            gdd_info = {"display_name": os.path.splitext(file_name)[0], "file_path": destination_path}
            self.gdds_data[tab_name].append(gdd_info)
            self._update_gdd_display(tab_name) # Atualiza a exibição de cards
            self._save_data()
        except Exception as e:
            messagebox.showerror("Erro ao Carregar GDD", f"Não foi possível carregar o arquivo: {e}")

    def _update_gdd_display(self, tab_name):
        """Atualiza a exibição de cards para a aba especificada."""
        content_frame = self.tab_content_frames.get(tab_name)
        if not content_frame:
            return

        # Limpa todos os widgets existentes no frame de conteúdo
        for widget in content_frame.winfo_children():
            widget.destroy()

        # Re-cria os cards
        col = 0
        row = 0
        for i, gdd_info in enumerate(self.gdds_data[tab_name]):
            self._create_gdd_card(content_frame, gdd_info, tab_name, i, row, col)
            col += 1
            if col > 2: # 3 cards por linha
                col = 0
                row += 1

    def _create_gdd_card(self, parent_frame, gdd_info, tab_name, index, row, col):
        """Cria um widget de card para um GDD."""
        card_frame = ttk.Frame(parent_frame, relief="solid", borderwidth=1, padding="10")
        card_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        # Configura o grid para o card_frame
        card_frame.grid_columnconfigure(0, weight=1)

        # Área de Preview
        preview_label = ttk.Label(card_frame, text="Preview")
        file_extension = os.path.splitext(gdd_info["file_path"])[1].lower()

        if file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            try:
                img = Image.open(gdd_info["file_path"])
                img.thumbnail(PREVIEW_THUMB_SIZE) # Redimensiona a imagem para a miniatura
                photo = ImageTk.PhotoImage(img)
                preview_label.config(image=photo, text="")
                self.photo_images[gdd_info["file_path"]] = photo # Mantém referência para evitar garbage collection
            except Exception as e:
                preview_label.config(text=f"Erro ao carregar imagem: {e}", foreground="red")
        else:
            # Para outros tipos de arquivo, mostra um ícone genérico ou texto
            # Removido width e height que causam o erro para ttk.Label com texto
            preview_label.config(text=f"Documento\n({file_extension})", relief="groove") 
            preview_label.config(anchor="center", justify="center")
            # Adiciona um padding para simular um tamanho fixo visualmente
            preview_label.config(padding=(10, 20)) # Ajuste o padding conforme necessário para o visual desejado


        preview_label.pack(pady=5, fill="x", expand=True)

        # Nome do GDD
        name_label = ttk.Label(card_frame, text=gdd_info["display_name"], wraplength=150, font=("Arial", 10, "bold"))
        name_label.pack(pady=5)

        # Botões de Ação
        action_frame = ttk.Frame(card_frame)
        action_frame.pack(pady=5)

        open_button = ttk.Button(action_frame, text="Abrir", command=lambda: self._open_gdd_from_card(gdd_info))
        open_button.pack(side="left", padx=2)

        rename_button = ttk.Button(action_frame, text="Renomear", command=lambda: self._rename_gdd_from_card(gdd_info, tab_name))
        rename_button.pack(side="left", padx=2)

        remove_button = ttk.Button(action_frame, text="Remover", command=lambda: self._remove_gdd_from_card(gdd_info, tab_name))
        remove_button.pack(side="left", padx=2)

        # Associa o menu de contexto ao card inteiro
        card_frame.bind("<Button-3>", lambda event: self._show_context_menu_for_card(event, gdd_info, tab_name))
        preview_label.bind("<Button-3>", lambda event: self._show_context_menu_for_card(event, gdd_info, tab_name))
        name_label.bind("<Button-3>", lambda event: self._show_context_menu_for_card(event, gdd_info, tab_name))


    def _setup_context_menu(self):
        """Cria o menu de contexto para os itens da listbox."""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Abrir GDD", command=self._open_gdd_from_context)
        self.context_menu.add_command(label="Renomear GDD", command=self._rename_gdd_from_context)
        self.context_menu.add_command(label="Remover GDD da Aba", command=self._remove_gdd_from_context)
        # Variáveis para armazenar o GDD e a aba clicados com o botão direito
        self.context_gdd_info = None
        self.context_tab_name = None

    def _show_context_menu_for_card(self, event, gdd_info, tab_name):
        """Exibe o menu de contexto para um card específico."""
        self.context_gdd_info = gdd_info
        self.context_tab_name = tab_name
        self.context_menu.post(event.x_root, event.y_root)

    def _open_gdd_from_card(self, gdd_info):
        """Abre o GDD a partir do clique no botão do card."""
        self._open_gdd_file(gdd_info)

    def _rename_gdd_from_card(self, gdd_info, tab_name):
        """Renomeia o GDD a partir do clique no botão do card."""
        self._rename_gdd_logic(gdd_info, tab_name)

    def _remove_gdd_from_card(self, gdd_info, tab_name):
        """Remove o GDD a partir do clique no botão do card."""
        self._remove_gdd_from_tab_logic(gdd_info, tab_name)

    def _open_gdd_from_context(self):
        """Abre o GDD a partir do menu de contexto."""
        if self.context_gdd_info:
            self._open_gdd_file(self.context_gdd_info)

    def _rename_gdd_from_context(self):
        """Renomeia o GDD a partir do menu de contexto."""
        if self.context_gdd_info and self.context_tab_name:
            self._rename_gdd_logic(self.context_gdd_info, self.context_tab_name)

    def _remove_gdd_from_context(self):
        """Remove o GDD a partir do menu de contexto."""
        if self.context_gdd_info and self.context_tab_name:
            self._remove_gdd_from_tab_logic(self.context_gdd_info, self.context_tab_name)

    def _open_gdd_file(self, gdd_info):
        """Lógica para abrir o GDD selecionado com o editor padrão do sistema."""
        file_path = gdd_info["file_path"]
        if os.path.exists(file_path):
            try:
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin": # macOS
                    subprocess.call(["open", file_path])
                else: # Linux
                    subprocess.call(["xdg-open", file_path])
                messagebox.showinfo("Abrir GDD", f"Abrindo '{gdd_info['display_name']}'...")
            except Exception as e:
                messagebox.showerror("Erro ao Abrir", f"Não foi possível abrir o arquivo: {e}")
        else:
            messagebox.showerror("Arquivo Não Encontrado", f"O arquivo '{gdd_info['display_name']}' não foi encontrado em '{file_path}'. Ele pode ter sido movido ou excluído externamente.")

    def _rename_gdd_logic(self, gdd_info_to_rename, tab_name):
        """Lógica para renomear o GDD."""
        old_display_name = gdd_info_to_rename["display_name"]
        old_file_path = gdd_info_to_rename["file_path"]

        new_display_name = simpledialog.askstring("Renomear GDD", f"Novo nome para '{old_display_name}':",
                                                  initialvalue=old_display_name)
        if new_display_name and new_display_name.strip() and new_display_name.strip() != old_display_name:
            new_display_name = new_display_name.strip()
            
            # Encontra o índice do GDD na lista da aba
            try:
                index_in_list = self.gdds_data[tab_name].index(gdd_info_to_rename)
            except ValueError:
                messagebox.showerror("Erro", "GDD não encontrado para renomear.")
                return

            # Renomeia o arquivo real no sistema de arquivos
            try:
                file_extension = os.path.splitext(old_file_path)[1]
                new_file_path = os.path.join(ASSETS_GDD_DIR, f"{new_display_name}{file_extension}")

                if os.path.exists(old_file_path):
                    shutil.move(old_file_path, new_file_path)
                    messagebox.showinfo("Sucesso", f"Arquivo renomeado para '{new_display_name}{file_extension}'.")
                else:
                    messagebox.showwarning("Aviso", f"O arquivo original '{old_file_path}' não foi encontrado. Apenas o nome de exibição será atualizado.")

                # Atualiza os dados no dicionário
                self.gdds_data[tab_name][index_in_list]["display_name"] = new_display_name
                self.gdds_data[tab_name][index_in_list]["file_path"] = new_file_path
                self._update_gdd_display(tab_name) # Atualiza a exibição de cards
                self._save_data()
            except Exception as e:
                messagebox.showerror("Erro ao Renomear", f"Não foi possível renomear o GDD: {e}")

    def _remove_gdd_from_tab_logic(self, gdd_info_to_remove, tab_name):
        """Lógica para remover o GDD da aba (não exclui o arquivo físico)."""
        display_name = gdd_info_to_remove["display_name"]
        if messagebox.askyesno("Remover GDD", f"Tem certeza que deseja remover '{display_name}' desta aba? O arquivo físico NÃO será excluído."):
            # Encontra e remove o GDD da lista da aba
            try:
                self.gdds_data[tab_name].remove(gdd_info_to_remove)
                self._update_gdd_display(tab_name) # Atualiza a exibição de cards
                self._save_data()
            except ValueError:
                messagebox.showerror("Erro", "GDD não encontrado para remover.")


    def _save_data(self):
        """Salva o estado atual das abas e GDDs em um arquivo JSON."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.gdds_data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar os dados: {e}")

    def _load_data(self):
        """Carrega o estado das abas e GDDs de um arquivo JSON."""
        default_tab_names = ["Em Andamento", "Concluído", "Esboço para GameJam"]
        
        # Tenta carregar os dados existentes
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict):
                        self.gdds_data = loaded_data
                    else:
                        raise ValueError("Conteúdo do arquivo de configuração inválido.")
            except (json.JSONDecodeError, ValueError) as e:
                messagebox.showwarning("Erro de Leitura", f"O arquivo de configuração está corrompido ou inválido ({e}). Iniciando com dados vazios.")
                self.gdds_data = {}
            except Exception as e:
                messagebox.showerror("Erro ao Carregar", f"Não foi possível carregar os dados: {e}")
                self.gdds_data = {}
        else:
            self.gdds_data = {}

        # Adiciona/recria a UI para as abas carregadas
        for tab_name in list(self.gdds_data.keys()):
            self._add_tab(tab_name, select_tab=False)
            # A chamada para _update_gdd_display já está dentro de _add_tab, então não precisa aqui.

        # Garante que as abas padrão existam tanto nos dados quanto na UI
        for default_tab_name in default_tab_names:
            if default_tab_name not in self.gdds_data:
                self.gdds_data[default_tab_name] = []
                self._add_tab(default_tab_name, select_tab=False)
        
        # Seleciona a primeira aba se houver alguma
        if self.notebook.tabs():
            self.notebook.select(self.notebook.tabs()[0])
        
        self._save_data()

if __name__ == "__main__":
    if sys.platform != "win32":
        import subprocess

    root = tk.Tk()
    app = GDDOrganizerApp(root)
    root.mainloop()
