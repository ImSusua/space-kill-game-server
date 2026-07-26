"""
Main game server - implements HTTP login, Gate/RPC TCP, and Scene TCP servers.
"""
import socket
import threading
import time
import struct
import hashlib
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from pb import PBReader, decode_varint, encode_varint
from config import *
import messages as msg

# Player database (in-memory)
players = {}
player_id_counter = 1000000

# Active gate sessions
gate_sessions = {}

# Active scene rooms
scene_rooms = {}

# Scene player positions
scene_players = {}


def generate_player_id():
    global player_id_counter
    player_id_counter += 1
    return player_id_counter


def generate_gate_key(player_id):
    """Generate a gate key for the player."""
    return hashlib.md5(f"gate_{player_id}_{time.time()}".encode()).hexdigest()


def generate_scene_key(player_id):
    """Generate a scene key for the player."""
    return hashlib.md5(f"scene_{player_id}_{time.time()}".encode()).hexdigest()


def get_or_create_player(device_id, account="", password=""):
    """Get or create a player by device ID or account."""
    global player_id_counter

    # Try to find by account
    if account and account in players:
        return players[account]

    # Try to find by device
    for p in players.values():
        if p.get('device') == device_id:
            return p

    # Create new player
    pid = generate_player_id()
    if not account:
        account = f"Player_{pid}"

    player = {
        'id': pid,
        'account': account,
        'password': password,
        'device': device_id,
        'name': account,
        'gate_key': '',
        'scene_key': '',
        'color_id': 1,
        'clothes': [],
        'level': 1,
        'cup_num': 0,
        'cookie': 10000,
        'donut': 100,
        'pai': 100,
        'space_num': 1,
    }
    players[account] = player
    return player


# ==================== HTTP Login Server ====================

class LoginHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        if len(body) < 12:
            self.send_response(400)
            self.end_headers()
            return

        # Parse HTTP protocol header
        # Bytes 0-1: module (little-endian)
        # Bytes 2-3: cmd (little-endian)
        # Bytes 4-11: uid (little-endian)
        # Bytes 12+: PbObj data
        module = body[0] | (body[1] << 8)
        cmd = body[2] | (body[3] << 8)
        uid = int.from_bytes(body[4:12], 'little')
        pb_data = body[12:]

        print(f"[HTTP] module={module} cmd={cmd} uid={uid} data_len={len(pb_data)}")

        response_data = None
        err_code = 0

        if module == ModuleType.Login:
            if cmd == LoginCmd.Login:
                response_data, err_code = self.handle_login(pb_data, uid)
            elif cmd == LoginCmd.StartGame:
                response_data, err_code = self.handle_start_game(pb_data, uid)
            elif cmd == LoginCmd.Bind:
                response_data = b''
            elif cmd == LoginCmd.VerificationCode:
                response_data = b''
            elif cmd == LoginCmd.ResetPasswordLogout:
                response_data = b''
            elif cmd == LoginCmd.BindThird:
                response_data = b''
            elif cmd == LoginCmd.ThirdShareId:
                response_data = b''
            else:
                response_data = b''
        else:
            # Other HTTP modules - return empty success
            response_data = b''

        if err_code != 0:
            resp = msg.encode_error_response(err_code)
        else:
            resp = msg.encode_http_success(response_data or b'')

        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(resp)))
        self.send_header('Set-Cookie', f'session={generate_gate_key(uid)}; Path=/')
        self.end_headers()
        self.wfile.write(resp)

    def handle_login(self, pb_data, uid):
        """Handle login request."""
        # Parse ReqLoginMsg
        device = ""
        account = ""
        password = ""

        try:
            reader = PBReader(pb_data)
            while reader.has_more():
                field_num, wire_type = reader.read_tag()
                if field_num == 1 and wire_type == 2:  # Device
                    device = reader.read_string()
                elif field_num == 2 and wire_type == 2:  # Account
                    account = reader.read_string()
                elif field_num == 3 and wire_type == 2:  # Password
                    password = reader.read_string()
                elif field_num == 4 and wire_type == 0:  # Version
                    reader.read_varint()
                else:
                    reader.skip_field(wire_type)
        except Exception as e:
            print(f"[HTTP] Login parse error: {e}")

        player = get_or_create_player(device, account, password)
        gate_key = generate_gate_key(player['id'])
        player['gate_key'] = gate_key
        gate_sessions[gate_key] = player

        print(f"[HTTP] Login OK: pid={player['id']} account={player['account']}")

        ret_data = msg.encode_ret_login_msg(
            player_id=player['id'],
            account=player['account'],
            gate_addr=GATE_ADDR,
            gate_key=gate_key,
            is_bind=False
        )
        return ret_data, 0

    def handle_start_game(self, pb_data, uid):
        """Handle start game request."""
        mtype = 0
        room_id = 0
        seat_number = 0

        try:
            reader = PBReader(pb_data)
            while reader.has_more():
                field_num, wire_type = reader.read_tag()
                if field_num == 1 and wire_type == 0:  # MType
                    mtype = reader.read_varint()
                elif field_num == 2 and wire_type == 0:  # RoomId
                    room_id = reader.read_varint()
                elif field_num == 3 and wire_type == 0:  # SeatNumber
                    seat_number = reader.read_varint()
                else:
                    reader.skip_field(wire_type)
        except Exception as e:
            print(f"[HTTP] StartGame parse error: {e}")

        # Find player by uid
        player = None
        for p in players.values():
            if p['id'] == uid:
                player = p
                break

        if not player:
            # Create a temporary player
            player = get_or_create_player(f"uid_{uid}", f"Player_{uid}")

        scene_key = generate_scene_key(player['id'])
        player['scene_key'] = scene_key

        # Create a scene room
        room_id_new = len(scene_rooms) + 1
        scene_rooms[room_id_new] = {
            'id': room_id_new,
            'players': {},
            'scene_key': scene_key,
            'player_keys': {scene_key: player['id']},
        }

        print(f"[HTTP] StartGame OK: uid={uid} room_addr={SCENE_ADDR}")

        ret_data = msg.encode_ret_start_game(
            room_addr=SCENE_ADDR,
            room_key=scene_key
        )
        return ret_data, 0


