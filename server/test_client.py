#!/usr/bin/env python3
"""Test client to verify the game server login flow."""
import socket
import struct
import time
import sys
import requests

from pb import PBWriter, PBReader, encode_varint

# Server address
SERVER_IP = "127.0.0.1"
HTTP_PORT = 8080
GATE_PORT = 8100
SCENE_PORT = 8200


def test_http_login():
    """Test HTTP login."""
    print("\n=== Testing HTTP Login ===")

    # Build ReqLoginMsg
    w = PBWriter()
    w.write_string_field(1, "test_device_123")  # Device
    w.write_string_field(2, "TestPlayer")  # Account
    w.write_string_field(3, "password123")  # Password
    w.write_varint_field(4, 4)  # Version
    pb_data = w.get_bytes()

    # Build HTTP request body: module(2B LE) + cmd(2B LE) + uid(8B LE) + pb_data
    module = 1  # Login
    cmd = 1  # Login
    uid = 0
    body = struct.pack('<HH', module, cmd) + struct.pack('<Q', uid) + pb_data

    url = f"http://{SERVER_IP}:{HTTP_PORT}/login"
    print(f"POST {url}")
    print(f"Body length: {len(body)}")

    resp = requests.post(url, data=body, headers={
        'Content-Type': 'application/octet-stream',
        'qqdztype': '1'
    })

    print(f"Response status: {resp.status_code}")
    print(f"Response length: {len(resp.content)}")

    if len(resp.content) < 1:
        print("ERROR: Empty response")
        return None, None

    flag = resp.content[0]
    if flag & 1 == 1:
        # Error response
        err_code = struct.unpack('<i', resp.content[1:5])[0]
        print(f"ERROR: Login failed with error code: {err_code}")
        return None, None

    # Success response
    pb_resp = resp.content[1:]
    reader = PBReader(pb_resp)

    player_id = 0
    account = ""
    gate_addr = ""
    gate_key = ""

    while reader.has_more():
        field_num, wire_type = reader.read_tag()
        if field_num == 1 and wire_type == 0:  # Id
            player_id = reader.read_varint()
        elif field_num == 2 and wire_type == 0:  # IsBind
            reader.read_varint()
        elif field_num == 3 and wire_type == 2:  # Account
            account = reader.read_string()
        elif field_num == 5 and wire_type == 2:  # GateAddr
            gate_addr = reader.read_string()
        elif field_num == 6 and wire_type == 2:  # GateKey
            gate_key = reader.read_string()
        else:
            reader.skip_field(wire_type)

    print(f"Player ID: {player_id}")
    print(f"Account: {account}")
    print(f"GateAddr: {gate_addr}")
    print(f"GateKey: {gate_key}")

    return player_id, gate_key, gate_addr


