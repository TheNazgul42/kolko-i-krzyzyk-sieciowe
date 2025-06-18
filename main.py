import socket
import threading
import tkinter as tk
import random
import time
import math

BUFFER_SIZE = 1024
AVAILABLE_PLAYER_COLORS = ["#E74C3C", "#3498DB", "#2ECC71", "#F1C40F", "#9B59B6", "#E67E22", "#1ABC9C", "#FF69B4",
                           "#7D3C98"]
BUTTON_BG_COLOR = "#2980B9"
BUTTON_HOVER_BG_COLOR = "#3498DB"
BUTTON_ACTIVE_BG_COLOR = "#1F618D"
CELL_HOVER_COLOR = "#A9CCE3"


# Funkcje pomocnicze do rysowania gradientu
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return '#' + ''.join(f'{v:02x}' for v in rgb)


def interpolate_color(color1, color2, factor):
    r1, g1, b1 = hex_to_rgb(color1);
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 + (r2 - r1) * factor);
    g = int(g1 + (g2 - g1) * factor);
    b = int(b1 + (b2 - b1) * factor)
    return rgb_to_hex((r, g, b))


def draw_gradient(canvas, width, height, color1, color2):
    steps = height;
    for i in range(steps): factor = i / steps;color = interpolate_color(color1, color2, factor);canvas.create_line(0, i,
                                                                                                                   width,
                                                                                                                   i,
                                                                                                                   fill=color)


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_free_port():
    while True:
        port = random.randint(49152, 65535)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port)); return port
            except OSError:
                continue


