import os
import sys
import threading
import time
import tkinter
from tkinter import messagebox

import pygame.freetype

from data import network, game

pygame.init()
game_socket = network.GameSocket()
game_state = 0
games = False  # 游戏是否开始
online_list = False  # 游戏在线列表显示状态
online_list_recv_state = False  # True表示接收线程已开启
game_receive_state = False
game_color = False  # False 是黑子 Ture 是白子
windows_new = 1
num = 0


def connect_windows():
    root = tkinter.Tk()
    root.title('服务器地址')
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f'250x60+{int(screen_width / 2)}+{int(screen_height / 2)}')
    root.resizable(width=False, height=False)
    entry_ip = tkinter.Entry(root, font=('Arial', 14))
    entry_ip.pack()
    tkinter.Button(root, width=10, height=1, text='连接', font=('Arial', 14),
                   command=lambda: connect_ip(root, entry_ip.get())).pack()
    entry_ip.focus_set()
    root.mainloop()


def connect_ip(root, entry_ip):
    global online_list, game_socket, screen
    game_socket.connect(entry_ip, 45555)
    # 连接成功后关闭主窗口
    online_list = True
    root.destroy()


def connect_game_windows(ips):
    global online_list_recv_state
    online_list_recv_state = True
    root = tkinter.Tk()
    root.title('温馨提示')
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f'400x60+{int(screen_width / 2)}+{int(screen_height / 2)}')
    root.resizable(width=False, height=False)
    tkinter.Label(root, text=f"已向{ips}发起挑战，等待回应中···", font=('Arial', 14),
                  justify='left', padx=10).pack(side='left')
    connect_game_threading = threading.Thread(target=connect_game, args=(root, ips))
    connect_game_threading.daemon = True
    connect_game_threading.start()

    def close_window():
        global online_list_recv_state
        online_list_recv_state = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_window)
    root.mainloop()


def connect_game(root, ips):
    global games, screen, game_receive_state, online_list_recv_state, online_list, game_color, game_receive_threading
    online_list_recv_state = True
    game_socket.connect_game(ips)
    time.sleep(1)
    while online_list:
        recv_data = game_socket.receive()
        print('recv_data···')
        if not recv_data:
            break
        if recv_data['type'] == 'Accept challenge':
            # 应战后关闭主窗口
            print('Accept challenge')
            game_receive_threading = threading.Thread(target=game_receive)
            game_receive_threading.daemon = True
            game_receive_threading.start()
            game_receive_state = True
            games = True
            online_list = False
            game_color = True
            root.destroy()
            break
        if recv_data['type'] == 'Refuse challenge':
            # 拒绝挑战
            messagebox.showerror("Error", "对方拒绝了挑战！")
            root.destroy()
            return False
        if recv_data['type'] == 'error':
            messagebox.showerror("Error", recv_data['msg'])
            root.destroy()
            return False
        if online_list_recv_state:
            return False
    return False


def online_list_recv():
    global online_ips, online_list_recv_state, screen, game_state, games, online_list, game_receive_state
    while online_list:
        recv_data = game_socket.receive()
        print(recv_data, "???")
        if not recv_data:
            break

        if recv_data['type'] == 'challenge':
            recv_true = True

            def recv_():
                recv = ''
                while recv_true:
                    recv = game_socket.receive()
                return recv
            recv_threading = threading.Thread(target=recv_)
            recv_threading.daemon = True
            recv_threading.start()
            select = messagebox.askyesno(title="是或否", message=f"是否接受{recv_data['challenger']}的挑战？")
            print(select)
            if select:
                # 接受挑战
                game_socket.accept_challenge(recv_data['challenger'])
                games = True
                online_list = False
                recv_true = False
                break
            else:
                # 拒绝挑战
                game_socket.refuse_challenge(recv_data['challenger'])
                recv_true = False

        elif recv_data['type'] == 'online list':
            online_ips = recv_data['data']
            online_list_recv_state = False
            return recv_data['data']
    return False


def game_receive():
    global game_receive_state, game_state
    recv_data = game_socket.receive()
    game.add_ops([[recv_data['x'], recv_data['y']], recv_data['color']])
    game_state = recv_data['game']
    # 接收到数据，将接收状态改为False
    game_receive_state = False
    return recv_data


# 首页
window_size = window_x, window_y = 800, 480
screen = pygame.display.set_mode(window_size)
pygame.display.set_caption('五子棋 LAN-Gobang v2.0')
screen_color = [85, 81, 255]  # 设置在线列表画布颜色

game_receive_threading = threading.Thread(target=game_receive)

# 选择指针坐标
pointer_y = 120

# 在线列表数据（模拟）
online_ips = []

# 系统路径
dir_path = os.path.split(os.path.realpath(__file__))[0]

