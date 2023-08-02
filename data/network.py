import socket


class GameSocket:
    def __init__(self):
        self.Socket = socket.socket()

    def connect(self, ip, port):
        # client
        self.Socket.connect((ip, port))

    def connect_game(self, ip):
        # 发起挑战
        msg = {
            'type': 'challenge',
            'url': ip
        }
        self.Socket.send(str(msg).encode())
        print(f'send -> {ip} : {msg}')

    def accept_challenge(self, ip):
        # 接受挑战
        msg = {
            'type': 'Accept challenge',
            'url': ip
        }
        self.Socket.send(str(msg).encode())
        print(f'send -> {ip} : {msg}')

    def refuse_challenge(self, ip):
        # 放弃挑战
        msg = {
            'type': 'Refuse challenge',
            'url': ip
        }
        self.Socket.send(str(msg).encode())
        print(f'send -> {ip} : {msg}')

    def bind(self, ip, port):
        # server
        self.Socket.bind((ip, port))
        self.Socket.listen(5)
        sock, addr = self.Socket.accept()
        self.Socket = sock
        return sock

    def fall(self, coordinate_x, coordinate_y, piece_color, game_state, ip):
        # 初始化落子数据
        data = {
            'type': 'game',
            "x": coordinate_x,
            "y": coordinate_y,
            "color": piece_color,
            "game": game_state,
            "url": ip
        }
        text = str(data)
        print('发送：', text)
        # 向对手发送落子数据
        self.Socket.send(text.encode())

    def receive(self):
        # 接收数据
        receive_data = self.Socket.recv(2048).decode()
        # 格式化接收到的数据
        try:
            format_data = eval(receive_data)
        except:
            print('error: format_data = eval(receive_data) \n data:', receive_data)
            return False
        return format_data

    def disconnect(self):
        self.Socket.close()