class TicTacToeNetworkGame:
    def __init__(self, master, is_host, host_ip=None, host_port=None, on_game_end=None):
        self.master = master;
        self.is_host = is_host;
        self.host_ip = host_ip;
        self.host_port = host_port;
        self.on_game_end = on_game_end
        self.sock = None;
        self.conn = None;
        self.my_mark = None;
        self.other_mark = None;
        self.turn = None
        self.board = [["" for _ in range(3)] for _ in range(3)];
        self.game_over = False;
        self.reset_pending = False;
        self.port = None
        self.player_colors = {};
        self.fireworks_particles = [];
        self.fireworks_animation_id = None;
        self.fireworks_active = False
        self.winning_player_color = None;
        self.fireworks_duration = 5;
        self.fireworks_start_time = 0
        self.animated_objects = {}
        self.current_hover_cell = None
        self.debug_id = "Host" if self.is_host else "Client"
        print(f"[{self.debug_id}] Inicjalizacja TicTacToeNetworkGame.")
        self.setup_ui()
        if self.is_host:
            self.start_server()
        else:
            self.connect_to_server()

    def _setup_button_hover(self, button):
        button.bind("<Enter>", lambda e, b=button: b.config(bg=BUTTON_HOVER_BG_COLOR))
        button.bind("<Leave>",
                    lambda e, b=button: b.config(bg=BUTTON_BG_COLOR if b['state'] == tk.NORMAL else BUTTON_BG_COLOR))
        button.bind("<ButtonPress-1>", lambda e, b=button: b.config(bg=BUTTON_ACTIVE_BG_COLOR))
        button.bind("<ButtonRelease-1>", lambda e, b=button: b.config(
            bg=BUTTON_HOVER_BG_COLOR if b['state'] == tk.NORMAL else BUTTON_BG_COLOR))

    def setup_ui(self):
        print(f"[{self.debug_id}] setup_ui start.")
        self.game_frame = tk.Frame(self.master, bg="#2C3E50");
        self.game_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.status_label = tk.Label(self.game_frame, text="Inicjalizacja...", font=("Helvetica", 16, "bold"),
                                     bg="#2C3E50", fg="white");
        self.status_label.pack(pady=(0, 10))
        self.canvas = tk.Canvas(self.game_frame, width=300, height=300, highlightthickness=0);
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.canvas_click);
        self.canvas.bind("<Motion>", self.canvas_hover);
        self.canvas.bind("<Leave>", self.canvas_leave)
        control_frame = tk.Frame(self.game_frame, bg="#2C3E50");
        control_frame.pack(pady=10)
        self.reset_button = tk.Button(control_frame, text="Reset gry", font=("Helvetica", 14, "bold"),
                                      bg=BUTTON_BG_COLOR, fg="white", activebackground=BUTTON_ACTIVE_BG_COLOR,
                                      relief=tk.RAISED, command=self.request_reset)
        self.reset_button.grid(row=0, column=0, padx=10);
        self._setup_button_hover(self.reset_button)
        self.exit_button = tk.Button(control_frame, text="Wyjdź do menu", font=("Helvetica", 14, "bold"),
                                     bg=BUTTON_BG_COLOR, fg="white", activebackground=BUTTON_ACTIVE_BG_COLOR,
                                     relief=tk.RAISED, command=self.exit_game)
        self.exit_button.grid(row=0, column=1, padx=10);
        self._setup_button_hover(self.exit_button)
        self.draw_board_static()
        print(f"[{self.debug_id}] setup_ui koniec.")

    def canvas_hover(self, event):
        if self.game_over or not self.player_colors: self.canvas.delete("hover_highlight"); return
        cell_size = 100;
        col, row = event.x // cell_size, event.y // cell_size
        self.canvas.delete("hover_highlight")
        if 0 <= row <= 2 and 0 <= col <= 2 and self.board[row][col] == "" and self.turn == self.my_mark:
            x0, y0, x1, y1 = col * cell_size, row * cell_size, col * cell_size + cell_size, row * cell_size + cell_size
            self.canvas.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, outline=CELL_HOVER_COLOR, width=2,
                                         tags="hover_highlight")
            self.current_hover_cell = (row, col)
        else:
            self.current_hover_cell = None

    def canvas_leave(self, event):
        self.canvas.delete("hover_highlight"); self.current_hover_cell = None

    def draw_board_static(self):
        self.canvas.delete("grid_lines")
        width, height = 300, 300;
        draw_gradient(self.canvas, width, height, "#D7DDE8", "#F7F9FC")
        cell_size = 100
        for i in range(1, 3): self.canvas.create_line(3, i * cell_size + 3, width + 3, i * cell_size + 3, width=3,
                                                      fill="#7f8c8d", tags="grid_lines"); self.canvas.create_line(
            i * cell_size + 3, 3, i * cell_size + 3, height + 3, width=3, fill="#7f8c8d", tags="grid_lines")
        for i in range(1, 3): self.canvas.create_line(0, i * cell_size, width, i * cell_size, width=3, fill="#2980B9",
                                                      tags="grid_lines"); self.canvas.create_line(i * cell_size, 0,
                                                                                                  i * cell_size, height,
                                                                                                  width=3,
                                                                                                  fill="#2980B9",
                                                                                                  tags="grid_lines")
        for r_idx, row_val in enumerate(self.board):
            for c_idx, mark in enumerate(row_val):
                if mark and self.player_colors: self._draw_mark_at_scale(r_idx, c_idx, mark,
                                                                         self.player_colors.get(mark, "#000000"), 1.0,
                                                                         f"mark_{r_idx}_{c_idx}")

    def _draw_mark_at_scale(self, r_idx, c_idx, mark_char, color, scale, tag):
        self.canvas.delete(tag)
        cell_size = 100;
        center_x, center_y = c_idx * cell_size + cell_size / 2, r_idx * cell_size + cell_size / 2
        size = (cell_size / 2 - 20) * scale
        if mark_char == "X":
            self.canvas.create_line(center_x - size + 2, center_y - size + 2, center_x + size + 2, center_y + size + 2,
                                    width=4, fill="#7f8c8d", tags=tag)
            self.canvas.create_line(center_x + size + 2, center_y - size + 2, center_x - size + 2, center_y + size + 2,
                                    width=4, fill="#7f8c8d", tags=tag)
            self.canvas.create_line(center_x - size, center_y - size, center_x + size, center_y + size, width=4,
                                    fill=color, tags=tag)
            self.canvas.create_line(center_x + size, center_y - size, center_x - size, center_y + size, width=4,
                                    fill=color, tags=tag)
        elif mark_char == "O":
            self.canvas.create_oval(center_x - size + 2, center_y - size + 2, center_x + size + 2, center_y + size + 2,
                                    width=4, outline="#7f8c8d", tags=tag)
            self.canvas.create_oval(center_x - size, center_y - size, center_x + size, center_y + size, width=4,
                                    outline=color, tags=tag)

    def _animate_mark_placement(self, r_idx, c_idx, mark_char, color, current_step=0, max_steps=10, delay=20):
        tag = f"mark_{r_idx}_{c_idx}"
        if current_step > max_steps: self._draw_mark_at_scale(r_idx, c_idx, mark_char, color, 1.0,
                                                              tag); self.animated_objects.pop(tag, None); return
        scale = current_step / max_steps;
        self._draw_mark_at_scale(r_idx, c_idx, mark_char, color, scale, tag)
        anim_id = self.master.after(delay, self._animate_mark_placement, r_idx, c_idx, mark_char, color,
                                    current_step + 1, max_steps, delay)
        self.animated_objects[tag] = anim_id

    def canvas_click(self, event):
        if self.game_over or not self.player_colors: return
        cell_size = 100;
        col, row = event.x // cell_size, event.y // cell_size
        if not (0 <= row <= 2 and 0 <= col <= 2) or self.board[row][col] != "": return
        if self.turn != self.my_mark: self.status_label.config(text="Nie twój ruch!"); return
        tag = f"mark_{row}_{col}"
        if tag in self.animated_objects: self.master.after_cancel(
            self.animated_objects[tag]); self.animated_objects.pop(tag)
        self.board[row][col] = self.my_mark
        self._animate_mark_placement(row, col, self.my_mark, self.player_colors.get(self.my_mark, "#000000"))
        self._check_game_state_after_move(self.my_mark)
        if not self.game_over: self.send_message(f"MOVE|{row}|{col}")

    def make_move(self, r, c, mark):
        if self.board[r][c] == "" and not self.game_over:
            self.board[r][c] = mark
            self._animate_mark_placement(r, c, mark, self.player_colors.get(mark, "#000000"))
            self._check_game_state_after_move(mark)

    def _check_game_state_after_move(self, mark_just_placed):
        winner_info = self.get_winner_info(mark_just_placed)
        if winner_info:
            self.game_over = True;
            winner_mark, winner_color = winner_info[0], self.player_colors.get(winner_info[0], "#27AE60")
            if self.my_mark == winner_mark:  # Wygrałem
                self.status_label.config(text=f"🎉 TY WYGRAŁEŚ/AŚ! 🎉", font=("Helvetica", 20, "bold"), fg=winner_color)
                self.animate_winning_line(winner_info, winner_color);
                self.trigger_victory_celebration(winner_color)
                self.send_message(f"YOU_LOST|{winner_mark}")
                print(f"[{self.debug_id}] Wygrałem. Wysyłam YOU_LOST.")
            else:  # Przegrałem (przeciwnik wykonał zwycięski ruch, który właśnie przetworzyłem)
                print(
                    f"[{self.debug_id}] Przeciwnik ({winner_mark}) wygrał. Rysuję jego linię. Moja etykieta zostanie zaktualizowana przez YOU_LOST.")
                self.animate_winning_line(winner_info, winner_color)  # Rysuj linię zwycięzcy na mojej planszy
                # Komunikat o przegranej i efekt porażki zostaną obsłużone przez process_message("YOU_LOST")
        elif self.is_board_full():
            self.game_over = True;
            self.status_label.config(text="REMIS!", font=("Helvetica", 18, "bold"))
            if mark_just_placed == self.my_mark: self.send_message(
                "DRAW")  # Tylko gracz wykonujący ruch wysyła info o remisie
            print(f"[{self.debug_id}] Remis.")
        else:  # Gra kontynuuje
            self.game_over = False
            self.turn = self.other_mark if mark_just_placed == self.my_mark else self.my_mark
            turn_text = "Twój ruch" if self.turn == self.my_mark else "Ruch przeciwnika"
            self.status_label.config(text=turn_text, font=("Helvetica", 16, "bold"), fg="white")
            print(f"[{self.debug_id}] Gra kontynuowana. Tura dla: {self.turn}.")

    def get_winner_info(self, mark):
        for i in range(3):
            if all(self.board[i][j] == mark for j in range(3)): return (mark, "row", i)
            if all(self.board[j][i] == mark for j in range(3)): return (mark, "col", i)
        if all(self.board[i][i] == mark for i in range(3)): return (mark, "diag", None)
        if all(self.board[i][2 - i] == mark for i in range(3)): return (mark, "antidiag", None)
        return None

    def animate_winning_line(self, winner_info, color="#27AE60", steps=20, delay=15):
        self.canvas.delete("win_line_segment")
        cell_size = 100;
        _, win_type, index = winner_info;
        padding = 10
        if win_type == "row":
            y_coord = index * cell_size + cell_size / 2; x_start, y_start, x_end, y_end = padding, y_coord, 300 - padding, y_coord
        elif win_type == "col":
            x_coord = index * cell_size + cell_size / 2; x_start, y_start, x_end, y_end = x_coord, padding, x_coord, 300 - padding
        elif win_type == "diag":
            x_start, y_start, x_end, y_end = padding, padding, 300 - padding, 300 - padding
        else:
            x_start, y_start, x_end, y_end = 300 - padding, padding, padding, 300 - padding
        dx = (x_end - x_start) / steps;
        dy = (y_end - y_start) / steps

        def _draw_segment(current_step):
            if current_step > steps: return
            curr_x, curr_y = x_start + dx * current_step, y_start + dy * current_step
            prev_x, prev_y = x_start + dx * (current_step - 1), y_start + dy * (current_step - 1)
            if current_step > 0: self.canvas.create_line(prev_x, prev_y, curr_x, curr_y, width=5, fill=color,
                                                         tags="win_line_segment")
            self.master.after(delay, _draw_segment, current_step + 1)

        _draw_segment(1)

    def _show_defeat_effect(self):
        if hasattr(self, 'canvas') and self.canvas.winfo_exists():
            self.canvas.delete("defeat_text_overlay")
            self.canvas.create_text(150 + 2, 150 + 2, text="PRZEGRANA", font=("Helvetica", 30, "bold"), fill="#A04040",
                                    tags="defeat_text_overlay", anchor=tk.CENTER)  # Cień
            self.canvas.create_text(150, 150, text="PRZEGRANA", font=("Helvetica", 30, "bold"), fill="#E74C3C",
                                    tags="defeat_text_overlay", anchor=tk.CENTER)  # Główny tekst
            self.canvas.tag_raise("defeat_text_overlay")
            print(f"[{self.debug_id}] Efekt porażki (tekst) zastosowany.")

    def is_board_full(self):
        return all(self.board[i][j] != "" for i in range(3) for j in range(3))

    def reset_board(self):
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.canvas.delete("win_line_segment");
        self.canvas.delete("hover_highlight");
        self.canvas.delete("defeat_text_overlay")
        for r in range(3):
            for c in range(3): self.canvas.delete(f"mark_{r}_{c}"); self.animated_objects.pop(f"mark_{r}_{c}", None)
        self.draw_board_static();
        self.game_over = False;
        self.stop_fireworks_display()

    def request_reset(self):
        if self.reset_pending: return
        self.reset_pending = True;
        self.status_label.config(text="Wysłano prośbę o reset...", fg="white");
        self.reset_button.config(state=tk.DISABLED, bg=BUTTON_BG_COLOR)
        self.send_message("RESET_REQUEST", connection=self.conn if self.is_host else None)

    def ask_reset_confirmation(self):
        dialog = tk.Toplevel(self.master);
        dialog.title("Reset gry");
        dialog.configure(bg="#2C3E50");
        dialog.geometry("300x150");
        dialog.resizable(False, False)
        tk.Label(dialog, text="Przeciwnik prosi o reset gry.\nCzy akceptujesz?", font=("Helvetica", 14), bg="#2C3E50",
                 fg="white").pack(pady=10, padx=10)

        def accept(): dialog.destroy();self.send_message("RESET_ACCEPT",
                                                         connection=self.conn if self.is_host else None);self.perform_reset()

        def reject(): dialog.destroy();self.send_message("RESET_REJECT",
                                                         connection=self.conn if self.is_host else None);self.reset_pending = False;self.status_label.config(
            text="Reset anulowany.", fg="white");self.reset_button.config(state=tk.NORMAL, bg=BUTTON_BG_COLOR)

        btn_frame = tk.Frame(dialog, bg="#2C3E50");
        btn_frame.pack(pady=10)
        accept_btn = tk.Button(btn_frame, text="Tak", font=("Helvetica", 12, "bold"), bg="#27AE60", fg="white",
                               activebackground="#229954", command=accept);
        accept_btn.pack(side=tk.LEFT, padx=5);
        self._setup_button_hover(accept_btn)
        reject_btn = tk.Button(btn_frame, text="Nie", font=("Helvetica", 12, "bold"), bg="#C0392B", fg="white",
                               activebackground="#A93226", command=reject);
        reject_btn.pack(side=tk.LEFT, padx=5);
        self._setup_button_hover(reject_btn)
        dialog.transient(self.master);
        dialog.grab_set();
        self.master.wait_window(dialog)

    def perform_reset(self):
        self.reset_board();
        self.reset_pending = False;
        self.reset_button.config(state=tk.NORMAL, bg=BUTTON_BG_COLOR)
        if self.is_host:
            self.assign_colors_and_turn()
        else:
            self.status_label.config(text="Oczekiwanie na hosta...", fg="white")

    def send_message(self, message, connection=None):
        sock_to_use = self.conn if self.is_host else self.sock
        if connection is not None: sock_to_use = connection
        role = self.debug_id;
        target_info = "N/A"
        if sock_to_use:
            try:
                target_info = str(sock_to_use.getpeername())
            except:
                pass  # Błędy są możliwe jeśli socket jest już zamknięty
        print(f"[{role} SENDING] Do: {target_info}, Wiadomość: '{message}'")
        if sock_to_use:
            try:
                sock_to_use.sendall((message + "\n").encode()); print(f"[{role} SENT OK] '{message}'")
            except Exception as e:
                print(f"[{role} SEND FAIL] '{message}' do {target_info}: {e}")
        else:
            print(f"[{role} SEND FAIL] Brak socketa dla '{message}'")

    def receive_messages(self, sock):
        buffer = "";
        role = self.debug_id
        print(f"[{role} RECV THREAD STARTED] Socket: {sock.getsockname() if hasattr(sock, 'getsockname') else 'N/A'}")
        while True:
            try:
                data = sock.recv(BUFFER_SIZE)
            except socket.timeout:
                print(f"[{role} RECV TIMEOUT]"); continue
            except Exception as e:
                print(f"[{role} RECV ERROR]: {e}"); break
            if not data: print(f"[{role} RECV] Połączenie zamknięte."); break
            buffer += data.decode('utf-8', 'ignore');
            print(f"[{role} RECV BUFFER]: '{buffer}'")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1);
                line_to_process = line.strip()
                print(f"[{role} RECV PROC LINE]: '{line_to_process}'")
                self.master.after(0, self.process_message, line_to_process)
        print(f"[{role} RECV THREAD ENDED]")
        if hasattr(self, 'game_frame') and self.game_frame.winfo_exists(): self.master.after(100, self.exit_game)

    def process_message(self, message):
        role = self.debug_id;
        print(f"[{role} PROCESSING MSG] Wiadomość: '{message}'")
        parts = message.split("|");
        cmd = parts[0]
        if cmd == "START":
            self.turn = parts[1];
            self.player_colors['X'] = parts[2];
            self.player_colors['O'] = parts[3]
            self.reset_board()
            turn_text = "Twój ruch" if self.turn == self.my_mark else "Ruch przeciwnika"
            self.status_label.config(text=turn_text, font=("Helvetica", 16, "bold"), fg="white")
            print(f"[{role} PROC START] Tura: {self.turn}. Kolory: X={parts[2]}, O={parts[3]}.")
        elif cmd == "MOVE":
            try:
                r, c = int(parts[1]), int(parts[2]); self.make_move(r, c, self.other_mark)
            except (ValueError, IndexError) as e:
                print(f"[{role} PROC MOVE ERR]: {message}, {e}"); return
        elif cmd == "YOU_LOST":
            winner_mark = parts[1] if len(parts) > 1 else "Przeciwnik"
            self.status_label.config(text=f"PRZEGRAŁEŚ/AŚ! Wygrał: {winner_mark}", font=("Helvetica", 18, "bold"),
                                     fg="#E74C3C")
            self.game_over = True;
            self._show_defeat_effect()
            print(f"[{role} PROC YOU_LOST] Przegrana. Wygrał: {winner_mark}.")
        elif cmd == "DRAW":
            self.status_label.config(text="REMIS!", font=("Helvetica", 18, "bold"), fg="white");
            self.game_over = True
            print(f"[{role} PROC DRAW] Remis.")
        elif cmd == "RESET_REQUEST":
            if not self.reset_pending:
                self.reset_pending = True; self.ask_reset_confirmation()
            else:
                self.send_message("RESET_ACCEPT", connection=self.conn if self.is_host else None); self.perform_reset()
        elif cmd == "RESET_ACCEPT":
            _ = self.perform_reset() if self.reset_pending else None
        elif cmd == "RESET_REJECT":
            self.reset_pending = False;self.status_label.config(text="Reset odrzucony.",
                                                                fg="white");self.reset_button.config(state=tk.NORMAL,
                                                                                                     bg=BUTTON_BG_COLOR)
        else:
            print(f"[{role} PROC UNKNOWN CMD]: '{cmd}' w '{message}'")

    def connect_to_server(self):
        print(f"[{self.debug_id}] connect_to_server: IP={self.host_ip}, Port={self.host_port}")
        self.my_mark, self.other_mark = "O", "X";
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host_ip, self.host_port));
            self.sock.settimeout(5.0)
            print(f"[{self.debug_id}] Połączono z serwerem. Lokalny socket: {self.sock.getsockname()}")
            self.status_label.config(text="Połączono. Oczekiwanie na start...", fg="white")
            threading.Thread(target=self.receive_messages, args=(self.sock,), daemon=True,
                             name=f"{self.debug_id}ReceiveThread").start()
        except Exception as e:
            print(f"[{self.debug_id}] Błąd połączenia: {e}"); self.status_label.config(text=f"Błąd połączenia: {e}",
                                                                                       fg="red");self.master.after(2000,
                                                                                                                   self.exit_game)

    def assign_colors_and_turn(self):
        print(f"[{self.debug_id}] assign_colors_and_turn.")
        color_x = random.choice(AVAILABLE_PLAYER_COLORS);
        available_colors_for_o = [c for c in AVAILABLE_PLAYER_COLORS if c != color_x];
        color_o = random.choice(available_colors_for_o) if available_colors_for_o else "#17A589"
        self.player_colors['X'], self.player_colors['O'] = color_x, color_o;
        first_turn = random.choice(["X", "O"]);
        self.turn = first_turn
        self.reset_board()
        print(f"[{self.debug_id}] Wylosowano: Tura={self.turn}, Kolor X={color_x}, Kolor O={color_o}")
        if self.conn:
            self.send_message(f"START|{self.turn}|{color_x}|{color_o}", connection=self.conn)
            turn_text = "Losowanie: Zaczynasz!" if self.turn == self.my_mark else "Losowanie: Przeciwnik zaczyna."
            self.status_label.config(text=turn_text, font=("Helvetica", 16, "bold"), fg="white")
        else:
            print(f"[{self.debug_id}] assign_colors_and_turn: self.conn jest None.")

    def start_server(self):
        print(f"[{self.debug_id}] start_server.")
        self.my_mark, self.other_mark = "X", "O";
        self.port = get_free_port();
        local_ip = get_local_ip()
        self.status_label.config(text=f"Hostujesz grę.\nIP: {local_ip} Port: {self.port}\nOczekiwanie...",
                                 font=("Helvetica", 14), fg="white")
        print(f"[{self.debug_id}] Serwer startuje na IP: {local_ip}, Port: {self.port}")
        threading.Thread(target=self.server_thread, daemon=True, name=f"{self.debug_id}ServerThread").start()

    def server_thread(self):
        print(f"[{self.debug_id} SERVER THREAD] Start.")
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind(("", self.port))
        except Exception as e:
            print(f"[{self.debug_id} SERVER THREAD] Błąd bindowania portu {self.port}: {e}");self.status_label.config(
                text=f"Błąd portu: {e}", fg="red");return
        server_sock.listen(1);
        print(f"[{self.debug_id} SERVER THREAD] Nasłuch na porcie {self.port}")
        try:
            self.conn, addr = server_sock.accept();
            self.conn.settimeout(5.0)
            print(f"[{self.debug_id} SERVER THREAD] Połączono z: {addr}. self.conn={self.conn}")
            self.assign_colors_and_turn()
            threading.Thread(target=self.receive_messages, args=(self.conn,), daemon=True,
                             name=f"{self.debug_id}HostReceiveThread").start()
        except Exception as e:
            print(f"[{self.debug_id} SERVER THREAD] Błąd akceptacji: {e}");self.status_label.config(
                text=f"Błąd połączenia: {e}", fg="red")
        finally:
            print(f"[{self.debug_id} SERVER THREAD] Zamykanie socketa serwera."); server_sock.close()

    def trigger_victory_celebration(self, winner_color):
        self.winning_player_color = winner_color;self.fireworks_active = True;self.fireworks_start_time = time.time();self.fireworks_particles.clear();self.canvas.delete(
            "firework");_ = self.master.after_cancel(
            self.fireworks_animation_id) if self.fireworks_animation_id else None;self._animate_fireworks()

    def _animate_fireworks(self):
        if not self.fireworks_active or (
                time.time() - self.fireworks_start_time > self.fireworks_duration): self.stop_fireworks_display(); return
        if random.random() < 0.15: bx, by = random.randint(50, 250), random.randint(50,
                                                                                    150);self._create_firework_burst(bx,
                                                                                                                     by,
                                                                                                                     self.winning_player_color)
        self.canvas.delete("firework");
        new_particles = []
        for p in self.fireworks_particles:
            p['x'] += p['vx'];
            p['y'] += p['vy'];
            p['vy'] += 0.1;
            p['life'] -= random.uniform(0.5, 1.5)
            if p['life'] > 0: new_particles.append(p);size = p['size'] * (
                        p['life'] / p['max_life']);self.canvas.create_oval(p['x'] - size, p['y'] - size, p['x'] + size,
                                                                           p['y'] + size, fill=p['color'],
                                                                           outline=p['color'], tags="firework")
        self.fireworks_particles = new_particles;
        self.fireworks_animation_id = self.master.after(40, self._animate_fireworks)

    def _create_firework_burst(self, x, y, base_color):
        num_particles = random.randint(30, 50)
        for _ in range(num_particles): angle = random.uniform(0, 2 * math.pi);speed = random.uniform(1,
                                                                                                     5);life = random.randint(
            25, 50);self.fireworks_particles.append(
            {'x': x, 'y': y, 'vx': math.cos(angle) * speed, 'vy': math.sin(angle) * speed, 'color': base_color,
             'size': random.randint(2, 5), 'life': life, 'max_life': life})

    def stop_fireworks_display(self):
        self.fireworks_active = False;_ = self.master.after_cancel(
            self.fireworks_animation_id) if self.fireworks_animation_id else None;self.fireworks_animation_id = None;self.fireworks_particles.clear();self.canvas.delete(
            "firework")

    def exit_game(self):
        print(f"[{self.debug_id}] exit_game: Zamykanie.")
        self.stop_fireworks_display()
        for anim_id in list(self.animated_objects.values()): self.master.after_cancel(
            anim_id)  # Użyj list() do iteracji po kopii
        self.animated_objects.clear()
        try:
            if self.is_host and self.conn: print(
                f"[{self.debug_id}] Zamykanie self.conn."); self.conn.close(); self.conn = None
            if not self.is_host and self.sock: print(
                f"[{self.debug_id}] Zamykanie self.sock."); self.sock.close(); self.sock = None
        except Exception as e:
            print(f"[{self.debug_id}] Błąd zamykania socketu w exit_game: {e}")
        if hasattr(self, 'game_frame') and self.game_frame.winfo_exists(): self.game_frame.destroy()
        if self.on_game_end: self.on_game_end()


