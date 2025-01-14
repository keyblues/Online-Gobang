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

class LobbyWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        # 添加主题颜色
        self.theme = {
            'primary': '#4A90E2',      # 主色调
            'secondary': '#F5F5F5',    # 背景色
            'text': '#333333',         # 主文本色
            'text_light': '#666666',   # 次要文本色
            'success': '#2ECC71',      # 成功色
            'warning': '#E67E22',      # 警告色
            'board_bg': '#E9B973',     # 棋盘背景色
            'board_line': '#8B4513',   # 棋盘线条色
            'black_piece': '#000000',  # 黑棋颜色
            'white_piece': '#FFFFFF'   # 白棋颜色
        }
        
        self.title("五子棋 - 游戏大厅")
        self.configure(bg=self.theme['secondary'])
        
        # 更新样式
        self.style = ttk.Style()
        self.style.configure(
            "Room.TButton",
            padding=15,
            font=('Microsoft YaHei UI', 11, 'bold'),
            background=self.theme['primary'],
            foreground='white'
        )
        self.style.configure(
            "Exit.TButton",
            padding=10,
            font=('Microsoft YaHei UI', 10),
            foreground=self.theme['warning']
        )
        self.style.configure(
            "Title.TLabel",
            font=('Microsoft YaHei UI', 24, 'bold'),
            foreground=self.theme['primary']
        )
        
        self.setup_lobby_ui()
        self.game_windows = {}  # 存储游戏窗口实例
        self.start_websocket()  # 添加websocket连接
    
    def setup_lobby_ui(self):
        # Logo和标题
        logo_frame = ttk.Frame(self)
        logo_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title_label = ttk.Label(
            logo_frame,
            text="五子棋对战",
            style="Title.TLabel"
        )
        title_label.pack()
        
        # 状态栏
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(fill=tk.X, padx=20)
        self.status_label = ttk.Label(
            self.status_frame,
            text="状态: 未连接",
            style="Status.TLabel"
        )
        self.status_label.pack(side=tk.LEFT)
        
        # 分隔线
        separator = ttk.Separator(self, orient='horizontal')
        separator.pack(fill=tk.X, padx=20, pady=20)
        
        # 房间列表
        rooms_frame = ttk.Frame(self)
        rooms_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        self.room_buttons = []
        for i in range(5):
            room_container = ttk.Frame(rooms_frame)
            room_container.pack(fill=tk.X, pady=10)
            
            room_frame = ttk.Frame(
                room_container,
                style="Room.TFrame"
            )
            room_frame.pack(fill=tk.X)
            
            # 房间信息
            info_frame = ttk.Frame(room_frame)
            info_frame.pack(side=tk.LEFT, padx=10)
            
            room_label = ttk.Label(
                info_frame,
                text=f"房间 {i+1}",
                font=('Microsoft YaHei UI', 12)
            )
            room_label.pack(anchor=tk.W)
            
            status_label = ttk.Label(
                info_frame,
                text="等待玩家加入...",
                font=('Microsoft YaHei UI', 9),
                foreground='#666666'
            )
            status_label.pack(anchor=tk.W)
            
            # 按钮
            button_frame = ttk.Frame(room_frame)
            button_frame.pack(side=tk.RIGHT, padx=10)
            
            join_btn = ttk.Button(
                button_frame,
                text="加入房间",
                style="Room.TButton",
                command=lambda x=i+1: self.join_room(str(x))
            )
            join_btn.pack(side=tk.LEFT, padx=5)
            
            exit_btn = ttk.Button(
                button_frame,
                text="退出",
                style="Exit.TButton",
                state=tk.DISABLED,
                command=lambda x=i+1: self.exit_room(str(x))
            )
            exit_btn.pack(side=tk.LEFT)
            
            self.room_buttons.append((join_btn, exit_btn, status_label))
            
            # 分隔线
            if i < 4:
                separator = ttk.Separator(rooms_frame, orient='horizontal')
                separator.pack(fill=tk.X, pady=10)

    def join_room(self, room_id):
        # 创建新的游戏窗口
        game_window = GameWindow(self, room_id)
        self.game_windows[room_id] = game_window
        
        # 更新按钮状态
        idx = int(room_id) - 1
        join_btn, exit_btn, _ = self.room_buttons[idx]
        join_btn.config(state=tk.DISABLED)
        exit_btn.config(state=tk.NORMAL)

    def exit_room(self, room_id):
        if room_id in self.game_windows:
            self.game_windows[room_id].destroy()
            del self.game_windows[room_id]
            
            # 更新按钮状态
            idx = int(room_id) - 1
            join_btn, exit_btn, _ = self.room_buttons[idx]
            join_btn.config(state=tk.NORMAL)
            exit_btn.config(state=tk.DISABLED)

    def start_websocket(self):
        self.ws = None
        threading.Thread(target=self.websocket_thread, daemon=True).start()
    
    def websocket_thread(self):
        async def connect():
            uri = "ws://localhost:8765"
            try:
                async with websockets.connect(uri) as websocket:
                    self.ws = websocket
                    self.status_label.config(text="状态: 已连接")
                    while True:
                        try:
                            message = await websocket.recv()
                            data = json.loads(message)
                            await self.handle_lobby_message(data)
                        except Exception as e:
                            print(f"Error in lobby websocket: {e}")
                            break
            except Exception as e:
                print(f"Connection error: {e}")
                self.status_label.config(text="状态: 连接失败")
            finally:
                self.ws = None
                self.status_label.config(text="状态: 未连接")
        
        asyncio.run(connect())

    async def handle_lobby_message(self, data):
        action = data.get('action')
        if action == 'room_status':
            rooms = data.get('rooms', {})
            for room_id, status in rooms.items():
                idx = int(room_id) - 1
                if 0 <= idx < len(self.room_buttons):
                    _, _, status_label = self.room_buttons[idx]
                    player_count = status.get('player_count', 0)
                    status_text = f"玩家数: {player_count}/2"
                    status_label.config(text=status_text)

