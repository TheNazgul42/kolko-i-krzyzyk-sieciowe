import socket
import threading
import tkinter as tk
import random

BUFFER_SIZE = 1024

# Funkcje pomocnicze do rysowania gradientu
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return '#' + ''.join(f'{v:02x}' for v in rgb)

def interpolate_color(color1, color2, factor):
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return rgb_to_hex((r, g, b))

def draw_gradient(canvas, width, height, color1, color2):
    """Rysuje pionowy gradient na danym canvasie."""
    steps = height
    for i in range(steps):
        factor = i / steps
        color = interpolate_color(color1, color2, factor)
        canvas.create_line(0, i, width, i, fill=color)

def get_local_ip():
    """Wykrywa lokalny adres IP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def get_free_port():
    """Losuje port z zakresu 49152-65535 i sprawdza, czy jest wolny."""
    while True:
        port = random.randint(49152, 65535)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue

class TicTacToeNetworkGame:
    def __init__(self, master, is_host, host_ip=None, host_port=None, on_game_end=None):
        """
        Inicjalizacja gry sieciowej.
        :param master: główne okno
        :param is_host: True dla hosta, False dla klienta
        :param host_ip: adres IP hosta (dla klienta)
        :param host_port: port hosta (dla klienta)
        :param on_game_end: funkcja wywoływana po zakończeniu gry (powrót do menu)
        """
        self.master = master
        self.is_host = is_host
        self.host_ip = host_ip
        self.host_port = host_port
        self.on_game_end = on_game_end
        self.sock = None   # Socket klienta (dla klienta)
        self.conn = None   # Socket połączenia (dla hosta)
        self.my_mark = None   # "X" lub "O"
        self.other_mark = None
        self.turn = None      # Aktualny ruch
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.game_over = False
        self.reset_pending = False  # Flaga resetu
        self.port = None  # Port na którym host nasłuchuje
        self.setup_ui()
        if self.is_host:
            self.start_server()
        else:
            self.connect_to_server()

    def setup_ui(self):
        """Tworzy interfejs gry – plansza (Canvas) i przyciski sterujące."""
        self.game_frame = tk.Frame(self.master, bg="#2C3E50")
        self.game_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.status_label = tk.Label(self.game_frame, text="Inicjalizacja...", font=("Helvetica", 16, "bold"),
                                     bg="#2C3E50", fg="white")
        self.status_label.pack(pady=(0, 10))

        # Canvas z planszą – teraz z gradientowym tłem
        self.canvas = tk.Canvas(self.game_frame, width=300, height=300, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.canvas_click)

        control_frame = tk.Frame(self.game_frame, bg="#2C3E50")
        control_frame.pack(pady=10)
        self.reset_button = tk.Button(control_frame, text="Reset gry", font=("Helvetica", 14, "bold"),
                                      bg="#2980B9", fg="white", command=self.request_reset)
        self.reset_button.grid(row=0, column=0, padx=10)
        self.exit_button = tk.Button(control_frame, text="Wyjdź do menu", font=("Helvetica", 14, "bold"),
                                     bg="#2980B9", fg="white", command=self.exit_game)
        self.exit_button.grid(row=0, column=1, padx=10)

        self.draw_board()

    def draw_board(self):
        """Rysuje planszę – gradientowe tło, siatkę z cieniem oraz symbole."""
        self.canvas.delete("all")
        width, height = 300, 300
        # Rysujemy gradientowe tło
        draw_gradient(self.canvas, width, height, "#D7DDE8", "#F7F9FC")

        cell_size = 100
        # Rysujemy cień siatki (offset +3 piksele)
        for i in range(1, 3):
            self.canvas.create_line(0+3, i * cell_size+3, width+3, i * cell_size+3, width=3, fill="#7f8c8d")
            self.canvas.create_line(i * cell_size+3, 0+3, i * cell_size+3, height+3, width=3, fill="#7f8c8d")
        # Rysujemy główne linie siatki
        for i in range(1, 3):
            self.canvas.create_line(0, i * cell_size, width, i * cell_size, width=3, fill="#2980B9")
            self.canvas.create_line(i * cell_size, 0, i * cell_size, height, width=3, fill="#2980B9")

        # Rysujemy symbole – zamiast tekstu, rysujemy wektorowe kształty z cieniem
        for i in range(3):
            for j in range(3):
                mark = self.board[i][j]
                if mark:
                    # Określamy margines dla symbolu
                    x0 = j * cell_size + 20
                    y0 = i * cell_size + 20
                    x1 = j * cell_size + cell_size - 20
                    y1 = i * cell_size + cell_size - 20
                    if mark == "X":
                        # Rysujemy cień dla X (offset +2)
                        self.canvas.create_line(x0+2, y0+2, x1+2, y1+2, width=4, fill="#7f8c8d")
                        self.canvas.create_line(x1+2, y0+2, x0+2, y1+2, width=4, fill="#7f8c8d")
                        # Rysujemy główne X
                        self.canvas.create_line(x0, y0, x1, y1, width=4, fill="#E74C3C")
                        self.canvas.create_line(x1, y0, x0, y1, width=4, fill="#E74C3C")
                    elif mark == "O":
                        # Rysujemy cień dla O
                        self.canvas.create_oval(x0+2, y0+2, x1+2, y1+2, width=4, outline="#7f8c8d")
                        # Rysujemy główne O
                        self.canvas.create_oval(x0, y0, x1, y1, width=4, outline="#3498DB")

    def canvas_click(self, event):
        """Obsługuje kliknięcia na planszy."""
        if self.game_over:
            return
        cell_size = 100
        col = event.x // cell_size
        row = event.y // cell_size
        if row < 0 or row > 2 or col < 0 or col > 2:
            return
        if self.board[row][col] != "":
            return
        if self.turn != self.my_mark:
            self.status_label.config(text="Nie twój ruch!")
            return
        self.make_move(row, col, self.my_mark)
        self.send_message(f"MOVE|{row}|{col}")

    def make_move(self, r, c, mark):
        """Aktualizuje planszę po ruchu oraz sprawdza warunki zwycięstwa."""
        if self.board[r][c] == "" and not self.game_over:
            self.board[r][c] = mark
            self.draw_board()
            winner_info = self.get_winner_info(mark)
            if winner_info:
                self.status_label.config(text=f"Gracz {mark} wygrywa!")
                self.draw_winning_line(winner_info)
                self.game_over = True
            elif self.is_board_full():
                self.status_label.config(text="Remis!")
                self.game_over = True
            else:
                self.turn = self.other_mark if self.turn == self.my_mark else self.my_mark
                turn_text = "Twój ruch" if self.turn == self.my_mark else "Ruch przeciwnika"
                self.status_label.config(text=turn_text)

    def get_winner_info(self, mark):
        """Sprawdza, czy dany gracz wygrał."""
        for i in range(3):
            if all(self.board[i][j] == mark for j in range(3)):
                return (mark, "row", i)
        for j in range(3):
            if all(self.board[i][j] == mark for i in range(3)):
                return (mark, "col", j)
        if all(self.board[i][i] == mark for i in range(3)):
            return (mark, "diag", None)
        if all(self.board[i][2 - i] == mark for i in range(3)):
            return (mark, "antidiag", None)
        return None

    def draw_winning_line(self, winner_info):
        """Rysuje przekreślenie wygrywającej kombinacji."""
        cell_size = 100
        _, win_type, index = winner_info
        padding = 10
        if win_type == "row":
            y = index * cell_size + cell_size / 2
            x1, y1 = padding, y
            x2, y2 = 300 - padding, y
        elif win_type == "col":
            x = index * cell_size + cell_size / 2
            x1, y1 = x, padding
            x2, y2 = x, 300 - padding
        elif win_type == "diag":
            x1, y1 = padding, padding
            x2, y2 = 300 - padding, 300 - padding
        elif win_type == "antidiag":
            x1, y1 = 300 - padding, padding
            x2, y2 = padding, 300 - padding
        self.canvas.create_line(x1, y1, x2, y2, width=4, fill="#27AE60", tags="win_line")

    def is_board_full(self):
        """Sprawdza, czy plansza jest pełna."""
        return all(self.board[i][j] != "" for i in range(3) for j in range(3))

    def reset_board(self):
        """Czyści planszę i usuwa wygrywającą linię."""
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.draw_board()
        self.canvas.delete("win_line")
        self.game_over = False

    def request_reset(self):
        """Wysyła prośbę o reset gry."""
        if self.reset_pending:
            return
        self.reset_pending = True
        self.status_label.config(text="Wysłano prośbę o reset, oczekiwanie na odpowiedź...")
        self.reset_button.config(state=tk.DISABLED)
        if self.is_host:
            self.send_message("RESET_REQUEST", connection=self.conn)
        else:
            self.send_message("RESET_REQUEST")

    def ask_reset_confirmation(self):
        """Wyświetla okno dialogowe z zapytaniem o reset."""
        dialog = tk.Toplevel(self.master)
        dialog.title("Reset gry")
        dialog.configure(bg="#2C3E50")
        tk.Label(dialog, text="Przeciwnik prosi o reset gry.\nCzy akceptujesz?", font=("Helvetica", 14),
                 bg="#2C3E50", fg="white").pack(pady=10, padx=10)

        def accept():
            if self.reset_pending:
                if self.is_host:
                    self.send_message("RESET_ACCEPT", connection=self.conn)
                else:
                    self.send_message("RESET_ACCEPT")
                dialog.destroy()
                self.perform_reset()

        def reject():
            if self.reset_pending:
                if self.is_host:
                    self.send_message("RESET_REJECT", connection=self.conn)
                else:
                    self.send_message("RESET_REJECT")
                self.reset_pending = False
                self.status_label.config(text="Reset anulowany.")
                self.reset_button.config(state=tk.NORMAL)
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg="#2C3E50")
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Tak", font=("Helvetica", 12, "bold"), bg="#27AE60", fg="white",
                  command=accept).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Nie", font=("Helvetica", 12, "bold"), bg="#C0392B", fg="white",
                  command=reject).pack(side=tk.LEFT, padx=5)
        dialog.attributes('-topmost', True)

    def perform_reset(self):
        """Przeprowadza reset gry."""
        self.reset_board()
        self.reset_pending = False
        self.reset_button.config(state=tk.NORMAL)
        if self.is_host:
            first_turn = random.choice(["X", "O"])
            self.turn = first_turn
            self.send_message("START|" + first_turn, connection=self.conn)
            turn_text = "Losowanie: zaczynasz ty!" if self.turn == self.my_mark else "Losowanie: przeciwnik zaczyna!"
            self.status_label.config(text=turn_text)

    def send_message(self, message, connection=None):
        """Wysyła wiadomość do drugiej strony."""
        try:
            if self.is_host:
                if connection is None:
                    connection = self.conn
                connection.sendall((message + "\n").encode())
            else:
                self.sock.sendall((message + "\n").encode())
        except Exception as e:
            print("Błąd wysyłania:", e)

    def receive_messages(self, sock):
        """Odbiera wiadomości z połączenia i przekazuje je do przetwarzania."""
        buffer = ""
        while True:
            try:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    break
                buffer += data.decode()
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self.process_message(line.strip())
            except Exception as e:
                print("Błąd odbioru:", e)
                break
        print("Połączenie zakończone")
        self.master.after(100, self.exit_game)

    def process_message(self, message):
        """Przetwarza odebrane wiadomości wg ustalonego protokołu."""
        print("Odebrano:", message)
        parts = message.split("|")
        if parts[0] == "START":
            first_turn = parts[1]
            self.turn = first_turn
            turn_text = "Twój ruch" if self.turn == self.my_mark else "Ruch przeciwnika"
            self.status_label.config(text=turn_text)
        elif parts[0] == "MOVE":
            try:
                r = int(parts[1])
                c = int(parts[2])
            except:
                return
            self.master.after(0, self.make_move, r, c, self.other_mark)
        elif parts[0] == "RESET_REQUEST":
            if not self.reset_pending:
                self.reset_pending = True
                self.master.after(0, self.ask_reset_confirmation)
            else:
                self.send_message("RESET_ACCEPT", connection=self.conn if self.is_host else None)
                self.master.after(0, self.perform_reset)
        elif parts[0] == "RESET_ACCEPT":
            if self.reset_pending:
                self.master.after(0, self.perform_reset)
        elif parts[0] == "RESET_REJECT":
            self.reset_pending = False
            self.status_label.config(text="Reset request odrzucony przez przeciwnika.")
            self.reset_button.config(state=tk.NORMAL)

    def connect_to_server(self):
        """Konfiguracja klienta – łączenie z hostem."""
        self.my_mark = "O"
        self.other_mark = "X"
        self.turn = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host_ip, self.host_port))
        except Exception as e:
            self.status_label.config(text=f"Błąd połączenia: {e}")
            return
        self.listen_thread = threading.Thread(target=self.receive_messages, args=(self.sock,), daemon=True)
        self.listen_thread.start()
        self.status_label.config(text="Połączono z hostem.")

    def start_server(self):
        """Konfiguracja hosta – ustawia symbole, losuje, kto zaczyna, wybiera wolny port oraz nasłuchuje połączenia."""
        self.my_mark = "X"
        self.other_mark = "O"
        first_turn = random.choice(["X", "O"])
        self.turn = first_turn
        self.port = get_free_port()  # losujemy wolny port
        local_ip = get_local_ip()
        self.status_label.config(
            text=f"Hostujesz grę.\nTwój IP: {local_ip}\nPort: {self.port}\nOczekiwanie na przeciwnika..."
        )
        server_thread = threading.Thread(target=self.server_thread, daemon=True)
        server_thread.start()

    def server_thread(self):
        """Wątek serwera – nasłuchuje połączenia klienta, wysyła informację START."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_sock.bind(("", self.port))
        except Exception as e:
            print("Błąd bindowania portu:", e)
            self.status_label.config(text=f"Błąd bindowania portu: {e}")
            return
        server_sock.listen(1)
        self.conn, addr = server_sock.accept()
        print("Połączono z:", addr)
        self.send_message("START|" + self.turn, connection=self.conn)
        self.listen_thread = threading.Thread(target=self.receive_messages, args=(self.conn,), daemon=True)
        self.listen_thread.start()
        turn_text = "Losowanie: zaczynasz ty!" if self.turn == self.my_mark else "Losowanie: przeciwnik zaczyna!"
        self.status_label.config(text=turn_text)

    def exit_game(self):
        """Kończy rozgrywkę, zamyka połączenia i wraca do menu."""
        try:
            if self.is_host and self.conn:
                self.conn.close()
            if not self.is_host and self.sock:
                self.sock.close()
        except Exception as e:
            print("Błąd zamknięcia połączenia:", e)
        self.game_frame.destroy()
        if self.on_game_end:
            self.on_game_end()