def start_http_server():
    """Start the HTTP login server."""
    server = HTTPServer(('0.0.0.0', HTTP_PORT), LoginHandler)
    print(f"[HTTP] Login server started on port {HTTP_PORT}")
    server.serve_forever()


# ==================== Gate/RPC TCP Server ====================

class GateClient:
    """Represents a connected gate client."""
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.player_id = 0
        self.player = None
        self.recv_buf = bytearray()
        self.lock = threading.Lock()

    def send_rpc_response(self, sid, pb_data, flag=0x00):
        """Send an RPC response to the client.

        RPC TCP format (server → client):
        - 3 bytes: total_size (big-endian) = 8 + len(pb_data)
        - 1 byte: flag (0=normal, 0x08=error, 0x20=push)
        - 4 bytes: sid (big-endian)
        - N bytes: pb_data
        """
        total_size = 8 + len(pb_data)
        header = struct.pack('>I', (total_size << 8) | flag)[:3] + bytes([flag])
        sid_bytes = struct.pack('>I', sid)
        data = header + sid_bytes + pb_data
        try:
            with self.lock:
                self.conn.sendall(data)
        except Exception as e:
            print(f"[Gate] Send error: {e}")

    def send_rpc_push(self, handle_id, pb_data):
        """Send a push message to the client."""
        total_size = 8 + len(pb_data)
        flag = 0x20  # Push flag (bit 5)
        header = struct.pack('>I', (total_size << 8) | flag)[:3] + bytes([flag])
        sid_bytes = struct.pack('>I', handle_id)
        data = header + sid_bytes + pb_data
        try:
            with self.lock:
                self.conn.sendall(data)
        except Exception as e:
            print(f"[Gate] Push send error: {e}")

    def send_rpc_error(self, sid, err_code):
        """Send an error response."""
        total_size = 8 + 2  # sid(4) + errcode(2)
        flag = 0x08  # Error flag (bit 3)
        header = struct.pack('>I', (total_size << 8) | flag)[:3] + bytes([flag])
        sid_bytes = struct.pack('>I', sid)
        err_bytes = struct.pack('>H', err_code)
        data = header + sid_bytes + err_bytes
        try:
            with self.lock:
                self.conn.sendall(data)
        except Exception as e:
            print(f"[Gate] Error send error: {e}")


