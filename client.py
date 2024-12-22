import tkinter as tk
from tkinter import ttk, messagebox
import websockets
import asyncio
import json
import threading
from enum import Enum

class GameState(Enum):
    PLAYING = 0
    GAME_OVER = 1

class GomokuClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("五子棋网络对战")
        
        self.SERVER_URL = "ws://localhost:8765"
        self.websocket = None
        self.room_id = None
        self.loop = None
        self.message_thread = None
        self.is_connected = False
        self.is_my_turn = False
        self.game_started = False
        self.is_black = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2000
        
        self.setup_main_ui()
        self.connect_to_server()
        
    def setup_main_ui(self):
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = ttk.Label(self.status_frame, text="状态: 未连接")
        self.status_label.pack(side=tk.LEFT)
        
        self.rooms_frame = ttk.LabelFrame(self, text="房间列表")
        self.rooms_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.room_buttons = []
        for i in range(5):
            room_frame = ttk.Frame(self.rooms_frame)
            room_frame.pack(fill=tk.X, padx=5, pady=2)
            
            room_btn = ttk.Button(room_frame, 
                                text=f"房间 {i+1}\n(空闲)", 
                                width=20,
                                command=lambda x=i+1: self.join_room(str(x)))
            room_btn.pack(side=tk.LEFT, padx=5)
            
            exit_btn = ttk.Button(room_frame,
                                text="退出",
                                command=lambda x=i+1: self.exit_room(str(x)),
                                state=tk.DISABLED)
            exit_btn.pack(side=tk.LEFT, padx=5)
            
            self.room_buttons.append((room_btn, exit_btn))
        
        self.game_frame = ttk.Frame(self)
        self.gomoku = None
    
    def update_connection_status(self, is_connected: bool, message: str = None):
        self.is_connected = is_connected
        status_text = f"状态: {'已连接' if is_connected else '未连接'}"
        if message:
            status_text += f" - {message}"
        self.status_label.config(text=status_text)
        
        for room_btn, _ in self.room_buttons:
            room_btn.config(state=tk.NORMAL if is_connected else tk.DISABLED)
        
        if not is_connected:
            self.try_reconnect()

    def try_reconnect(self):
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            self.status_label.config(text=f"状态: 正在尝试重新连接... ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
            self.after(self.reconnect_delay, self.connect_to_server)
        else:
            self.status_label.config(text="状态: 重连失败，请重启程序")
    
    def update_room_status(self, room_id: str, player_count: int):
        idx = int(room_id) - 1
        if 0 <= idx < len(self.room_buttons):
            room_btn, exit_btn = self.room_buttons[idx]
            status = "满员" if player_count >= 2 else f"({player_count}/2人)"
            room_btn.config(text=f"房间 {room_id}\n{status}")
            room_btn.config(state=tk.DISABLED if player_count >= 2 else tk.NORMAL)
    
    def connect_to_server(self):
        self.loop = asyncio.new_event_loop()
        self.message_thread = threading.Thread(target=self._run_async_loop, 
                                            args=(self.SERVER_URL,), 
                                            daemon=True)
        self.message_thread.start()
        
    def _run_async_loop(self, uri):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.start_connection(uri))
    
    async def start_connection(self, uri):
        try:
            self.websocket = await websockets.connect(uri, ping_interval=None)
            self.after(0, lambda: self.update_connection_status(True))
            self.reconnect_attempts = 0
            await self.message_loop()
        except Exception as e:
            self.after(0, lambda: self.update_connection_status(False, str(e)))
    
    async def message_loop(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self.after(0, lambda d=data: self.handle_server_message_safe(d))
                except json.JSONDecodeError:
                    print("Invalid JSON received")
                except Exception as e:
                    print(f"Error handling message: {str(e)}")
        except websockets.exceptions.ConnectionClosed:
            self.after(0, lambda: self.update_connection_status(False, "连接已断开"))
        except Exception as e:
            self.after(0, lambda: self.update_connection_status(False, f"连接错误: {str(e)}"))
    
    def handle_server_message_safe(self, data):
        action = data.get('action')
        print(f"Received message: {data}")
        
        if action == 'room_status':
            for room_id, status in data.get('rooms', {}).items():
                self.update_room_status(room_id, status['player_count'])
                
        elif action == 'join_success':
            self.room_id = data.get('room_id')
            self.is_black = data.get('is_first', False)
            role = data.get('role', 'black' if self.is_black else 'white')
            room_idx = int(self.room_id) - 1
            _, exit_btn = self.room_buttons[room_idx]
            exit_btn.config(state=tk.NORMAL)
            self.show_game_ui()
            print(f"Joined room as {role}")
            
        elif action == 'game_start':
            print("Received game_start message")
            self.game_started = True
            if self.gomoku:
                # 重新初始化游戏状态
                self.gomoku.init_game_state(self.is_black)
                print(f"Started game as {'black' if self.is_black else 'white'}")
            
        elif action == 'move':
            if self.gomoku:  # 移除 game_started 检查
                x, y = data.get('x'), data.get('y')
                player = data.get('player')
                print(f"Received move: {x}, {y} by player {player}")
                self.gomoku.handle_remote_move(x, y, player)
                
        elif action == 'player_disconnected':
            if self.gomoku:
                messagebox.showwarning("提示", "对手已断开连接")
                self.exit_room(self.room_id)
                
        elif action == 'game_over':
            if self.gomoku:
                winner = data.get('winner', '')
                messagebox.showinfo("游戏结束", f"{winner}获胜！")
                self.gomoku.game_state = GameState.GAME_OVER
    
    async def send_message(self, data):
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(data))
            except Exception as e:
                print(f"Error sending message: {str(e)}")
                self.after(0, lambda: self.update_connection_status(False, "发送消息失败"))

    def join_room(self, room_id: str):
        if self.websocket and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.send_message({
                    'action': 'join_room',
                    'room_id': room_id
                }),
                self.loop
            )
    
    def exit_room(self, room_id: str):
        if self.websocket and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.send_message({
                    'action': 'exit_room',
                    'room_id': room_id
                }),
                self.loop
            )
            self.hide_game_ui()
            room_idx = int(room_id) - 1
            _, exit_btn = self.room_buttons[room_idx]
            exit_btn.config(state=tk.DISABLED)
            self.room_id = None
    
    def show_game_ui(self):
        self.hide_game_ui()
        
        self.gomoku = Gomoku(self.game_frame, self)
        role = "黑方" if self.is_black else "白方"
        self.gomoku.player_label.config(text=f"你是{role} - 等待对手加入...")
        print(f"Showing game UI as {role}")
        self.game_frame.pack(after=self.rooms_frame)
    
    def hide_game_ui(self):
        if self.gomoku:
            self.gomoku.destroy()
            self.gomoku = None
        if self.game_frame:
            self.game_frame.pack_forget()

