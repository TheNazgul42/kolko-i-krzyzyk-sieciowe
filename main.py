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
CELL_HOVER_COLOR = "#A9CCE3"  # Kolor podświetlenia komórki


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
        self.animated_objects = {}  # Do śledzenia animacji znaków
        self.current_hover_cell = None  # Do podświetlania komórek

        self.setup_ui()
        if self.is_host:
            self.start_server()
        else:
            self.connect_to_server()

    def setup_ui(self):
        self.game_frame = tk.Frame(self.master, bg="#2C3E50");
        self.game_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.status_label = tk.Label(self.game_frame, text="Inicjalizacja...", font=("Helvetica", 16, "bold"),
                                     bg="#2C3E50", fg="white");
        self.status_label.pack(pady=(0, 10))
        self.canvas = tk.Canvas(self.game_frame, width=300, height=300, highlightthickness=0);
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Motion>", self.canvas_hover)  # Do podświetlania komórek
        self.canvas.bind("<Leave>", self.canvas_leave)  # Do usunięcia podświetlenia

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
        self.draw_board_static()  # Rysuje tylko statyczną planszę na początku

    def _setup_button_hover(self, button):
        button.bind("<Enter>", lambda e, b=button: b.config(bg=BUTTON_HOVER_BG_COLOR))
        button.bind("<Leave>", lambda e, b=button: b.config(bg=BUTTON_BG_COLOR if b[
                                                                                      'state'] == tk.NORMAL else BUTTON_BG_COLOR))  # Powrót do normalnego lub szarego jeśli disabled
        button.bind("<ButtonPress-1>", lambda e, b=button: b.config(bg=BUTTON_ACTIVE_BG_COLOR))
        button.bind("<ButtonRelease-1>", lambda e, b=button: b.config(bg=BUTTON_HOVER_BG_COLOR))

    def canvas_hover(self, event):
        if self.game_over or not self.player_colors: return
        cell_size = 100;
        col, row = event.x // cell_size, event.y // cell_size

        # Usuń poprzednie podświetlenie, jeśli istnieje
        self.canvas.delete("hover_highlight")

        if 0 <= row <= 2 and 0 <= col <= 2 and self.board[row][col] == "" and self.turn == self.my_mark:
            x0, y0 = col * cell_size, row * cell_size
            x1, y1 = x0 + cell_size, y0 + cell_size
            # Rysuj podświetlenie - półprzezroczysty prostokąt lub obramowanie
            # Dla prostoty, użyjemy obramowania, bo gradient tła komplikuje półprzezroczystość
            self.canvas.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, outline=CELL_HOVER_COLOR, width=2,
                                         tags="hover_highlight")
            self.current_hover_cell = (row, col)
        else:
            self.current_hover_cell = None

    def canvas_leave(self, event):
        self.canvas.delete("hover_highlight")
        self.current_hover_cell = None

    def draw_board_static(self):  # Rysuje siatkę i gradient
        self.canvas.delete("grid_lines")  # Usuwamy tylko linie, nie wszystko
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
        # Przerysowanie istniejących znaków bez animacji (np. po resecie lub inicjalizacji)
        for r_idx, row_val in enumerate(self.board):
            for c_idx, mark in enumerate(row_val):
                if mark and self.player_colors:
                    self._draw_mark_at_scale(r_idx, c_idx, mark, self.player_colors.get(mark, "#000000"), 1.0,
                                             f"mark_{r_idx}_{c_idx}")

    def _draw_mark_at_scale(self, r_idx, c_idx, mark_char, color, scale, tag):
        self.canvas.delete(tag)  # Usuń poprzednią klatkę tego znaku
        cell_size = 100
        center_x, center_y = c_idx * cell_size + cell_size / 2, r_idx * cell_size + cell_size / 2
        size = (cell_size / 2 - 20) * scale  # 20 to margines

        if mark_char == "X":
            # Cień
            self.canvas.create_line(center_x - size + 2, center_y - size + 2, center_x + size + 2, center_y + size + 2,
                                    width=4, fill="#7f8c8d", tags=tag)
            self.canvas.create_line(center_x + size + 2, center_y - size + 2, center_x - size + 2, center_y + size + 2,
                                    width=4, fill="#7f8c8d", tags=tag)
            # Główny znak
            self.canvas.create_line(center_x - size, center_y - size, center_x + size, center_y + size, width=4,
                                    fill=color, tags=tag)
            self.canvas.create_line(center_x + size, center_y - size, center_x - size, center_y + size, width=4,
                                    fill=color, tags=tag)
        elif mark_char == "O":
            # Cień
            self.canvas.create_oval(center_x - size + 2, center_y - size + 2, center_x + size + 2, center_y + size + 2,
                                    width=4, outline="#7f8c8d", tags=tag)
            # Główny znak
            self.canvas.create_oval(center_x - size, center_y - size, center_x + size, center_y + size, width=4,
                                    outline=color, tags=tag)

    def _animate_mark_placement(self, r_idx, c_idx, mark_char, color, current_step=0, max_steps=10, delay=20):
        tag = f"mark_{r_idx}_{c_idx}"
        if current_step > max_steps:
            self._draw_mark_at_scale(r_idx, c_idx, mark_char, color, 1.0, tag)  # Finalne dorysowanie
            self.animated_objects.pop(tag, None)
            return

        scale = current_step / max_steps
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

        # Anuluj poprzednią animację dla tego pola jeśli jakaś była (mało prawdopodobne, ale bezpieczne)
        tag = f"mark_{row}_{col}"
        if tag in self.animated_objects: self.master.after_cancel(
            self.animated_objects[tag]); self.animated_objects.pop(tag)

        # Ustawiamy znak w logice planszy
        self.board[row][col] = self.my_mark
        # Rozpoczynamy animację rysowania
        self._animate_mark_placement(row, col, self.my_mark, self.player_colors.get(self.my_mark, "#000000"))

        # Sprawdzenie stanu gry i zmiana tury (bezpośrednio po logice, nie czeka na koniec animacji)
        self._check_game_state_after_move(self.my_mark)  # Ta funkcja musi być wywołana po ustawieniu self.board
        if not self.game_over:  # Wyślij ruch tylko jeśli gra się nie zakończyła
            self.send_message(f"MOVE|{row}|{col}")

    def make_move(self, r, c, mark):  # Wywoływane po otrzymaniu ruchu od przeciwnika
        if self.board[r][c] == "" and not self.game_over:
            self.board[r][c] = mark  # Ustaw logikę
            # Rozpocznij animację dla ruchu przeciwnika
            self._animate_mark_placement(r, c, mark, self.player_colors.get(mark, "#000000"))
            self._check_game_state_after_move(mark)  # Sprawdź stan gry

    def _check_game_state_after_move(self, mark_just_placed):
        winner_info = self.get_winner_info(mark_just_placed)
        if winner_info:
            winner_mark, winner_color = winner_info[0], self.player_colors.get(winner_info[0], "#27AE60")
            self.status_label.config(text=f"🎉 Gracz {winner_mark} ZWYCIĘŻA! 🎉", font=("Helvetica", 20, "bold"),
                                     fg=winner_color)
            self.animate_winning_line(winner_info, winner_color)  # Zamiast draw_winning_line
            self.game_over = True;
            self.trigger_victory_celebration(winner_color)
        elif self.is_board_full():
            self.status_label.config(text="Remis!", font=("Helvetica", 18, "bold"));
            self.game_over = True
        else:  # Zmiana tury tylko jeśli gra nie jest zakończona
            self.turn = self.other_mark if self.turn == self.my_mark else self.my_mark
            turn_text = "Twój ruch" if self.turn == self.my_mark else "Ruch przeciwnika"
            self.status_label.config(text=turn_text, font=("Helvetica", 16, "bold"), fg="white")

    def get_winner_info(self, mark):
        for i in range(3):
            if all(self.board[i][j] == mark for j in range(3)): return (mark, "row", i)
            if all(self.board[j][i] == mark for j in range(3)): return (mark, "col", i)
        if all(self.board[i][i] == mark for i in range(3)): return (mark, "diag", None)
        if all(self.board[i][2 - i] == mark for i in range(3)): return (mark, "antidiag", None)
        return None

    def animate_winning_line(self, winner_info, color="#27AE60", steps=20, delay=15):
        self.canvas.delete("win_line")  # Usuń starą linię, jeśli jest
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
            x_start, y_start, x_end, y_end = 300 - padding, padding, padding, 300 - padding  # antidiag

        dx = (x_end - x_start) / steps
        dy = (y_end - y_start) / steps

        def _draw_segment(current_step):
            if current_step > steps: return
            curr_x = x_start + dx * current_step
            curr_y = y_start + dy * current_step
            # Rysuj odcinek od poprzedniego punktu do aktualnego
            prev_x = x_start + dx * (current_step - 1)
            prev_y = y_start + dy * (current_step - 1)
            if current_step > 0:  # Nie rysuj nic dla kroku 0, zacznij od 1
                self.canvas.create_line(prev_x, prev_y, curr_x, curr_y, width=5, fill=color,
                                        tags="win_line_segment")  # Użyj innego tagu, by nie kasować całości
            self.master.after(delay, _draw_segment, current_step + 1)

        _draw_segment(1)  # Zacznij od kroku 1

    def is_board_full(self):
        return all(self.board[i][j] != "" for i in range(3) for j in range(3))

    def reset_board(self):
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.canvas.delete("win_line_segment")  # Usuń segmenty linii wygrywającej
        self.canvas.delete("hover_highlight")
        # Usuń wszystkie dynamicznie rysowane znaki
        for r in range(3):
            for c in range(3):
                self.canvas.delete(f"mark_{r}_{c}")
                self.animated_objects.pop(f"mark_{r}_{c}", None)  # Usuń z listy animowanych

        self.draw_board_static()  # Odśwież statyczną planszę
        self.game_over = False;
        self.stop_fireworks_display()

    def request_reset(self):
        if self.reset_pending: return
        self.reset_pending = True;
        self.status_label.config(text="Wysłano prośbę o reset...", fg="white");
        self.reset_button.config(state=tk.DISABLED,
                                 bg=BUTTON_BG_COLOR)  # Ustaw BG na normalny, bo stan DISABLED ma swój
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
        # Przyciski w dialogu też mogą mieć hover
        accept_btn = tk.Button(btn_frame, text="Tak", font=("Helvetica", 12, "bold"), bg="#27AE60", fg="white",
                               activebackground="#229954", command=accept);
        accept_btn.pack(side=tk.LEFT, padx=5)
        reject_btn = tk.Button(btn_frame, text="Nie", font=("Helvetica", 12, "bold"), bg="#C0392B", fg="white",
                               activebackground="#A93226", command=reject);
        reject_btn.pack(side=tk.LEFT, padx=5)
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
        if sock_to_use:
            try:
                sock_to_use.sendall((message + "\n").encode())
            except Exception as e:
                print(f"SEND FAIL: {e} for '{message}'")
        else:
            print(f"SEND FAIL: No socket for '{message}'")

    def receive_messages(self, sock):
        buffer = ""
        while True:
            try:
                data = sock.recv(BUFFER_SIZE)
            except socket.timeout:
                continue  # Jeśli socket ma timeout
            except Exception as e:
                print(f"RECV ERROR: {e}"); break
            if not data: print(f"RECV: Connection closed."); break
            buffer += data.decode('utf-8', 'ignore')
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1);
                line_to_process = line.strip()
                self.master.after(0, self.process_message, line_to_process)
        if hasattr(self, 'game_frame') and self.game_frame.winfo_exists(): self.master.after(100, self.exit_game)

    def process_message(self, message):
        parts = message.split("|");
        cmd = parts[0]
        if cmd == "START":
            self.turn = parts[1];
            self.player_colors['X'] = parts[2];
            self.player_colors['O'] = parts[3]
            self.reset_board()  # Czyści planszę i rysuje ją na nowo (bez znaków)
            turn_text = "Twój ruch" if self.turn == self.my_mark else "Ruch przeciwnika"
            self.status_label.config(text=turn_text, font=("Helvetica", 16, "bold"), fg="white")
        elif cmd == "MOVE":
            try:
                r, c = int(parts[1]), int(parts[2]); self.make_move(r, c, self.other_mark)
            except (ValueError, IndexError) as e:
                print(f"PROC MOVE ERR: {message}, {e}"); return
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
            print(f"PROC UNKNOWN CMD: '{cmd}' in '{message}'")

    def connect_to_server(self):
        self.my_mark, self.other_mark = "O", "X";
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host_ip, self.host_port));
            self.sock.settimeout(5.0)
            self.status_label.config(text="Połączono. Oczekiwanie na start...", fg="white")
            threading.Thread(target=self.receive_messages, args=(self.sock,), daemon=True).start()
        except Exception as e:
            self.status_label.config(text=f"Błąd połączenia: {e}", fg="red");self.master.after(2000, self.exit_game)

    def assign_colors_and_turn(self):
        color_x = random.choice(AVAILABLE_PLAYER_COLORS);
        available_colors_for_o = [c for c in AVAILABLE_PLAYER_COLORS if c != color_x];
        color_o = random.choice(available_colors_for_o) if available_colors_for_o else "#17A589"
        self.player_colors['X'], self.player_colors['O'] = color_x, color_o;
        first_turn = random.choice(["X", "O"]);
        self.turn = first_turn
        self.reset_board()  # Resetuje i rysuje pustą planszę
        if self.conn:
            self.send_message(f"START|{self.turn}|{color_x}|{color_o}", connection=self.conn)
            turn_text = "Losowanie: Zaczynasz!" if self.turn == self.my_mark else "Losowanie: Przeciwnik zaczyna."
            self.status_label.config(text=turn_text, font=("Helvetica", 16, "bold"), fg="white")

    def start_server(self):
        self.my_mark, self.other_mark = "X", "O";
        self.port = get_free_port();
        local_ip = get_local_ip()
        self.status_label.config(text=f"Hostujesz grę.\nIP: {local_ip} Port: {self.port}\nOczekiwanie...",
                                 font=("Helvetica", 14), fg="white")
        threading.Thread(target=self.server_thread, daemon=True).start()

    def server_thread(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind(("", self.port))
        except Exception as e:
            self.status_label.config(text=f"Błąd portu: {e}", fg="red");return
        server_sock.listen(1)
        try:
            self.conn, addr = server_sock.accept();
            self.conn.settimeout(5.0)
            self.assign_colors_and_turn()
            threading.Thread(target=self.receive_messages, args=(self.conn,), daemon=True).start()
        except Exception as e:
            self.status_label.config(text=f"Błąd połączenia: {e}", fg="red")
        finally:
            server_sock.close()

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
                                                                                                                     self.winning_player_color)  # Zwiększona szansa
        self.canvas.delete("firework");
        new_particles = []
        for p in self.fireworks_particles:
            p['x'] += p['vx'];
            p['y'] += p['vy'];
            p['vy'] += 0.1;
            p['life'] -= random.uniform(0.5, 1.5)  # Zróżnicowane zanikanie
            if p['life'] > 0: new_particles.append(p);size = p['size'] * (
                        p['life'] / p['max_life']);self.canvas.create_oval(p['x'] - size, p['y'] - size, p['x'] + size,
                                                                           p['y'] + size, fill=p['color'],
                                                                           outline=p['color'], tags="firework")
        self.fireworks_particles = new_particles;
        self.fireworks_animation_id = self.master.after(40, self._animate_fireworks)  # Szybsza animacja

    def _create_firework_burst(self, x, y, base_color):
        num_particles = random.randint(30, 50)  # Więcej cząstek
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
        self.stop_fireworks_display()
        # Anuluj wszystkie oczekujące animacje znaków
        for anim_id in self.animated_objects.values(): self.master.after_cancel(anim_id)
        self.animated_objects.clear()
        try:
            if self.is_host and self.conn: self.conn.close(); self.conn = None
            if not self.is_host and self.sock: self.sock.close(); self.sock = None
        except Exception as e:
            print(f"EXIT ERR: {e}")
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

    def _setup_button_hover(self, button):  # Metoda pomocnicza dla MainMenu
        button.bind("<Enter>", lambda e, b=button: b.config(bg=BUTTON_HOVER_BG_COLOR))
        button.bind("<Leave>", lambda e, b=button: b.config(bg=BUTTON_BG_COLOR))
        button.bind("<ButtonPress-1>",
                    lambda e, b=button: b.config(bg=BUTTON_ACTIVE_BG_COLOR))  # Ciemniejszy przy kliknięciu
        button.bind("<ButtonRelease-1>",
                    lambda e, b=button: b.config(bg=BUTTON_HOVER_BG_COLOR))  # Powrót do hover po puszczeniu

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
        ip_entry.pack(pady=5);
        ip_entry.insert(0, "127.0.0.1")  # Domyślnie localhost
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
        for widget in self.master.winfo_children(): widget.destroy()
        MainMenu(self.master)


def main():
    root = tk.Tk()
    MainMenu(root)
    root.mainloop()


if __name__ == "__main__":
    main()