def handle_gate_client(client):
    """Handle a gate client connection."""
    print(f"[Gate] Client connected: {client.addr}")

    try:
        while True:
            data = client.conn.recv(4096)
            if not data:
                break

            client.recv_buf.extend(data)

            # Process complete messages
            while len(client.recv_buf) >= 4:
                # RPC TCP format (client → server):
                # 3 bytes: total_size (big-endian) = obj.Size() + 12
                # 1 byte: flag
                # 2 bytes: module (big-endian)
                # 2 bytes: cmd (big-endian)
                # 4 bytes: sid (big-endian)
                # N bytes: pb_data

                total_size = (client.recv_buf[0] << 16) | (client.recv_buf[1] << 8) | client.recv_buf[2]
                flag = client.recv_buf[3]

                if len(client.recv_buf) < total_size:
                    break  # Wait for more data

                if total_size < 12:
                    print(f"[Gate] Invalid message size: {total_size}")
                    client.recv_buf = client.recv_buf[total_size:]
                    continue

                module = (client.recv_buf[4] << 8) | client.recv_buf[5]
                cmd = (client.recv_buf[6] << 8) | client.recv_buf[7]
                sid = struct.unpack('>I', bytes(client.recv_buf[8:12]))[0]
                pb_data = bytes(client.recv_buf[12:total_size])

                # Remove processed message
                client.recv_buf = client.recv_buf[total_size:]

                print(f"[Gate] module={module} cmd={cmd} sid={sid} data_len={len(pb_data)}")

                handle_rpc_message(client, module, cmd, sid, pb_data)

    except Exception as e:
        print(f"[Gate] Client error: {e}")
    finally:
        print(f"[Gate] Client disconnected: {client.addr}")
        try:
            client.conn.close()
        except:
            pass


