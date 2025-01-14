import asyncio
import websockets
import json
from dataclasses import dataclass
from typing import Dict, Set

class Room:
    def __init__(self, id: str):
        self.id = id
        self.players = set()
        self.reset_game_state()
    
    def reset_game_state(self):
        """重置房间的游戏状态"""
        self.game_started = False
        self.game_state = {
            'board': [[0]*15 for _ in range(15)],
            'current_player': 1,
            'last_move': None
        }

class GameServer:
    def __init__(self):
        self.connections = {}
        self.rooms = {
            str(i): Room(str(i)) for i in range(1, 6)
        }
        self.broadcast_task = None
    
    async def start_broadcast_task(self):
        while True:
            await self.broadcast_room_status()
            await asyncio.sleep(1)  # 每秒更新一次状态
    
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
        
        if not self.broadcast_task:
            self.broadcast_task = asyncio.create_task(self.start_broadcast_task())
        
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
        try:
            action = data.get('action')
            print(f"处理消息: action={action}, client={client_id}")
            
            if not action:
                return {'action': 'error', 'message': 'invalid_action'}

            if action == 'join_room':
                room_id = data.get('room_id')
                if room_id in self.rooms:
                    room = self.rooms[room_id]
                    if len(room.players) < 2:
                        is_first = len(room.players) == 0
                        # 如果是第一个玩家加入，重置房间状态
                        if is_first:
                            room.reset_game_state()
                        room.players.add(client_id)
                        
                        await self.broadcast_room_status()
                        
                        # 发送房间当前状态给新加入的玩家
                        response = {
                            'action': 'join_success',
                            'room_id': room_id,
                            'is_first': is_first,
                            'role': 'black' if is_first else 'white',
                            'game_state': room.game_state
                        }
                        
                        if len(room.players) == 2:
                            room.game_started = True
                            # 重新发送游戏开始状态
                            await self.broadcast_to_room(room_id, {
                                'action': 'game_start',
                                'game_state': room.game_state
                            })
                        
                        return response
                return {'action': 'join_failed'}

            elif action == 'exit_room':
                room_id = data.get('room_id')
                if room_id in self.rooms:
                    room = self.rooms[room_id]
                    if client_id in room.players:
                        room.players.remove(client_id)
                        room.reset_game_state()
                        await self.broadcast_room_status()
                        await self.broadcast_to_room(room_id, {
                            'action': 'player_disconnected'
                        })
                        return {'action': 'exit_success'}
            
            elif action == 'move':
                try:
                    room_id = data.get('room_id')
                    x = int(data.get('x', -1))
                    y = int(data.get('y', -1))
                    
                    print(f"收到移动请求: room={room_id}, x={x}, y={y}")
                    
                    room = self.rooms.get(room_id)
                    if not room:
                        return {'action': 'move_failed', 'reason': 'room_not_found'}
                    
                    if not room.game_started:
                        return {'action': 'move_failed', 'reason': 'game_not_started'}
                    
                    if len(room.players) != 2:
                        return {'action': 'move_failed', 'reason': 'waiting_for_player'}
                    
                    players = list(room.players)
                    player_index = players.index(client_id) if client_id in players else -1
                    current_player = room.game_state['current_player']
                    
                    print(f"移动验证: player_index={player_index}, current_player={current_player}")
                    
                    # 检查是否是当前玩家的回合
                    expected_player = 1 if player_index == 0 else 2
                    if current_player != expected_player:
                        print(f"回合错误: expected={expected_player}, current={current_player}")
                        return {'action': 'move_failed', 'reason': 'not_your_turn'}
                    
                    board = room.game_state['board']
                    
                    # 验证坐标和位置是否有效
                    if not (0 <= x < 15 and 0 <= y < 15):
                        print("无效位置")
                        return {'action': 'move_failed', 'reason': 'invalid_position'}
                    
                    if board[y][x] != 0:
                        print("位置已被占用")
                        return {'action': 'move_failed', 'reason': 'position_occupied'}
                    
                    # 落子成功，更新状态
                    board[y][x] = current_player
                    room.game_state['current_player'] = 3 - current_player
                    room.game_state['last_move'] = (x, y)
                    
                    print(f"落子成功: x={x}, y={y}, player={current_player}")
                    
                    # 广播移动消息
                    await self.broadcast_to_room(room_id, {
                        'action': 'move',
                        'x': x,
                        'y': y,
                        'player': current_player
                    })
                    
                    # 检查胜负
                    if self.check_winner(board, x, y, current_player):
                        await self.broadcast_to_room(room_id, {
                            'action': 'game_over',
                            'winner': '黑棋' if current_player == 1 else '白棋',
                            'winning_move': (x, y)
                        })
                        room.reset_game_state()
                    
                except Exception as e:
                    print(f"处理移动时出错: {e}")
                    return {'action': 'move_failed', 'reason': str(e)}
            
            elif action == 'game_over':
                room_id = data.get('room_id')
                if room_id in self.rooms:
                    room = self.rooms[room_id]
                    room.reset_game_state()
                    await self.broadcast_to_room(room_id, {
                        'action': 'game_state',
                        'state': room.game_state
                    })
            
        except Exception as e:
            print(f"Error handling message: {e}")
            import traceback
            traceback.print_exc()
            return {'action': 'error', 'message': str(e)}
    
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
                    try:
                        await self.connections[player_id].send(json.dumps(message))
                    except Exception as e:
                        print(f"Error broadcasting to {player_id}: {e}")
    
    async def handle_disconnect(self, client_id: str):
        if client_id in self.connections:
            del self.connections[client_id]
        
        for room in self.rooms.values():
            if client_id in room.players:
                room.players.remove(client_id)
                room.reset_game_state()
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
        ping_timeout=None,  # 禁用ping超时
        ping_interval=None  # 禁用ping间隔
    ) as websocket_server:
        print("Server started on ws://localhost:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
