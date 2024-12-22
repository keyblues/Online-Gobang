import asyncio
import websockets
import json
from dataclasses import dataclass
from typing import Dict, Set

@dataclass
class Room:
    id: str
    players: Set[str]
    game_state: dict
    game_started: bool = False

class GameServer:
    def __init__(self):
        self.connections = {}
        self.rooms = {
            str(i): Room(
                id=str(i),
                players=set(),
                game_state={'board': [[0]*15 for _ in range(15)], 'current_player': 1}
            ) for i in range(1, 6)
        }
    
    async def broadcast_room_status(self):
        room_status = {
            room_id: {
                'player_count': len(room.players)
            }
            for room_id, room in self.rooms.items()
        }
        
        for websocket in self.connections.values():
            try:
                await websocket.send(json.dumps({
                    'action': 'room_status',
                    'rooms': room_status
                }))
            except:
                pass
    
    async def handle_connection(self, websocket):
        client_id = str(id(websocket))
        self.connections[client_id] = websocket
        print(f"New client connected: {client_id}")
        
        await self.broadcast_room_status()
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    response = await self.handle_message(client_id, data)
                    if response:
                        await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    print(f"Invalid JSON from client {client_id}")
                except Exception as e:
                    print(f"Error handling message from {client_id}: {str(e)}")
        except websockets.exceptions.ConnectionClosed:
            print(f"Client {client_id} connection closed")
        finally:
            await self.handle_disconnect(client_id)
    
    async def handle_message(self, client_id: str, data: dict):
        action = data.get('action')
        print(f"Handling action: {action} from client: {client_id}")
        
        if action == 'join_room':
            room_id = data.get('room_id')
            if room_id in self.rooms:
                room = self.rooms[room_id]
                if len(room.players) < 2:
                    is_first = len(room.players) == 0  # 第一个玩家是黑方
                    room.players.add(client_id)
                    print(f"Player {client_id} joined room {room_id} as {'black' if is_first else 'white'}")
                    await self.broadcast_room_status()
                    
                    # 发送加入成功消息给当前玩家
                    response = {
                        'action': 'join_success',
                        'room_id': room_id,
                        'is_first': is_first,
                        'role': 'black' if is_first else 'white'
                    }
                    
                    # 如果房间满员，立即向双方发送游戏开始消息
                    if len(room.players) == 2:
                        room.game_started = True
                        players = list(room.players)
                        # 先单独发送游戏开始消息
                        for i, pid in enumerate(players):
                            await self.connections[pid].send(json.dumps({
                                'action': 'game_start',
                                'is_first': i == 0,
                                'room_id': room_id
                            }))
                            print(f"Sent game_start to player {pid} as {'black' if i == 0 else 'white'}")
                    
                    return response
            return {'action': 'join_failed'}
        
        elif action == 'exit_room':
            room_id = data.get('room_id')
            if room_id in self.rooms:
                room = self.rooms[room_id]
                if client_id in room.players:
                    room.players.remove(client_id)
                    room.game_started = False
                    await self.broadcast_room_status()
                    await self.broadcast_to_room(room_id, {
                        'action': 'player_disconnected'
                    })
                    return {'action': 'exit_success'}
        
        elif action == 'move':
            room_id = data.get('room_id')
            x, y = data.get('x'), data.get('y')
            if room_id in self.rooms:
                room = self.rooms[room_id]
                board = room.game_state['board']
                current_player = room.game_state['current_player']
                
                if board[y][x] == 0:
                    board[y][x] = current_player
                    room.game_state['current_player'] = 3 - current_player
                    await self.broadcast_to_room(room_id, {
                        'action': 'move',
                        'x': x,
                        'y': y,
                        'player': current_player
                    })
                    
                    if self.check_winner(board, x, y, current_player):
                        await self.broadcast_to_room(room_id, {
                            'action': 'game_over',
                            'winner': '黑棋' if current_player == 1 else '白棋'
                        })
                        room.game_started = False
    
    def check_winner(self, board, x, y, player):
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            count += self.count_pieces(board, x, y, dx, dy, player)
            count += self.count_pieces(board, x, y, -dx, -dy, player)
            if count >= 5:
                return True
        return False
    
    def count_pieces(self, board, x, y, dx, dy, player):
        count = 0
        nx, ny = x + dx, y + dy
        while 0 <= nx < len(board) and 0 <= ny < len(board) and board[ny][nx] == player:
            count += 1
            nx += dx
            ny += dy
        return count
    
    async def broadcast_to_room(self, room_id: str, message: dict, exclude=None):
        """向房间内所有玩家广播消息"""
        if room_id in self.rooms:
            room = self.rooms[room_id]
            for player_id in room.players:
                if player_id != exclude and player_id in self.connections:
                    await self.connections[player_id].send(json.dumps(message))
    
    async def handle_disconnect(self, client_id: str):
        if client_id in self.connections:
            del self.connections[client_id]
        
        for room in self.rooms.values():
            if client_id in room.players:
                room.players.remove(client_id)
                await self.broadcast_room_status()
                await self.broadcast_to_room(room.id, {
                    'action': 'player_disconnected'
                })

async def main():
    server = GameServer()
    async with websockets.serve(
        server.handle_connection,
        "localhost",
        8765,
        ping_interval=None
    ) as websocket_server:
        print("Server started on ws://localhost:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