def handle_rpc_message(client, module, cmd, sid, pb_data):
    """Handle an RPC message from the client."""

    # Gate service commands
    if module == ModuleType.GateService:
        if cmd == GateCmd.GateLogin:
            handle_gate_login(client, sid, pb_data)
        elif cmd == GateCmd.HeartBeat:
            client.send_rpc_response(sid, msg.encode_ret_heartbeat())
        elif cmd == GateCmd.Betick:
            client.send_rpc_response(sid, msg.encode_ret_betick(int(time.time())))
        elif cmd == GateCmd.GateErrCode:
            client.send_rpc_response(sid, b'')
        else:
            client.send_rpc_response(sid, b'')
        return

    # User module
    if module == ModuleType.User:
        if cmd == UserCmd.GetRoleDetail:
            handle_get_role_detail(client, sid, pb_data)
        elif cmd == UserCmd.LogicOnline:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.LogicOffline:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.RegisterAcc:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.GetBoxStoreHouse:
            client.send_rpc_response(sid, msg.encode_ret_get_box_store_house())
        elif cmd == UserCmd.GetDailyChose:
            client.send_rpc_response(sid, msg.encode_ret_get_daily_chose())
        elif cmd == UserCmd.PlayerOccupations:
            client.send_rpc_response(sid, msg.encode_ret_player_occupations())
        elif cmd == UserCmd.PlayerClothes:
            client.send_rpc_response(sid, msg.encode_ret_player_clothes())
        elif cmd == UserCmd.GetSimUserInfo:
            client.send_rpc_response(sid, msg.encode_ret_get_sim_user_info())
        elif cmd == UserCmd.GetUserPage:
            client.send_rpc_response(sid, msg.encode_ret_get_user_page())
        elif cmd == UserCmd.GetUserGamePage:
            client.send_rpc_response(sid, msg.encode_ret_get_user_game_page())
        elif cmd == UserCmd.GetLikeRecord:
            client.send_rpc_response(sid, msg.encode_ret_get_like_record())
        elif cmd == UserCmd.GetVisiteRecord:
            client.send_rpc_response(sid, msg.encode_ret_get_visite_record())
        elif cmd == UserCmd.InteractRecord:
            client.send_rpc_response(sid, msg.encode_ret_interact_record())
        elif cmd == UserCmd.NewMessage:
            client.send_rpc_response(sid, msg.encode_ret_new_message())
        elif cmd == UserCmd.GetUserState:
            client.send_rpc_response(sid, msg.encode_ret_get_user_state())
        elif cmd == UserCmd.IdCardVerify:
            client.send_rpc_response(sid, msg.encode_ret_id_card_verify())
        elif cmd == UserCmd.SetUserSetting:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.SetColor:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.SetAttackEffect:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.SetAge:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.SetSex:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.SetSign:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.ChangeAccount:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.VerifyPasswd:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.ChangePasswd:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.GetPhotoList:
            client.send_rpc_response(sid, msg.encode_ret_get_photo_list())
        elif cmd == UserCmd.HeadUser:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.InitAbility:
            client.send_rpc_response(sid, b'')
        elif cmd == UserCmd.InitAgeLevel:
            client.send_rpc_response(sid, b'')
        else:
            client.send_rpc_response(sid, b'')
        return

    # Relation module
    if module == ModuleType.Relation:
        if cmd == RelationCmd.GetSvrTime:
            svr_time = int(time.time())
            client.send_rpc_response(sid, msg.encode_ret_get_svr_time(svr_time))
        elif cmd == RelationCmd.FollowList:
            client.send_rpc_response(sid, msg.encode_ret_follow_list())
        elif cmd == RelationCmd.FansList:
            client.send_rpc_response(sid, msg.encode_ret_fans_list())
        elif cmd == RelationCmd.FriendList:
            client.send_rpc_response(sid, msg.encode_ret_friend_list())
        elif cmd == RelationCmd.NewFansStat:
            client.send_rpc_response(sid, msg.encode_ret_new_fans_stat())
        elif cmd == RelationCmd.AddFollow:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.CancelFollow:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.FollowState:
            client.send_rpc_response(sid, msg.encode_ret_follow_state())
        elif cmd == RelationCmd.BatchRelation:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.RecentGamer:
            client.send_rpc_response(sid, msg.encode_ret_recent_gamer())
        elif cmd == RelationCmd.SearchAccount:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.ReadNewMessage:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.SkipNewFans:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.AddAlias:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.RecommendList:
            client.send_rpc_response(sid, msg.encode_ret_recommend_list())
        elif cmd == RelationCmd.RecommendPlayers:
            client.send_rpc_response(sid, b'')
        elif cmd == RelationCmd.GetTheInviter:
            client.send_rpc_response(sid, msg.encode_ret_get_the_inviter())
        elif cmd == RelationCmd.NoticeFollow:
            client.send_rpc_response(sid, b'')
        else:
            client.send_rpc_response(sid, b'')
        return

    # Bag module
    if module == ModuleType.Bag:
        if cmd == BagCmd.GetBagData:
            client.send_rpc_response(sid, msg.encode_ret_get_bag_data())
        elif cmd == BagCmd.UseItem:
            client.send_rpc_response(sid, b'')
        elif cmd == BagCmd.UpdateOccupation:
            client.send_rpc_response(sid, b'')
        elif cmd == BagCmd.ChangeOccCard:
            client.send_rpc_response(sid, b'')
        else:
            client.send_rpc_response(sid, b'')
        return

    # Room module
    if module == ModuleType.Room:
        if cmd == RoomCmd.RoomList:
            client.send_rpc_response(sid, msg.encode_ret_room_list())
        elif cmd == RoomCmd.TypeRoomList:
            client.send_rpc_response(sid, b'')
        elif cmd == RoomCmd.RoomOperate:
            client.send_rpc_response(sid, b'')
        elif cmd == RoomCmd.RoomPlayerOpState:
            client.send_rpc_response(sid, b'')
        elif cmd == RoomCmd.Praise:
            client.send_rpc_response(sid, b'')
        else:
            client.send_rpc_response(sid, b'')
        return

    # Shop module
    if module == ModuleType.Shop:
        client.send_rpc_response(sid, b'')
        return

    # Chat module
    if module == ModuleType.Chat:
        client.send_rpc_response(sid, b'')
        return

    # BBS module
    if module == ModuleType.BBS:
        if cmd == BBSCmd.GetMsgBoard:
            client.send_rpc_response(sid, msg.encode_ret_get_msg_board())
        elif cmd == BBSCmd.GetMsgBoardTop:
            client.send_rpc_response(sid, msg.encode_ret_get_msg_board_top())
        elif cmd == BBSCmd.GetMsgBoardHot:
            client.send_rpc_response(sid, msg.encode_ret_get_msg_board_hot())
        elif cmd == BBSCmd.GetUserLeaveMsg:
            client.send_rpc_response(sid, msg.encode_ret_get_user_leave_msg())
        elif cmd == BBSCmd.GetBBSOpenTo:
            client.send_rpc_response(sid, msg.encode_ret_get_bbs_open_to())
        else:
            client.send_rpc_response(sid, b'')
        return

    # Clothes module
    if module == ModuleType.Clothes:
        client.send_rpc_response(sid, b'')
        return

    # Mail module
    if module == ModuleType.Other:
        if cmd == OtherCmd.GetUserState:
            client.send_rpc_response(sid, msg.encode_ret_get_user_state())
        elif cmd == OtherCmd.IdCardVerify:
            client.send_rpc_response(sid, msg.encode_ret_id_card_verify())
        elif cmd == OtherCmd.Redpoints:
            client.send_rpc_response(sid, b'')
        else:
            client.send_rpc_response(sid, b'')
        return

    # Gift module
    if module == ModuleType.Gift:
        client.send_rpc_response(sid, b'')
        return

    # Newbie module
    if module == ModuleType.Newbie:
        client.send_rpc_response(sid, b'')
        return

    # Activity module
    if module == ModuleType.Activity:
        client.send_rpc_response(sid, b'')
        return

    # Watch module
    if module == ModuleType.Watch:
        client.send_rpc_response(sid, b'')
        return

    # Watcher module
    if module == ModuleType.Watcher:
        client.send_rpc_response(sid, b'')
        return

    # Qualifying module
    if module == ModuleType.Qualifying:
        if cmd == QualifyingCmd.GetQualifyingInfo:
            client.send_rpc_response(sid, msg.encode_ret_qualifying_info())
        else:
            client.send_rpc_response(sid, b'')
        return

    # Rank module
    if module == ModuleType.Rank:
        client.send_rpc_response(sid, b'')
        return

    # UGC module
    if module == ModuleType.UGC:
        client.send_rpc_response(sid, b'')
        return

    # GEO module
    if module == ModuleType.GEO:
        client.send_rpc_response(sid, b'')
        return

    # Team module
    if module == ModuleType.Team:
        client.send_rpc_response(sid, b'')
        return

    # Default: return empty success
    print(f"[Gate] Unknown module={module} cmd={cmd}, returning empty")
    client.send_rpc_response(sid, b'')


