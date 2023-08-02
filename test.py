import socket

def main():
    server_host = '127.0.0.1'  # 服务器的IP地址
    server_port = 45555       # 服务器的端口号

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # 连接到服务器
        client_socket.connect((server_host, server_port))

        while True:
            # 接收服务器返回的消息
            response = client_socket.recv(1024)
            print("服务器回复: {}".format(response.decode()))
    except ConnectionRefusedError:
        print("连接失败：无法连接到服务器。")
    except KeyboardInterrupt:
        print("客户端关闭。")
    finally:
        # 关闭套接字
        client_socket.close()

if __name__ == "__main__":
    main()