class Gomoku:
    def __init__(self, master, client):
        self.master = master
        self.client = client
        self.is_my_turn = False
        self.master.pack()
        
        self.board_size = 15
        self.cell_size = 40
        self.offset = 20
        
        self.root_frame = tk.Frame(master)
        self.root_frame.pack()
        
        self.canvas = tk.Canvas(
            self.root_frame,
            width=self.board_size * self.cell_size, 
            height=self.board_size * self.cell_size, 
            bg="burlywood"
        )
        self.canvas.pack()
        
        self.game_state = GameState.PLAYING
        self.moves_history = []
        self.game_started = False
        self.is_black = False
        
        self.control_frame = tk.Frame(self.root_frame)
        self.control_frame.pack(pady=5)
        
        self.player_label = tk.Label(self.control_frame, text="当前玩家：黑棋")
        self.player_label.pack(side=tk.LEFT, padx=10)
        
        self.board = [[0] * self.board_size for _ in range(self.board_size)]
        self.current_player = 1
        
        self.draw_board()
        self.canvas.bind("<Button-1>", self.handle_click)
        self.init_game_state(client.is_black)  # 初始化游戏状态
    
    def init_game_state(self, is_black):
        """初始化或重置游戏状态"""
        print(f"Initializing game state as {'black' if is_black else 'white'}")
        self.game_started = True
        self.is_black = is_black
        self.game_state = GameState.PLAYING
        self.current_player = 1  # 总是从黑方开始
        self.is_my_turn = is_black  # 如果是黑方则轮到自己
        
        role = "黑方" if is_black else "白方"
        if is_black:
            status = "轮到你下"
        else:
            status = "等待黑方下棋"
        
        text = f"游戏开始 - 你是{role} - {status}"
        print(f"Setting label: {text}")
        self.player_label.config(text=text)
    
    def draw_board(self):
        for i in range(self.board_size):
            self.canvas.create_line(
                self.offset, self.offset + i * self.cell_size,
                self.offset + (self.board_size - 1) * self.cell_size, self.offset + i * self.cell_size
            )
            self.canvas.create_line(
                self.offset + i * self.cell_size, self.offset,
                self.offset + i * self.cell_size, self.offset + (self.board_size - 1) * self.cell_size
            )
        self.draw_star_points()
    
    def draw_star_points(self):
        star_positions = [(3, 3), (3, 11), (11, 3), (11, 11), (7, 7)]
        for x, y in star_positions:
            cx = self.offset + x * self.cell_size
            cy = self.offset + y * self.cell_size
            self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="black")
    
    def start_game(self, is_black):
        """开始游戏"""
        print(f"Starting game as {'black' if is_black else 'white'}")
        self.game_started = True
        self.is_black = is_black
        self.game_state = GameState.PLAYING
        self.current_player = 1  # 总是从黑方开始
        self.is_my_turn = is_black  # 如果是黑方则轮到自己
        
        role = "黑方" if is_black else "白方"
        if is_black:
            status = "轮到你下"
        else:
            status = "等待黑方下棋"
        
        text = f"游戏开始 - 你是{role} - {status}"
        print(f"Setting label: {text}")
        self.player_label.config(text=text)
    
    def handle_click(self, event):
        """处理鼠标点击事件"""
        print(f"Click - game_started: {self.game_started}, is_my_turn: {self.is_my_turn}")
        print(f"Current player: {self.current_player}, is_black: {self.is_black}")
        
        if not self.game_started or self.game_state == GameState.GAME_OVER:
            print("Game not started or already over")
            return
        
        # 检查是否该我方下棋
        can_move = ((self.is_black and self.current_player == 1) or 
                   (not self.is_black and self.current_player == 2))
        
        if not (self.is_my_turn and can_move):
            print(f"Not your turn. is_my_turn: {self.is_my_turn}, can_move: {can_move}")
            return
        
        x = (event.x - self.offset + self.cell_size // 2) // self.cell_size
        y = (event.y - self.offset + self.cell_size // 2) // self.cell_size
        
        if 0 <= x < self.board_size and 0 <= y < self.board_size and self.board[y][x] == 0:
            self.place_piece(x, y)
            
            if self.client and self.client.websocket and self.client.loop:
                asyncio.run_coroutine_threadsafe(
                    self.client.send_message({
                        'action': 'move',
                        'room_id': self.client.room_id,
                        'x': x,
                        'y': y
                    }),
                    self.client.loop
                )
            
            if self.check_winner(x, y):
                winner = "黑棋" if self.current_player == 1 else "白棋"
                messagebox.showinfo("游戏结束", f"{winner}获胜！")
                self.game_state = GameState.GAME_OVER
                if self.client and self.client.websocket and self.client.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.client.send_message({
                            'action': 'game_over',
                            'room_id': self.client.room_id,
                            'winner': winner
                        }),
                        self.client.loop
                    )
            
            self.is_my_turn = False
            self.current_player = 3 - self.current_player
            self.update_player_label()
    
    def place_piece(self, x, y):
        self.board[y][x] = self.current_player
        cx = self.offset + x * self.cell_size
        cy = self.offset + y * self.cell_size
        color = "black" if self.current_player == 1 else "white"
        piece = self.canvas.create_oval(cx-15, cy-15, cx+15, cy+15, fill=color, outline="#404040")
        self.moves_history.append((x, y, piece))
        
    def check_winner(self, x, y):
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            count += self.count_pieces(x, y, dx, dy)
            count += self.count_pieces(x, y, -dx, -dy)
            if count >= 5:
                return True
        return False
    
    def count_pieces(self, x, y, dx, dy):
        count = 0
        player = self.board[y][x]
        nx, ny = x + dx, y + dy
        while 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[ny][nx] == player:
            count += 1
            nx += dx
            ny += dy
        return count
    
    def update_player_label(self):
        """更新当前玩家标签"""
        if not self.game_started:
            return
            
        if self.game_state == GameState.GAME_OVER:
            self.player_label.config(text="游戏结束")
            return
            
        role = "黑方" if self.is_black else "白方"
        current = "黑棋" if self.current_player == 1 else "白棋"
        
        # 判断是否轮到自己
        my_turn = (self.is_black and self.current_player == 1) or (not self.is_black and self.current_player == 2)
        status = "轮到你下" if (self.is_my_turn and my_turn) else "等待对手"
        
        text = f"你是{role} - 当前{current} - {status}"
        print(f"Updating label: {text}")
        self.player_label.config(text=text)
        
    def handle_remote_move(self, x, y, player):
        """处理对手的远程移动"""
        if not self.game_started:
            return
            
        print(f"Handling remote move: {x}, {y} by player {player}")
        self.current_player = player
        self.place_piece(x, y)
        self.current_player = 3 - player  # 切换到下一个玩家
        self.is_my_turn = True  # 轮到我方下棋
        print(f"After remote move - current_player: {self.current_player}, is_my_turn: {self.is_my_turn}")
        self.update_player_label()
        
    def destroy(self):
        if self.root_frame:
            self.root_frame.destroy()
        self.canvas = None
        self.control_frame = None
        self.root_frame = None

if __name__ == "__main__":
    app = GomokuClient()
    app.mainloop()