def test_gate_login(gate_key, gate_addr):
    """Test Gate/RPC TCP login."""
    print("\n=== Testing Gate Login ===")

    # Parse gate address
    parts = gate_addr.split(':')
    ip = parts[0]
    port = int(parts[1])

    print(f"Connecting to {ip}:{port}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((ip, port))
    print("Connected!")

    # Send ReqGateLogin: module=60002, cmd=1
    w = PBWriter()
    w.write_string_field(1, gate_key)  # Key
    w.write_string_field(2, "1.0.0")  # Version
    pb_data = w.get_bytes()

    # RPC TCP format: 3B size (BE) + 1B flag + 2B module (BE) + 2B cmd (BE) + 4B sid (BE) + pb_data
    total_size = len(pb_data) + 12
    header = struct.pack('>I', (total_size << 8) | 0)[:3] + bytes([0])
    module = 60002  # GateService
    cmd = 1  # GateLogin
    sid = 1
    module_cmd = struct.pack('>HHI', module, cmd, sid)
    msg_data = header + module_cmd + pb_data

    print(f"Sending gate login ({len(msg_data)} bytes)")
    sock.sendall(msg_data)

    # Receive response
    resp = sock.recv(4096)
    print(f"Received {len(resp)} bytes")

    if len(resp) >= 8:
        resp_size = (resp[0] << 16) | (resp[1] << 8) | resp[2]
        resp_flag = resp[3]
        resp_sid = struct.unpack('>I', resp[4:8])[0]
        print(f"Response: size={resp_size} flag={resp_flag} sid={resp_sid}")

        if resp_flag >> 3 == 1:
            # Error
            err_code = struct.unpack('>H', resp[8:10])[0]
            print(f"ERROR: Gate login failed: {err_code}")
        else:
            print("Gate login OK!")
            # Parse RetGateLogin (Key1, Key2)
            if len(resp) > 8:
                reader = PBReader(resp[8:])
                while reader.has_more():
                    field_num, wire_type = reader.read_tag()
                    if field_num == 1:
                        key1 = reader.read_bytes()
                        print(f"Key1: {key1.hex()}")
                    elif field_num == 2:
                        key2 = reader.read_bytes()
                        print(f"Key2: {key2.hex()}")
                    else:
                        reader.skip_field(wire_type)

    # Test heartbeat
    print("\n--- Testing Heartbeat ---")
    hb_pb = b''  # Empty heartbeat
    total_size = len(hb_pb) + 12
    header = struct.pack('>I', (total_size << 8) | 0)[:3] + bytes([0])
    module_cmd = struct.pack('>HHI', 60002, 2, 2)  # GateService, HeartBeat, sid=2
    sock.sendall(header + module_cmd + hb_pb)

    resp = sock.recv(4096)
    print(f"Heartbeat response: {len(resp)} bytes")

    # Test GetSvrTime
    print("\n--- Testing GetSvrTime ---")
    svr_time_pb = b''
    total_size = len(svr_time_pb) + 12
    header = struct.pack('>I', (total_size << 8) | 0)[:3] + bytes([0])
    module_cmd = struct.pack('>HHI', 30, 16, 3)  # Relation, GetSvrTime, sid=3
    sock.sendall(header + module_cmd + svr_time_pb)

    resp = sock.recv(4096)
    print(f"GetSvrTime response: {len(resp)} bytes")
    if len(resp) >= 8:
        resp_flag = resp[3]
        resp_sid = struct.unpack('>I', resp[4:8])[0]
        if resp_flag >> 3 == 1:
            print(f"  Error response")
        else:
            # Parse RetGetSvrTime
            if len(resp) > 8:
                reader = PBReader(resp[8:])
                while reader.has_more():
                    field_num, wire_type = reader.read_tag()
                    if field_num == 1:
                        svr_time = reader.read_varint()
                        print(f"  Server time: {svr_time} ({time.ctime(svr_time)})")
                    else:
                        reader.skip_field(wire_type)

    # Test GetRoleDetail
    print("\n--- Testing GetRoleDetail ---")
    role_pb = b''
    total_size = len(role_pb) + 12
    header = struct.pack('>I', (total_size << 8) | 0)[:3] + bytes([0])
    module_cmd = struct.pack('>HHI', 2, 1, 4)  # User, GetRoleDetail, sid=4
    sock.sendall(header + module_cmd + role_pb)

    resp = sock.recv(4096)
    print(f"GetRoleDetail response: {len(resp)} bytes")
    if len(resp) >= 8:
        resp_flag = resp[3]
        resp_sid = struct.unpack('>I', resp[4:8])[0]
        if resp_flag >> 3 == 1:
            print(f"  Error response")
        else:
            print(f"  Success! Data length: {len(resp) - 8}")

    return sock


def test_http_start_game(uid):
    """Test HTTP start game."""
    print("\n=== Testing HTTP StartGame ===")

    # Build ReqStartGame
    w = PBWriter()
    w.write_varint_field(1, 1)  # MType (Space)
    pb_data = w.get_bytes()

    # Build HTTP request body
    module = 1  # Login
    cmd = 2  # StartGame
    body = struct.pack('<HH', module, cmd) + struct.pack('<Q', uid) + pb_data

    url = f"http://{SERVER_IP}:{HTTP_PORT}/login"
    resp = requests.post(url, data=body, headers={
        'Content-Type': 'application/octet-stream',
        'qqdztype': '1'
    })

    if len(resp.content) < 1:
        print("ERROR: Empty response")
        return None, None

    flag = resp.content[0]
    if flag & 1 == 1:
        err_code = struct.unpack('<i', resp.content[1:5])[0]
        print(f"ERROR: StartGame failed: {err_code}")
        return None, None

    pb_resp = resp.content[1:]
    reader = PBReader(pb_resp)

    room_addr = ""
    room_key = ""

    while reader.has_more():
        field_num, wire_type = reader.read_tag()
        if field_num == 1 and wire_type == 2:  # RoomAddr
            room_addr = reader.read_string()
        elif field_num == 2 and wire_type == 2:  # RoomKey
            room_key = reader.read_string()
        else:
            reader.skip_field(wire_type)

    print(f"RoomAddr: {room_addr}")
    print(f"RoomKey: {room_key}")

    return room_addr, room_key


def test_scene_login(room_addr, room_key, player_name="TestPlayer"):
    """Test Scene TCP login."""
    print("\n=== Testing Scene Login ===")

    parts = room_addr.split(':')
    ip = parts[0]
    port = int(parts[1])

    print(f"Connecting to {ip}:{port}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((ip, port))
    print("Connected!")

    # Send ReqSceneLogin
    w = PBWriter()
    w.write_string_field(1, player_name)  # Name
    w.write_string_field(2, room_key)  # Key
    w.write_varint_field(3, 1)  # Version
    pb_data = w.get_bytes()

    # Scene TCP format: 3B size (LE) + 1B flag + 4B cmd (BE) + pb_data
    body_size = len(pb_data) + 4
    header = bytes([body_size & 0xFF, (body_size >> 8) & 0xFF, (body_size >> 16) & 0xFF, 0])
    # cmd = (module << 16) | cmd_id = (3 << 16) | 1 = 0x00030001
    cmd_val = (3 << 16) | 1  # Scene module, Login cmd
    cmd_bytes = struct.pack('>I', cmd_val)
    msg_data = header + cmd_bytes + pb_data

    print(f"Sending scene login ({len(msg_data)} bytes)")
    sock.sendall(msg_data)

    # Receive response
    resp = sock.recv(4096)
    print(f"Received {len(resp)} bytes")

    if len(resp) >= 8:
        resp_body_size = resp[0] | (resp[1] << 8) | (resp[2] << 16)
        resp_flag = resp[3]
        resp_module = (resp[4] << 8) | resp[5]
        resp_cmd = (resp[6] << 8) | resp[7]
        print(f"Response: body_size={resp_body_size} flag={resp_flag} module={resp_module} cmd={resp_cmd}")

        if len(resp) > 8:
            reader = PBReader(resp[8:])
            while reader.has_more():
                field_num, wire_type = reader.read_tag()
                if field_num == 1:  # Ok
                    ok = reader.read_varint()
                    print(f"  Ok: {ok}")
                elif field_num == 2:  # PlayerId
                    pid = reader.read_varint()
                    print(f"  PlayerId: {pid}")
                elif field_num == 3:  # SceneId
                    sid = reader.read_varint()
                    print(f"  SceneId: {sid}")
                elif field_num == 6:  # MapId
                    mid = reader.read_varint()
                    print(f"  MapId: {mid}")
                else:
                    reader.skip_field(wire_type)

    # Test heartbeat
    print("\n--- Testing Scene Heartbeat ---")
    hb_pb = b''
    body_size = len(hb_pb) + 4
    header = bytes([body_size & 0xFF, (body_size >> 8) & 0xFF, (body_size >> 16) & 0xFF, 0])
    cmd_val = (3 << 16) | 2  # Scene, HeartBeat
    cmd_bytes = struct.pack('>I', cmd_val)
    sock.sendall(header + cmd_bytes + hb_pb)

    resp = sock.recv(4096)
    print(f"Heartbeat response: {len(resp)} bytes")

    return sock


def main():
    print("=" * 60)
    print("  Game Server Test Client")
    print("=" * 60)

    # Test HTTP login
    result = test_http_login()
    if result is None or result[0] is None:
        print("HTTP login failed!")
        return

    player_id, gate_key, gate_addr = result

    # Test Gate login
    gate_sock = test_gate_login(gate_key, gate_addr)
    if gate_sock is None:
        print("Gate login failed!")
        return

    # Test HTTP start game
    room_addr, room_key = test_http_start_game(player_id)
    if room_addr is None:
        print("Start game failed!")
        return

    # Test Scene login
    scene_sock = test_scene_login(room_addr, room_key)
    if scene_sock is None:
        print("Scene login failed!")
        return

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED!")
    print("=" * 60)

    # Cleanup
    gate_sock.close()
    scene_sock.close()


if __name__ == '__main__':
    main()