def handle_gate_login(client, sid, pb_data):
    """Handle gate login request."""
    gate_key = ""
    try:
        reader = PBReader(pb_data)
        while reader.has_more():
            field_num, wire_type = reader.read_tag()
            if field_num == 1 and wire_type == 2:  # Key
                gate_key = reader.read_string()
            else:
                reader.skip_field(wire_type)
    except Exception as e:
        print(f"[Gate] Login parse error: {e}")

    # Find player by gate key
    player = gate_sessions.get(gate_key)
    if player:
        client.player_id = player['id']
        client.player = player
        print(f"[Gate] Login OK: pid={player['id']} account={player['account']}")
    else:
        # Allow login anyway for testing
        print(f"[Gate] Login with unknown key, allowing anyway")

    # Return empty keys (no encryption)
    ret_data = msg.encode_ret_gate_login()
    client.send_rpc_response(sid, ret_data)


def handle_get_role_detail(client, sid, pb_data):
    """Handle get role detail request."""
    player = client.player
    if not player:
        # Create a default player
        player = get_or_create_player(f"gate_{client.addr[0]}_{client.addr[1]}")
        client.player = player
        client.player_id = player['id']

    ret_data = msg.encode_ret_get_role_detail(
        player_id=player['id'],
        account=player['account'],
        game_name=player.get('name', player['account'])
    )
    client.send_rpc_response(sid, ret_data)
    print(f"[Gate] GetRoleDetail OK: pid={player['id']}")


