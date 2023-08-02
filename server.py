import socket
import threading
import time

all_online = {}
in_the_game = []


class Error:
    NotOnline = {
        'type': 'error',
        'msg': '该用户现在不在线'
    }
    NotSend = {
        'type': 'error',
        'msg': '发送失败，用户已下线'
    }


def broadcast_message():
    global all_online, in_the_game
    while True:
        time.sleep(1)
        for client in list(all_online.keys()):
            # 当主机数为1时，不发送
            if len(all_online) == 1:
                break
            if client in in_the_game:
                continue
            # 删除它自己的ip
            online = []
            for client_ in list(all_online.keys()):
                online.append(client_)
            online.remove(client)
            message = {
                'type': 'online list',
                'data': online
            }
            try:
                all_online[client].send(str(message).encode())
            except:
                # 发送失败，说明该客户端已断开连接，将其移出列表
                all_online.pop(client, None)
                print(f'err: send -> {client} : {Error.NotSend}list')


def handle_client(client_socket, addr):
    global all_online
    native_url = f'{addr[0]}:{addr[1]}'
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            # 在这里处理客户端发送的数据
            data = eval(data)
            if data['type'] == 'challenge':
                # 发起挑战
                if data['url'] in all_online:
                    # 如果被挑战者在在线名单里，就向它发送战书
                    msg = {
                        'type': "challenge",
                        'challenger': native_url
                    }
                    try:
                        all_online[data['url']].send(str(msg).encode())
                        print(f'send -> {data["url"]} : {msg}')
                    except:
                        # 如果发送失败就输出错误
                        all_online.pop(data['url'], None)
                        client_socket.send(str(Error.NotSend).encode())
                        print(f'err: send -> {data["url"]} : {msg}')

                else:

                    try:
                        client_socket.send(str(Error.NotOnline).encode())
                        print(f'send -> {native_url} : {Error.NotOnline}')
                    except:
                        print(f'err: send -> {native_url} : {Error.NotOnline}')

            if data['type'] == 'Accept challenge' or data['type'] == 'Refuse challenge':

                # 转发
                if data['url'] in all_online:

                    try:
                        all_online[data['url']].send(str(data).encode())
                        print(f'send -> {data["url"]} : {data}')
                        if data['type'] == 'Accept challenge' and data['url'] not in in_the_game:
                            in_the_game.append(data['url'])
                            in_the_game.append(native_url)
                    except:
                        all_online.pop(data['url'], None)
                        client_socket.send(str(Error.NotSend).encode())
                        print(f'err: send -> {data["url"]} : {data}')

                else:

                    try:
                        client_socket.send(str(Error.NotOnline).encode())
                        print(f'send -> {native_url} : {Error.NotOnline}')
                    except:
                        print(f'err: send -> {native_url} : {Error.NotOnline}')

            if data['type'] == 'game':
                # 转发
                if data['url'] in all_online:

                    try:
                        all_online[data['url']].send(str(data).encode())
                        print(f'send -> {data["url"]} : {data}')
                    except:
                        all_online.pop(data['url'], None)
                        client_socket.send(str(Error.NotSend).encode())
                        print(f'err: send -> {data["url"]} : {data}')

                else:

                    try:

                        client_socket.send(str(Error.NotOnline).encode())
                        print(f'send -> {native_url} : {Error.NotOnline}')
                    except:
                        print(f'err: send -> {native_url} : {Error.NotOnline}')


    except:
        # 处理客户端断开连接或其他异常
        if native_url in in_the_game and data['url'] in in_the_game:
            in_the_game.remove(native_url)
            in_the_game.remove(data['url'])
        all_online.pop(native_url, None)
        print(f'err: {native_url} : {Error.NotSend}end')


def main():
    global all_online
    host = '127.0.0.1'
    port = 45555

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)

    print("Server listening on {}:{}".format(host, port))

    # 向其他客户端广播新连接的IP地址
    broadcast_message_threading = threading.Thread(target=broadcast_message)
    broadcast_message_threading.daemon = True
    broadcast_message_threading.start()

    try:
        while True:
            client_socket, addr = server.accept()
            print("Accepted connection from {}:{}".format(addr[0], addr[1]))

            # 将客户端连接加入字典
            all_online.update({f"{addr[0]}:{addr[1]}": client_socket})
            print(all_online)

            # 启动一个新的线程来处理当前连接的客户端
            client_thread = threading.Thread(target=handle_client, args=(client_socket, addr))
            client_thread.start()
    except KeyboardInterrupt:
        print("Server is shutting down...")
        for client_socket in all_online:
            all_online[client_socket].close()
        server.close()


if __name__ == "__main__":
    main()