class MainMenu:
    def __init__(self, master):
        self.master = master;
        self.master.title("Kółko i Krzyżyk - Gra sieciowa");
        self.master.geometry("400x550");
        self.master.resizable(False, False);
        self.master.configure(bg="#2C3E50")
        self.menu_frame = tk.Frame(master, bg="#2C3E50");
        self.menu_frame.pack(fill=tk.BOTH, expand=True)
        logo_canvas = tk.Canvas(self.menu_frame, width=200, height=150, bg="#2C3E50", highlightthickness=0);
        logo_canvas.pack(pady=10);
        self.draw_logo(logo_canvas)
        tk.Label(self.menu_frame, text="Kółko i Krzyżyk", font=("Helvetica", 28, "bold"), bg="#2C3E50",
                 fg="white").pack(pady=10)
        button_frame = tk.Frame(self.menu_frame, bg="#2C3E50");
        button_frame.pack(pady=20)
        self.host_button = tk.Button(button_frame, text="Hostuj grę", font=("Helvetica", 16, "bold"), width=15,
                                     bg=BUTTON_BG_COLOR, fg="white", activebackground=BUTTON_ACTIVE_BG_COLOR,
                                     relief=tk.RAISED, command=self.host_game);
        self.host_button.pack(pady=10);
        self._setup_button_hover(self.host_button)
        self.join_button = tk.Button(button_frame, text="Dołącz do gry", font=("Helvetica", 16, "bold"), width=15,
                                     bg=BUTTON_BG_COLOR, fg="white", activebackground=BUTTON_ACTIVE_BG_COLOR,
                                     relief=tk.RAISED, command=self.join_game);
        self.join_button.pack(pady=10);
        self._setup_button_hover(self.join_button)
        self.exit_button = tk.Button(button_frame, text="Wyjdź", font=("Helvetica", 16, "bold"), width=15,
                                     bg=BUTTON_BG_COLOR, fg="white", activebackground=BUTTON_ACTIVE_BG_COLOR,
                                     relief=tk.RAISED, command=self.master.quit);
        self.exit_button.pack(pady=10);
        self._setup_button_hover(self.exit_button)

    def _setup_button_hover(self, button):
        button.bind("<Enter>", lambda e, b=button: b.config(bg=BUTTON_HOVER_BG_COLOR))
        button.bind("<Leave>", lambda e, b=button: b.config(bg=BUTTON_BG_COLOR))
        button.bind("<ButtonPress-1>", lambda e, b=button: b.config(bg=BUTTON_ACTIVE_BG_COLOR))
        button.bind("<ButtonRelease-1>", lambda e, b=button: b.config(bg=BUTTON_HOVER_BG_COLOR))

    def draw_logo(self, canvas):
        canvas.delete("all");
        width, height = int(canvas['width']), int(canvas['height']);
        cell_size = width // 3
        for i in range(1, 3): canvas.create_line(2, i * cell_size + 2, width + 2, i * cell_size + 2, width=2,
                                                 fill="#7f8c8d");canvas.create_line(i * cell_size + 2, 2,
                                                                                    i * cell_size + 2, height + 2,
                                                                                    width=2, fill="#7f8c8d")
        for i in range(1, 3): canvas.create_line(0, i * cell_size, width, i * cell_size, width=2,
                                                 fill="#2980B9");canvas.create_line(i * cell_size, 0, i * cell_size,
                                                                                    height, width=2, fill="#2980B9")
        margin = 10;
        canvas.create_line(margin, margin, cell_size - margin, cell_size - margin, width=3, fill="#E74C3C");
        canvas.create_line(cell_size - margin, margin, margin, cell_size - margin, width=3, fill="#E74C3C")
        x0, y0, x1, y1 = cell_size + margin, cell_size + margin, 2 * cell_size - margin, 2 * cell_size - margin;
        canvas.create_oval(x0, y0, x1, y1, width=3, outline="#3498DB")
        canvas.create_text(width // 2 + 2, height - 10 + 2, text="Tic Tac Toe", font=("Helvetica", 16, "bold"),
                           fill="#7f8c8d");
        canvas.create_text(width // 2, height - 10, text="Tic Tac Toe", font=("Helvetica", 16, "bold"), fill="white")

    def host_game(self):
        self.menu_frame.destroy();TicTacToeNetworkGame(self.master, is_host=True, on_game_end=self.show_menu)

    def join_game(self):
        self.menu_frame.destroy();
        join_frame = tk.Frame(self.master, bg="#2C3E50");
        join_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(join_frame, text="Dołącz do gry", font=("Helvetica", 24, "bold"), bg="#2C3E50", fg="white").pack(
            pady=30)
        tk.Label(join_frame, text="Host IP:", font=("Helvetica", 16), bg="#2C3E50", fg="white").pack(pady=5);
        ip_entry = tk.Entry(join_frame, font=("Helvetica", 16), width=20, justify='center');
        ip_entry.pack(pady=5)  # Usunięto .insert(0, "127.0.0.1")
        tk.Label(join_frame, text="Port:", font=("Helvetica", 16), bg="#2C3E50", fg="white").pack(pady=5);
        port_entry = tk.Entry(join_frame, font=("Helvetica", 16), width=10, justify='center');
        port_entry.pack(pady=5)
        status_join_label = tk.Label(join_frame, text="", font=("Helvetica", 12), bg="#2C3E50", fg="red");
        status_join_label.pack(pady=5)

        def connect_action():
            host_ip, port_str = ip_entry.get().strip(), port_entry.get().strip()
            if not host_ip or not port_str: status_join_label.config(text="IP i Port nie mogą być puste!");return
            try:
                host_port = int(port_str);assert 1024 <= host_port <= 65535
            except(ValueError, AssertionError):
                status_join_label.config(text="Błędny port (1024-65535)!");return
            print(f"[MainMenu] Próba połączenia jako klient do {host_ip}:{host_port}")
            join_frame.destroy();
            TicTacToeNetworkGame(self.master, is_host=False, host_ip=host_ip, host_port=host_port,
                                 on_game_end=self.show_menu)

        connect_button = tk.Button(join_frame, text="Dołącz", font=("Helvetica", 16, "bold"), bg=BUTTON_BG_COLOR,
                                   fg="white", activebackground=BUTTON_ACTIVE_BG_COLOR, relief=tk.RAISED,
                                   command=connect_action);
        connect_button.pack(pady=20);
        self._setup_button_hover(connect_button)
        back_button = tk.Button(join_frame, text="Powrót", font=("Helvetica", 16, "bold"), bg=BUTTON_BG_COLOR,
                                fg="white", activebackground=BUTTON_ACTIVE_BG_COLOR, relief=tk.RAISED,
                                command=lambda: self.back_to_menu(join_frame));
        back_button.pack(pady=10);
        self._setup_button_hover(back_button)

    def back_to_menu(self, frame):
        frame.destroy();self.show_menu()

    def show_menu(self):
        print("[MainMenu] Pokazywanie menu głównego.")
        for widget in self.master.winfo_children(): widget.destroy()
        MainMenu(self.master)


def main():
    print("Uruchamianie aplikacji Kółko i Krzyżyk.")
    root = tk.Tk()
    MainMenu(root)
    root.mainloop()
    print("Zamykanie aplikacji Kółko i Krzyżyk.")


if __name__ == "__main__":
    main()
