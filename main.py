import socket
import threading
import tkinter as tk
import random

PORT = 5000
BUFFER_SIZE = 1024


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


class TicTacToeNetworkGame:
    def __init__(self, master, is_host, host_ip=None, input_game_code=None, on_game_end=None):
        """
        Inicjalizacja gry sieciowej.

        :param master: główne okno
        :param is_host: True dla hosta, False dla klienta
        :param host_ip: adres IP hosta (dla klienta)
        :param input_game_code: kod gry podany przez klienta
        :param on_game_end: funkcja wywoływana po zakończeniu gry (powrót do menu)
        """
        self.master = master
        self.is_host = is_host
        self.host_ip = host_ip
        self.input_game_code = input_game_code
        self.on_game_end = on_game_end
        self.sock = None  # Socket klienta (dla klienta)
        self.conn = None  # Socket połączenia (dla hosta)
        self.game_code = None  # Czterocyfrowy kod gry
        self.my_mark = None  # Znak przypisany graczowi
        self.other_mark = None
        self.turn = None  # Aktualny ruch – wartość "X" lub "O" wskazująca, kto ma wykonać ruch
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.game_over = False
        self.reset_pending = False  # Flaga, czy reset został zainicjowany
        self.setup_ui()
        if self.is_host:
            self.start_server()
        else:
            self.connect_to_server()

    def setup_ui(self):
        """Tworzy interfejs gry – plansza (Canvas) i przyciski sterujące."""
        # Ramka gry z nowoczesnym ciemnym tłem
        self.game_frame = tk.Frame(self.master, bg="#2C3E50")
        self.game_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.status_label = tk.Label(self.game_frame, text="Inicjalizacja...", font=("Helvetica", 16, "bold"),
                                     bg="#2C3E50", fg="white")
        self.status_label.pack(pady=(0, 10))

        # Canvas – plansza o wymiarach 300x300 pikseli
        self.canvas = tk.Canvas(self.game_frame, width=300, height=300, bg="#ECF0F1", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.canvas_click)

        # Kontrola – przyciski reset i powrót do menu
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
        """Rysuje planszę – siatkę i umieszczone już znaki."""
        self.canvas.delete("all")
        cell_size = 100
        # Rysowanie linii siatki
        for i in range(1, 3):
            # Linia pozioma
            self.canvas.create_line(0, i * cell_size, 300, i * cell_size, width=3, fill="#2980B9")
            # Linia pionowa
            self.canvas.create_line(i * cell_size, 0, i * cell_size, 300, width=3, fill="#2980B9")

        # Rysowanie X i O
        for i in range(3):
            for j in range(3):
                mark = self.board[i][j]
                if mark != "":
                    x = j * cell_size + cell_size / 2
                    y = i * cell_size + cell_size / 2
                    if mark == "X":
                        color = "#E74C3C"
                    else:
                        color = "#3498DB"
                    self.canvas.create_text(x, y, text=mark, font=("Helvetica", 36, "bold"), fill=color)

    def canvas_click(self, event):
        """Obsługuje kliknięcia na planszy (Canvas)."""
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
        """Aktualizuje planszę po ruchu, rysuje planszę oraz sprawdza warunki zwycięstwa."""
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
        """
        Sprawdza, czy dany gracz wygrał.
        Zwraca krotkę (mark, typ, index) gdzie typ to:
         - "row" dla wiersza (index = numer wiersza),
         - "col" dla kolumny (index = numer kolumny),
         - "diag" dla głównej przekątnej,
         - "antidiag" dla przeciwnej przekątnej.
        Jeśli brak zwycięzcy, zwraca None.
        """
        # Wiersze
        for i in range(3):
            if all(self.board[i][j] == mark for j in range(3)):
                return (mark, "row", i)
        # Kolumny
        for j in range(3):
            if all(self.board[i][j] == mark for i in range(3)):
                return (mark, "col", j)
        # Główna przekątna
        if all(self.board[i][i] == mark for i in range(3)):
            return (mark, "diag", None)
        # Przeciwna przekątna
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
        """Czyści planszę, usuwa wygrywającą linię i przywraca stan początkowy."""
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.draw_board()
        self.canvas.delete("win_line")
        self.game_over = False

    def request_reset(self):
        """Inicjuje prośbę o reset – wysyła RESET_REQUEST i oczekuje na akceptację."""
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
        # Po resecie decydujemy losowo, kto zaczyna – tylko host losuje i wysyła informację
        if self.is_host:
            first_turn = random.choice(["X", "O"])
            self.turn = first_turn
            self.send_message("START|" + first_turn, connection=self.conn)
            turn_text = "Losowanie: zaczynasz ty!" if self.turn == self.my_mark else "Losowanie: przeciwnik zaczyna!"
            self.status_label.config(text=turn_text)
        # Jeśli klient, oczekujemy na komunikat START

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
        if parts[0] == "CODE":
            received_code = parts[1]
            if self.input_game_code != received_code:
                self.status_label.config(text="Kod gry nieprawidłowy. Rozłączanie.")
                self.sock.close()
                self.master.after(2000, self.exit_game)
            else:
                self.status_label.config(text="Kod gry prawidłowy.\nOczekiwanie na ruch przeciwnika.")
        elif parts[0] == "START":
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
        """Konfiguracja klienta – łączenie z hostem i weryfikacja kodu gry."""
        self.my_mark = "O"
        self.other_mark = "X"
        # Na początku zakładamy, że host losowo wybierze, kto zaczyna
        self.turn = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host_ip, PORT))
        except Exception as e:
            self.status_label.config(text=f"Błąd połączenia: {e}")
            return
        self.listen_thread = threading.Thread(target=self.receive_messages, args=(self.sock,), daemon=True)
        self.listen_thread.start()
        self.status_label.config(text="Połączono z hostem.\nOczekiwanie na weryfikację kodu gry...")

    def start_server(self):
        """Konfiguracja hosta – ustawia znaki, losowo wybiera, kto zaczyna, generuje kod gry i nasłuchuje połączenia."""
        self.my_mark = "X"
        self.other_mark = "O"
        # Losowo wybieramy, kto zaczyna
        first_turn = random.choice(["X", "O"])
        self.turn = first_turn
        self.game_code = str(random.randint(1000, 9999))
        local_ip = get_local_ip()
        self.status_label.config(
            text=f"Hostujesz grę.\nKod gry: {self.game_code}\nTwój IP: {local_ip}\nOczekiwanie na przeciwnika...")
        server_thread = threading.Thread(target=self.server_thread, daemon=True)
        server_thread.start()

    def server_thread(self):
        """Wątek serwera – nasłuchuje połączenia klienta, wysyła kod gry oraz informację START."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("", PORT))
        server_sock.listen(1)
        self.conn, addr = server_sock.accept()
        print("Połączono z:", addr)
        self.send_message(f"CODE|{self.game_code}", connection=self.conn)
        # Po wysłaniu kodu losujemy, kto zaczyna i wysyłamy START
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
        self.master.geometry("400x500")
        self.master.resizable(False, False)
        self.master.configure(bg="#2C3E50")
        self.menu_frame = tk.Frame(master, bg="#2C3E50")
        self.menu_frame.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(self.menu_frame, text="Kółko i Krzyżyk", font=("Helvetica", 28, "bold"),
                         bg="#2C3E50", fg="white")
        title.pack(pady=30)

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

    def host_game(self):
        """Przechodzi do trybu hosta."""
        self.menu_frame.destroy()
        TicTacToeNetworkGame(self.master, is_host=True, on_game_end=self.show_menu)

    def join_game(self):
        """Wyświetla ekran z polami do wprowadzenia adresu IP hosta i kodu gry."""
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

        code_label = tk.Label(join_frame, text="Kod gry:", font=("Helvetica", 16), bg="#2C3E50", fg="white")
        code_label.pack(pady=5)
        code_entry = tk.Entry(join_frame, font=("Helvetica", 16))
        code_entry.pack(pady=5)

        def connect():
            host_ip = ip_entry.get().strip()
            game_code = code_entry.get().strip()
            join_frame.destroy()
            TicTacToeNetworkGame(self.master, is_host=False, host_ip=host_ip, input_game_code=game_code,
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