# 设置字体
font = pygame.font.Font(dir_path + '/data/Ya_hei.ttf', 30)

# 加载图片
icon = pygame.image.load(dir_path + '/data/log.ico')
bg = pygame.image.load(dir_path + '/data/Gobang800x480.png')
online_list_bg = pygame.image.load(dir_path + '/data/online_list.png')  # 439x480
pygame.display.set_icon(icon)  # 设置图标

# 显示字
text = font.render("轻按F1开始游戏", True, (255, 255, 255))
text_reset = font.render("F3-重置", True, (255, 255, 255))
text_online_list = font.render("在线列表", True, (255, 255, 255))
text_bind = font.render("等待连接···", True, (255, 255, 255))
text_now = font.render("轮到你了", True, (255, 255, 255))
text_wait = font.render("对手正在思考··", True, (255, 255, 255))
text_white = font.render("你执白子", True, (255, 255, 255))
text_black = font.render("你执黑子", True, (255, 255, 255))
text_white_win = font.render("执白子胜！", True, (255, 255, 255))
text_black_win = font.render("执黑子胜！", True, (255, 255, 255))

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        if event.type == pygame.KEYDOWN:
            print(event)
            # 按下了f1
            if event.key == 1073741882:
                connect_windows()

    while online_list:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.KEYDOWN:
                print(event)
                if event.key == 1073741906:
                    # 上方向键
                    pointer_y -= 30
                if event.key == 1073741905:
                    # 下方向键
                    pointer_y += 30
                # 上限和下限
                if pointer_y < 120:
                    pointer_y += 30
                if pointer_y >= (120 + len(online_ips) * 30):
                    pointer_y -= 30

                if event.key == 13:
                    # 确认连接
                    num = int((pointer_y - 120) / 30)
                    connect_game_windows(online_ips[num])

        screen.fill(screen_color)  # 清屏
        screen.blit(online_list_bg, (0, 0))
        screen.blit(text_online_list, (560, 30))

        if not online_list_recv_state:
            # 开启列表接收线程
            online_list_recv_state = True
            game_receive_threading = threading.Thread(target=online_list_recv)
            game_receive_threading.daemon = True
            game_receive_threading.start()

        if online_ips:
            # 当列表不为空时,显示在线列表
            pygame.draw.circle(screen, (255, 0, 0), (475, pointer_y), 8)
            # 在列表中显示在线IP
            for i, ip in enumerate(online_ips):
                text_surface = font.render(ip, True, (0, 0, 0))
                screen.blit(text_surface, (490, 90 + i * 30 + 10))

        pygame.display.flip()

    while games:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.KEYDOWN:
                print(event)
                # 按下了f3
                if event.key == 1073741884:
                    game_state = 0  # 游戏状态 0 - 游戏中  1 - 执黑子赢  2 - 执白子赢
                    game_receive_state = False
                    windows_new = 1
                    games = False
                    online_list = False  # 游戏在线列表显示状态
                    online_list_recv_state = False  # True表示接收线程已开启
                    game_color = False  # False 是黑子 Ture 是白子
                    num = 0
                    # 断开连接
                    game_socket.disconnect()
                    # 重置游戏
                    game.restart()
                    # 重置窗口
                    screen = pygame.display.set_mode(window_size)
                    game_socket = network.GameSocket()

        if windows_new == 1:
            windows_new = 2
            screen = pygame.display.set_mode((900, 670))

        game.fix()
        screen.blit(text_reset, (710, 30))
        if game_color:
            screen.blit(text_white, (710, 600))
        else:
            screen.blit(text_black, (710, 600))
        x, y, color = game.position_state()

        if not game_state:
            # 当game_state为0时,可以落子
            if color and not game_receive_state:
                # 当color为True，game_receive_state为False时可以落子
                screen.blit(text_now, (700, 400))
                game.add_ops([[x, y], color])
                if game.win():
                    # 判断五子连心
                    game_state = 1
                game_socket.fall(x, y, color, game_state, online_ips[num])
                print(game.get_over())
                game_receive_state = True

                if game_receive_state:
                    # 当game_receive_state为True时启动数据接收线程
                    game_receive_threading = threading.Thread(target=game_receive)
                    game_receive_threading.daemon = True
                    game_receive_threading.start()
            if game_receive_state:
                screen.blit(text_wait, (690, 400))
            elif not game_receive_state:
                screen.blit(text_now, (700, 400))

        if game_state == 1:
            # 执黑子赢得游戏
            screen.blit(text_black_win, (690, 300))
        if game_state == 2:
            # 执白子赢得游戏
            screen.blit(text_white_win, (690, 300))

        pygame.display.flip()

    screen.blit(bg, (0, 0))
    screen.blit(text, (520, 395))

    pygame.display.flip()