class MainMenu:
    def __init__(self, master):
        """Tworzy główne menu z opcjami: hostuj, dołącz, wyjdź."""
        self.master = master
        self.master.title("Kółko i Krzyżyk - Gra sieciowa")
        self.master.geometry("400x550")
        self.master.resizable(False, False)
        self.master.configure(bg="#2C3E50")
        self.menu_frame = tk.Frame(master, bg="#2C3E50")
        self.menu_frame.pack(fill=tk.BOTH, expand=True)

        # Dodajemy niestandardowe logo
        logo_canvas = tk.Canvas(self.menu_frame, width=200, height=150, bg="#2C3E50", highlightthickness=0)
        logo_canvas.pack(pady=10)
        self.draw_logo(logo_canvas)

        title = tk.Label(self.menu_frame, text="Kółko i Krzyżyk", font=("Helvetica", 28, "bold"),
                         bg="#2C3E50", fg="white")
        title.pack(pady=10)

        button_frame = tk.Frame(self.menu_frame, bg="#2C3E50")
        button_frame.pack(pady=20)

        host_button = tk.Button(button_frame, text="Hostuj grę", font=("Helvetica", 16, "bold"), width=15,
                                bg="#2980B9", fg="white", command=self.host_game)
        host_button.pack(pady=10)

        join_button = tk.Button(button_frame, text="Dołącz do gry", font=("Helvetica", 16, "bold"), width=15,
                                bg="#2980B9", fg="white", command=self.join_game)
        join_button.pack(pady=10)

        exit_button = tk.Button(button_frame, text="Wyjdź", font=("Helvetica", 16, "bold"), width=15,
                                bg="#2980B9", fg="white", command=self.master.quit)
        exit_button.pack(pady=10)

    def draw_logo(self, canvas):
        """Rysuje niestandardowe logo – stylizowaną siatkę z symbolami i efektem cienia."""
        canvas.delete("all")
        width = int(canvas['width'])
        height = int(canvas['height'])
        cell_size = width // 3
        # Rysujemy cień siatki
        for i in range(1, 3):
            canvas.create_line(0+2, i * cell_size+2, width+2, i * cell_size+2, width=2, fill="#7f8c8d")
            canvas.create_line(i * cell_size+2, 0+2, i * cell_size+2, height+2, width=2, fill="#7f8c8d")
        # Rysujemy główne linie siatki
        for i in range(1, 3):
            canvas.create_line(0, i * cell_size, width, i * cell_size, width=2, fill="#2980B9")
            canvas.create_line(i * cell_size, 0, i * cell_size, height, width=2, fill="#2980B9")
        # W top-left komórce rysujemy X
        margin = 10
        canvas.create_line(margin, margin, cell_size-margin, cell_size-margin, width=3, fill="#E74C3C")
        canvas.create_line(cell_size-margin, margin, margin, cell_size-margin, width=3, fill="#E74C3C")
        # W centralnej komórce rysujemy O
        x0 = cell_size + margin
        y0 = cell_size + margin
        x1 = 2*cell_size - margin
        y1 = 2*cell_size - margin
        canvas.create_oval(x0, y0, x1, y1, width=3, outline="#3498DB")
        # Dodajemy tytuł logo z efektem cienia
        canvas.create_text(width//2+2, height-10+2, text="Tic Tac Toe", font=("Helvetica", 16, "bold"), fill="#7f8c8d")
        canvas.create_text(width//2, height-10, text="Tic Tac Toe", font=("Helvetica", 16, "bold"), fill="white")

    def host_game(self):
        """Przechodzi do trybu hosta."""
        self.menu_frame.destroy()
        TicTacToeNetworkGame(self.master, is_host=True, on_game_end=self.show_menu)

    def join_game(self):
        """Wyświetla ekran z polami do wprowadzenia IP i portu hosta."""
        self.menu_frame.destroy()
        join_frame = tk.Frame(self.master, bg="#2C3E50")
        join_frame.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(join_frame, text="Dołącz do gry", font=("Helvetica", 24, "bold"),
                         bg="#2C3E50", fg="white")
        title.pack(pady=30)

        ip_label = tk.Label(join_frame, text="Host IP:", font=("Helvetica", 16), bg="#2C3E50", fg="white")
        ip_label.pack(pady=5)
        ip_entry = tk.Entry(join_frame, font=("Helvetica", 16))
        ip_entry.pack(pady=5)

        port_label = tk.Label(join_frame, text="Port:", font=("Helvetica", 16), bg="#2C3E50", fg="white")
        port_label.pack(pady=5)
        port_entry = tk.Entry(join_frame, font=("Helvetica", 16))
        port_entry.pack(pady=5)

        def connect():
            host_ip = ip_entry.get().strip()
            try:
                host_port = int(port_entry.get().strip())
            except ValueError:
                port_label.config(text="Błędny numer portu!")
                return
            join_frame.destroy()
            TicTacToeNetworkGame(self.master, is_host=False, host_ip=host_ip, host_port=host_port,
                                 on_game_end=self.show_menu)

        connect_button = tk.Button(join_frame, text="Dołącz", font=("Helvetica", 16, "bold"),
                                   bg="#2980B9", fg="white", command=connect)
        connect_button.pack(pady=20)

        back_button = tk.Button(join_frame, text="Powrót", font=("Helvetica", 16, "bold"),
                                bg="#2980B9", fg="white", command=lambda: self.back_to_menu(join_frame))
        back_button.pack(pady=10)

    def back_to_menu(self, frame):
        """Powrót do głównego menu."""
        frame.destroy()
        self.show_menu()

    def show_menu(self):
        """Odtwarza główne menu."""
        for widget in self.master.winfo_children():
            widget.destroy()
        MainMenu(self.master)


def main():
    root = tk.Tk()
    root.attributes('-topmost', True)
    MainMenu(root)
    root.mainloop()


if __name__ == "__main__":
    main()