def start_gate_server():
    """Start the Gate/RPC TCP server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', GATE_PORT))
    server.listen(5)
    print(f"[Gate] RPC server started on port {GATE_PORT}")

    while True:
        conn, addr = server.accept()
        client = GateClient(conn, addr)
        t = threading.Thread(target=handle_gate_client, args=(client,))
        t.daemon = True
        t.start()


# ==================== Scene TCP Server ====================

class SceneClient:
    """Represents a connected scene client."""
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.player_id = 0
        self.player_name = ""
        self.scene_key = ""
        self.room_id = 0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.state = 0
        self.color_id = 1
        self.recv_buf = bytearray()
        self.lock = threading.Lock()

    def send_scene_message(self, module, cmd, pb_data):
        """Send a scene message to the client.

        Scene TCP format (server → client):
        - 3 bytes: body_size (little-endian) = len(pb_data) + 4
        - 1 byte: flag = 0
        - 4 bytes: cmd (big-endian) where cmd = (module << 16) | cmd_id
        - N bytes: pb_data
        """
        body_size = len(pb_data) + 4
        header = bytes([body_size & 0xFF, (body_size >> 8) & 0xFF, (body_size >> 16) & 0xFF, 0])
        cmd_val = (module << 16) | cmd
        cmd_bytes = struct.pack('>I', cmd_val)
        data = header + cmd_bytes + pb_data
        try:
            with self.lock:
                self.conn.sendall(data)
        except Exception as e:
            print(f"[Scene] Send error: {e}")


def handle_scene_client(client):
    """Handle a scene client connection."""
    print(f"[Scene] Client connected: {client.addr}")

    try:
        while True:
            data = client.conn.recv(4096)
            if not data:
                break

            client.recv_buf.extend(data)

            # Process complete messages
            while len(client.recv_buf) >= 4:
                # Scene TCP format (client → server):
                # 3 bytes: body_size (little-endian) = obj.Size() + 4
                # 1 byte: flag
                # 4 bytes: cmd (big-endian) where cmd = (module << 16) | cmd_id
                # N bytes: pb_data

                body_size = client.recv_buf[0] | (client.recv_buf[1] << 8) | (client.recv_buf[2] << 16)
                flag = client.recv_buf[3]

                total_size = body_size + 4  # body_size doesn't include the 4-byte header

                if len(client.recv_buf) < total_size:
                    break  # Wait for more data

                if body_size < 4:
                    print(f"[Scene] Invalid body size: {body_size}")
                    client.recv_buf = client.recv_buf[total_size:]
                    continue

                # Read module and cmd (big-endian)
                module = (client.recv_buf[4] << 8) | client.recv_buf[5]
                cmd = (client.recv_buf[6] << 8) | client.recv_buf[7]
                pb_data = bytes(client.recv_buf[8:total_size])

                # Remove processed message
                client.recv_buf = client.recv_buf[total_size:]

                handle_scene_message(client, module, cmd, pb_data)

    except Exception as e:
        print(f"[Scene] Client error: {e}")
    finally:
        print(f"[Scene] Client disconnected: {client.addr}")
        # Remove from room
        if client.room_id and client.room_id in scene_rooms:
            room = scene_rooms[client.room_id]
            if client.player_id in room['players']:
                del room['players'][client.player_id]
                # Notify other players
                for pid, other_client in room['players'].items():
                    if other_client != client:
                        try:
                            other_client.send_scene_message(ModuleType.Scene, SceneCmd.AddDelPlayer,
                                msg.encode_scene_add_del_player([], [{'id': client.player_id}]))
                        except:
                            pass
        try:
            client.conn.close()
        except:
            pass


def handle_scene_message(client, module, cmd, pb_data):
    """Handle a scene message from the client."""

    if cmd == SceneCmd.Login:
        handle_scene_login(client, pb_data)
    elif cmd == SceneCmd.HeartBeat:
        client.send_scene_message(module, SceneCmd.HeartBeat, msg.encode_scene_heartbeat())
    elif cmd == SceneCmd.Move:
        handle_scene_move(client, pb_data)
    elif cmd == SceneCmd.BatchMove:
        handle_scene_batch_move(client, pb_data)
    elif cmd == SceneCmd.Action:
        pass  # Ignore action for now
    elif cmd == SceneCmd.ChangeState:
        handle_scene_change_state(client, pb_data)
    elif cmd == SceneCmd.Operate:
        pass
    elif cmd == SceneCmd.GameOprate:
        pass
    elif cmd == SceneCmd.GetRoomSetting:
        client.send_scene_message(module, SceneCmd.RoomSetting, b'')
    elif cmd == SceneCmd.RoomChat:
        handle_scene_chat(client, pb_data)
    elif cmd == SceneCmd.SendEmoji:
        pass
    elif cmd == SceneCmd.Trigger:
        pass
    elif cmd == SceneCmd.ChangeColor:
        handle_scene_change_color(client, pb_data)
    elif cmd == SceneCmd.ReportHangUp:
        pass
    elif cmd == SceneCmd.ReportSpeak:
        pass
    elif cmd == SceneCmd.SyncAction:
        pass
    elif cmd == SceneCmd.SyncMove:
        pass
    elif cmd == SceneCmd.MoveObject:
        pass
    else:
        # Silently ignore unhandled commands
        pass


def handle_scene_login(client, pb_data):
    """Handle scene login request."""
    name = ""
    key = ""
    version = 0

    try:
        reader = PBReader(pb_data)
        while reader.has_more():
            field_num, wire_type = reader.read_tag()
            if field_num == 1 and wire_type == 2:  # Name
                name = reader.read_string()
            elif field_num == 2 and wire_type == 2:  # Key
                key = reader.read_string()
            elif field_num == 3 and wire_type == 0:  # Version
                version = reader.read_varint()
            else:
                reader.skip_field(wire_type)
    except Exception as e:
        print(f"[Scene] Login parse error: {e}")

    client.scene_key = key
    client.player_name = name

    # Find player by scene key
    for room in scene_rooms.values():
        if key in room['player_keys']:
            client.player_id = room['player_keys'][key]
            client.room_id = room['id']
            room['players'][client.player_id] = client
            break

    if client.player_id == 0:
        client.player_id = generate_player_id()
        client.room_id = 1
        if client.room_id not in scene_rooms:
            scene_rooms[client.room_id] = {
                'id': 1,
                'players': {},
                'scene_key': key,
                'player_keys': {},
            }
        scene_rooms[client.room_id]['players'][client.player_id] = client
        scene_rooms[client.room_id]['player_keys'][key] = client.player_id

    scene_players[client.player_id] = client

    # Send login response
    ret_data = msg.encode_ret_scene_login(
        ok=True,
        player_id=client.player_id,
        scene_id=client.room_id,
        map_id=1,
        time=int(time.time())
    )
    client.send_scene_message(ModuleType.Scene, SceneCmd.Login, ret_data)

    print(f"[Scene] Login OK: pid={client.player_id} name={name}")

    # Send add player notification to other players in the room
    room = scene_rooms.get(client.room_id)
    if room:
        # Notify existing players about the new player
        new_player_info = msg.encode_msg_player_info(client.player_id, name, color_id=client.color_id)
        add_msg = msg.encode_scene_add_del_player(
            [{'id': client.player_id, 'name': name}],
            []
        )
        for pid, other_client in room['players'].items():
            if pid != client.player_id:
                try:
                    other_client.send_scene_message(ModuleType.Scene, SceneCmd.AddDelPlayer, add_msg)
                except:
                    pass

        # Notify new player about existing players
        existing_players = []
        for pid, other_client in room['players'].items():
            if pid != client.player_id:
                existing_players.append({'id': pid, 'name': other_client.player_name})
        if existing_players:
            existing_msg = msg.encode_scene_add_del_player(existing_players, [])
            client.send_scene_message(ModuleType.Scene, SceneCmd.AddDelPlayer, existing_msg)

    # Send game progress
    progress_msg = msg.encode_scene_game_progress(0)
    client.send_scene_message(ModuleType.Scene, SceneCmd.GameProgressNotice, progress_msg)


def handle_scene_move(client, pb_data):
    """Handle player movement."""
    try:
        reader = PBReader(pb_data)
        while reader.has_more():
            field_num, wire_type = reader.read_tag()
            if field_num == 1 and wire_type == 0:
                client.x = reader.read_varint() / 1000.0
            elif field_num == 2 and wire_type == 0:
                client.y = reader.read_varint() / 1000.0
            elif field_num == 3 and wire_type == 0:
                client.z = reader.read_varint() / 1000.0
            else:
                reader.skip_field(wire_type)
    except:
        pass

    # Broadcast to other players
    room = scene_rooms.get(client.room_id)
    if room:
        update_msg = msg.encode_scene_update_player(client.player_id, client.x, client.y, client.z, client.state)
        for pid, other_client in room['players'].items():
            if pid != client.player_id:
                try:
                    other_client.send_scene_message(ModuleType.Scene, SceneCmd.UpdatePlayer, update_msg)
                except:
                    pass


def handle_scene_batch_move(client, pb_data):
    """Handle batch movement."""
    pass


def handle_scene_change_state(client, pb_data):
    """Handle state change."""
    try:
        reader = PBReader(pb_data)
        while reader.has_more():
            field_num, wire_type = reader.read_tag()
            if field_num == 1 and wire_type == 0:
                client.state = reader.read_varint()
            else:
                reader.skip_field(wire_type)
    except:
        pass


def handle_scene_chat(client, pb_data):
    """Handle scene chat."""
    content = ""
    chat_type = 0
    try:
        reader = PBReader(pb_data)
        while reader.has_more():
            field_num, wire_type = reader.read_tag()
            if field_num == 3 and wire_type == 2:  # Content
                content = reader.read_string()
            elif field_num == 4 and wire_type == 0:  # Type
                chat_type = reader.read_varint()
            else:
                reader.skip_field(wire_type)
    except:
        pass

    # Broadcast chat to all players in room
    room = scene_rooms.get(client.room_id)
    if room:
        chat_msg = msg.encode_scene_chat(client.player_id, client.player_name, content, chat_type)
        for pid, other_client in room['players'].items():
            try:
                other_client.send_scene_message(ModuleType.Scene, SceneCmd.RoomChat, chat_msg)
            except:
                pass


def handle_scene_change_color(client, pb_data):
    """Handle color change."""
    try:
        reader = PBReader(pb_data)
        while reader.has_more():
            field_num, wire_type = reader.read_tag()
            if field_num == 1 and wire_type == 0:
                client.color_id = reader.read_varint()
            else:
                reader.skip_field(wire_type)
    except:
        pass


def start_scene_server():
    """Start the Scene TCP server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', SCENE_PORT))
    server.listen(5)
    print(f"[Scene] Scene server started on port {SCENE_PORT}")

    while True:
        conn, addr = server.accept()
        client = SceneClient(conn, addr)
        t = threading.Thread(target=handle_scene_client, args=(client,))
        t.daemon = True
        t.start()


# ==================== Heartbeat Thread ====================

def heartbeat_loop():
    """Send periodic heartbeats to gate clients."""
    while True:
        time.sleep(30)
        # Could send push heartbeats here if needed


# ==================== Main ====================

def main():
    print("=" * 60)
    print("  Game Server Starting...")
    print(f"  HTTP:  {SERVER_IP}:{HTTP_PORT}")
    print(f"  Gate:  {SERVER_IP}:{GATE_PORT}")
    print(f"  Scene: {SERVER_IP}:{SCENE_PORT}")
    print("=" * 60)

    # Start HTTP server in a thread
    http_thread = threading.Thread(target=start_http_server)
    http_thread.daemon = True
    http_thread.start()

    # Start Gate server in a thread
    gate_thread = threading.Thread(target=start_gate_server)
    gate_thread.daemon = True
    gate_thread.start()

    # Start Scene server in a thread
    scene_thread = threading.Thread(target=start_scene_server)
    scene_thread.daemon = True
    scene_thread.start()

    # Start heartbeat thread
    hb_thread = threading.Thread(target=heartbeat_loop)
    hb_thread.daemon = True
    hb_thread.start()

    print("\nAll servers started. Waiting for connections...")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)


if __name__ == '__main__':
    main()