class GameWindow(tk.Toplevel):
    def __init__(self, master, room_id):
        super().__init__(master)
        self.title(f"五子棋 - 房间 {room_id}")
        self.configure(bg='#F5F5F5')
        
        # 初始化游戏状态
        self.room_id = room_id
        self.game_state = GameState.PLAYING
        self.board = [[0]*15 for _ in range(15)]
        self.is_my_turn = False
        self.my_role = None
        self.cell_size = 40  # 调整格子大小
        self.board_padding = 50  # 调整边距
        self.pending_move = None  # 添加等待确认的移动
        self.current_player = None  # 添加当前玩家标记
        self._ws_lock = threading.Lock()  # 添加线程锁
        self._cleanup_needed = False  # 添加清理标记
        self.last_move = None  # 添加最后一步记录
        
        # 窗口设置
        window_width = 600
        window_height = 700
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2 + 200  # 错开与大厅窗口
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.resizable(False, False)
        
        self.room_id = room_id
        self.setup_game_ui()
        
        # 关闭窗口时退出房间
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("初始化游戏窗口")  # 添加调试信息
    
    def setup_game_ui(self):
        # 添加玩家信息面板
        player_frame = ttk.Frame(self)
        player_frame.pack(fill=tk.X, padx=30, pady=15)

        # 黑方信息
        black_frame = ttk.Frame(player_frame)
        black_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(
            black_frame,
            text="⚫ 黑方",
            font=('Microsoft YaHei UI', 14, 'bold'),
            foreground=self.master.theme['black_piece']
        ).pack()

        # 状态信息
        self.status_label = ttk.Label(
            player_frame,
            text="等待对手加入...",
            font=('Microsoft YaHei UI', 14),
            foreground=self.master.theme['primary']
        )
        self.status_label.pack(side=tk.LEFT, expand=True)

        # 白方信息
        white_frame = ttk.Frame(player_frame)
        white_frame.pack(side=tk.RIGHT, padx=20)
        ttk.Label(
            white_frame,
            text="⚪ 白方",
            font=('Microsoft YaHei UI', 14, 'bold'),
            foreground=self.master.theme['text_light']
        ).pack()

        # 棋盘容器（添加阴影效果）
        board_container = ttk.Frame(self)
        board_container.pack(pady=20, padx=30)

        # 棋盘画布
        self.canvas = tk.Canvas(
            board_container,
            width=600,
            height=600,
            bg=self.master.theme['board_bg'],
            highlightthickness=1,
            highlightbackground=self.master.theme['board_line']
        )
        self.canvas.pack()

        # 绘制棋盘
        self.draw_board()
        
        # 绑定鼠标事件
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # 启动websocket连接
        self.start_websocket()
    
    def draw_board(self):
        self.canvas.delete("all")
        
        # 绘制棋盘背景
        self.canvas.create_rectangle(
            0, 0, 600, 600,
            fill=self.master.theme['board_bg'],
            outline=""
        )
        
        # 绘制网格线
        for i in range(15):
            # 横线
            self.canvas.create_line(
                self.board_padding, self.board_padding + i * self.cell_size,
                self.board_padding + 14 * self.cell_size, self.board_padding + i * self.cell_size,
                fill=self.master.theme['board_line'],
                width=1
            )
            # 竖线
            self.canvas.create_line(
                self.board_padding + i * self.cell_size, self.board_padding,
                self.board_padding + i * self.cell_size, self.board_padding + 14 * self.cell_size,
                fill=self.master.theme['board_line'],
                width=1
            )

        # 绘制天元和星点
        star_points = [(3,3), (11,3), (7,7), (3,11), (11,11)]
        for x, y in star_points:
            self.draw_star_point(x, y)
        
        # 绘制棋子
        for y in range(15):
            for x in range(15):
                if self.board[y][x] != 0:
                    self.draw_piece(x, y, self.board[y][x])

    def draw_star_point(self, x, y):
        """绘制星点"""
        cx = self.board_padding + x * self.cell_size
        cy = self.board_padding + y * self.cell_size
        r = 4
        self.canvas.create_oval(
            cx-r, cy-r, cx+r, cy+r,
            fill=self.master.theme['board_line']
        )

    def draw_piece(self, x, y, player):
        """绘制棋子带光泽效果"""
        cx = self.board_padding + x * self.cell_size
        cy = self.board_padding + y * self.cell_size
        r = 16

        color = self.master.theme['black_piece'] if player == 1 else self.master.theme['white_piece']
        
        # 绘制阴影
        self.canvas.create_oval(
            cx-r+2, cy-r+2, cx+r+2, cy+r+2,
            fill='gray', outline='gray'
        )
        
        # 绘制棋子本体
        self.canvas.create_oval(
            cx-r, cy-r, cx+r, cy+r,
            fill=color,
            outline='gray'
        )
        
        # 添加高光效果
        if player == 2:  # 白棋添加光泽
            self.canvas.create_oval(
                cx-r/2, cy-r/2, cx, cy,
                fill='white',
                stipple='gray50'
            )
    
    def on_canvas_click(self, event):
        print(f"点击事件: x={event.x}, y={event.y}, is_my_turn={self.is_my_turn}, my_role={self.my_role}")
        
        if not self.is_my_turn or self.game_state != GameState.PLAYING or self.pending_move:
            print(f"不能下棋: is_my_turn={self.is_my_turn}, game_state={self.game_state}")
            return
        
        # 修正坐标计算逻辑
        x = round((event.x - self.board_padding) / self.cell_size)
        y = round((event.y - self.board_padding) / self.cell_size)
        
        print(f"尝试落子: x={x}, y={y}, my_role={self.my_role}")
        
        # 验证坐标是否有效
        if 0 <= x < 15 and 0 <= y < 15 and self.board[y][x] == 0:
            # 不预先在本地显示棋子，等服务器确认
            self.pending_move = (x, y)
            self.send_move(x, y)
            self.is_my_turn = False  # 暂时禁用落子
            self.update_status()
    
    def start_websocket(self):
        self.ws = None
        threading.Thread(target=self.websocket_thread, daemon=True).start()
    
    def websocket_thread(self):
        async def connect():
            uri = "ws://localhost:8765"
            async with websockets.connect(uri) as websocket:
                self.ws = websocket
                # 加入房间
                await websocket.send(json.dumps({
                    "action": "join_room",
                    "room_id": self.room_id
                }))
                
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        self.handle_message(data)
                    except:
                        break
        
        asyncio.run(connect())
    
    def send_move(self, x, y):
        async def send():
            with self._ws_lock:  # 使用线程锁保护websocket访问
                if self.ws:
                    try:
                        await self.ws.send(json.dumps({
                            "action": "move",
                            "room_id": self.room_id,
                            "x": x,
                            "y": y
                        }))
                    except Exception as e:
                        print(f"发送移动消息失败: {e}")
                        self.handle_move_failed()

        asyncio.run(send())

    def handle_move_failed(self):
        """处理移动失败的情况"""
        if self.pending_move:
            x, y = self.pending_move
            self.board[y][x] = 0
            self.pending_move = None
            self.is_my_turn = True
            self.draw_board()
            self.update_status()
            self.after(0, lambda: messagebox.showwarning("提示", "落子失败: 网络错误"))

    def handle_message(self, data):
        # 使用after方法确保在主线程中处理UI更新
        self.after(0, lambda: self._handle_message_impl(data))

    def _handle_message_impl(self, data):
        """在主线程中处理消息"""
        action = data.get("action")
        print(f"收到消息: {action}, data={data}")
        
        if action == "join_success":
            self.my_role = data.get("role")
            self.is_my_turn = data.get("is_first", False)
            self.current_player = 1  # 游戏开始时黑棋先行
            game_state = data.get("game_state", {})
            self.board = game_state.get("board", [[0]*15 for _ in range(15)])
            self.pending_move = None
            self.draw_board()
            self.update_status()
            print(f"加入成功: role={self.my_role}, is_first={self.is_my_turn}")
        
        elif action == "game_start":
            game_state = data.get("game_state", {})
            self.board = game_state.get("board", [[0]*15 for _ in range(15)])
            self.game_state = GameState.PLAYING
            self.pending_move = None  # 重置等待移动
            self.draw_board()
            self.update_status()
        
        elif action == "game_state":
            # 处理游戏状态更新
            state = data.get("state", {})
            self.board = state.get("board", [[0]*15 for _ in range(15)])
            self.draw_board()
            self.update_status()
        
        elif action == "game_over":
            self.game_state = GameState.GAME_OVER
            winner = data.get("winner")
            messagebox.showinfo("游戏结束", f"{winner}获胜！")
            self.pending_move = None  # 重置等待移动
            self.update_status()
        
        elif action == "player_disconnected":
            if not self._cleanup_needed:  # 避免重复显示消息
                self._cleanup_needed = True
                messagebox.showinfo("提示", "对手已断开连接")
                self.game_state = GameState.GAME_OVER
                self.pending_move = None  # 重置等待移动
                self.update_status()
        
        elif action == "move":
            x = data.get("x")
            y = data.get("y")
            player = data.get("player")
            print(f"收到移动: x={x}, y={y}, player={player}, my_role={self.my_role}")
            
            if 0 <= x < 15 and 0 <= y < 15:
                self.board[y][x] = player
                self.last_move = (x, y)
                
                # 更新当前玩家
                self.current_player = 3 - player  # 切换到下一个玩家
                
                # 更新是否是我的回合
                self.is_my_turn = (
                    (self.my_role == "black" and self.current_player == 1) or
                    (self.my_role == "white" and self.current_player == 2)
                )
                
                if self.pending_move == (x, y):
                    self.pending_move = None
                
                print(f"移动后状态: current_player={self.current_player}, is_my_turn={self.is_my_turn}")
                self.draw_board()
                self.update_status()
        
        elif action == "move_failed":
            print(f"Move failed: {data.get('reason')}")  # 添加调试信息
            if self.pending_move:
                self.board[self.pending_move[1]][self.pending_move[0]] = 0
                self.pending_move = None
                self.is_my_turn = True  # 恢复落子权限
                self.draw_board()
                self.update_status()
                messagebox.showwarning("提示", "落子失败: " + data.get("reason", "未知原因"))
        
        elif action == "game_over":
            self.game_state = GameState.GAME_OVER
            winner = data.get("winner")
            messagebox.showinfo("游戏结束", f"{winner}获胜！")
            self.update_status()
        
        elif action == "player_disconnected":
            messagebox.showinfo("提示", "对手已断开连接")
            self.game_state = GameState.GAME_OVER
            self.update_status()
    
    def update_ui(self):
        self.draw_board()
        self.update_status()
    
    def update_status(self):
        status = "游戏结束"
        if self.game_state == GameState.PLAYING:
            if self.my_role is None:
                status = "等待加入游戏..."
            elif self.is_my_turn:
                if self.pending_move:
                    status = "等待服务器确认..."
                else:
                    status = "轮到你下棋"
            else:
                status = "等待对手下棋"
        
        self.status_label.config(text=status)
    
    def on_closing(self):
        """处理窗口关闭事件"""
        async def close():
            with self._ws_lock:
                if self.ws:
                    try:
                        await self.ws.send(json.dumps({
                            "action": "exit_room",
                            "room_id": self.room_id
                        }))
                    except:
                        pass
        
        try:
            asyncio.run(close())
        except:
            pass
        finally:
            self.master.exit_room(self.room_id)
            self.destroy()

if __name__ == "__main__":
    app = LobbyWindow()
    app.mainloop()
