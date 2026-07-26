#!/bin/bash
# ============================================================
# 服务器自测脚本 - 在服务器上运行此脚本验证服务是否正常
# 使用方法: bash self_test.sh
# ============================================================

IP="172.21.26.128"
HTTP_PORT=8080
GATE_PORT=8100
SCENE_PORT=8200

echo "=========================================="
echo "  太空杀服务器自测脚本"
echo "  服务器IP: $IP"
echo "=========================================="
echo ""

# 1. 检查端口是否在监听
echo "=== 1. 检查端口监听状态 ==="
for port in $HTTP_PORT $GATE_PORT $SCENE_PORT; do
    if ss -tlnp | grep -q ":$port "; then
        echo "  ✓ 端口 $port 正在监听"
    else
        echo "  ✗ 端口 $port 未监听 - 服务器可能未启动!"
    fi
done
echo ""

# 2. 测试HTTP登录
echo "=== 2. 测试HTTP登录 (端口 $HTTP_PORT) ==="
LOGIN_RESP=$(python3 -c "
import struct, io, http.client

class PBWriter:
    def __init__(self):
        self.buf = io.BytesIO()
    def write_varint(self, v):
        while v > 0x7f:
            self.buf.write(bytes([0x80 | (v & 0x7f)]))
            v >>= 7
        self.buf.write(bytes([v & 0x7f]))
    def write_string(self, field_num, s):
        self.write_varint((field_num << 3) | 2)
        data = s.encode('utf-8')
        self.write_varint(len(data))
        self.buf.write(data)
    def getvalue(self):
        return self.buf.getvalue()

pb = PBWriter()
pb.write_string(1, 'test_device')
pb.write_string(2, 'TestPlayer')
pb.write_string(3, '')
body = struct.pack('<HH', 1, 1) + struct.pack('<Q', 0) + pb.getvalue()

conn = http.client.HTTPConnection('$IP', $HTTP_PORT, timeout=10)
conn.request('POST', '/login', body)
resp = conn.getresponse()
data = resp.read()

if len(data) > 1 and data[0] == 0:
    # Parse response
    class PBReader:
        def __init__(self, data):
            self.data = data; self.pos = 0
        def has_more(self):
            return self.pos < len(self.data)
        def read_varint(self):
            result = 0; shift = 0
            while self.pos < len(self.data):
                b = self.data[self.pos]; self.pos += 1
                result |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            return result
        def read_tag(self):
            v = self.read_varint()
            return (v >> 3, v & 0x7)
        def read_string(self):
            length = self.read_varint()
            s = self.data[self.pos:self.pos+length].decode('utf-8', errors='replace')
            self.pos += length
            return s
        def skip(self, wt):
            if wt == 0: self.read_varint()
            elif wt == 2:
                l = self.read_varint(); self.pos += l
            elif wt == 5: self.pos += 4
            elif wt == 1: self.pos += 8
    
    reader = PBReader(data[1:])
    pid = 0; gate_addr = ''; gate_key = ''
    while reader.has_more():
        fn, wt = reader.read_tag()
        if wt == 0:
            val = reader.read_varint()
            if fn == 1: pid = val
        elif wt == 2:
            val = reader.read_string()
            if fn == 5: gate_addr = val
            if fn == 6: gate_key = val
        else:
            reader.skip(wt)
    
    print(f'  ✓ 登录成功!')
    print(f'    玩家ID: {pid}')
    print(f'    Gate地址: {gate_addr}')
    print(f'    Gate密钥: {gate_key[:16]}...')
    
    if '$IP' in gate_addr:
        print(f'  ✓ Gate地址包含正确的IP ($IP)')
    else:
        print(f'  ✗ Gate地址不包含 $IP! 地址是: {gate_addr}')
else:
    print(f'  ✗ 登录失败! 响应长度: {len(data)}, flag: {data[0] if len(data)>0 else \"N/A\"}')
conn.close()
" 2>&1)
echo "$LOGIN_RESP"
echo ""

# 3. 测试Gate服务器TCP连接
echo "=== 3. 测试Gate服务器 (端口 $GATE_PORT) ==="
GATE_TEST=$(python3 -c "
import socket, struct, time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
try:
    s.connect(('$IP', $GATE_PORT))
    print(f'  ✓ Gate服务器TCP连接成功')
    
    # Send GateLogin packet
    # Protocol: total_size(3B BE) + flag(1B) + module(2B BE) + cmd(2B BE) + sid(4B BE) + PbObj
    module = 1   # Gate
    cmd = 1      # GateLogin
    sid = 1001
    # PbObj: field 1 (gate_key) = 'test_key'
    import io
    class PBW:
        def __init__(self): self.buf = io.BytesIO()
        def wv(self, v):
            while v > 0x7f: self.buf.write(bytes([0x80|(v&0x7f)])); v >>= 7
            self.buf.write(bytes([v&0x7f]))
        def ws(self, fn, s):
            self.wv((fn<<3)|2); d=s.encode(); self.wv(len(d)); self.buf.write(d)
        def get(self): return self.buf.getvalue()
    pb = PBW()
    pb.ws(1, 'test_gate_key_12345')
    pb_data = pb.get()
    
    body = struct.pack('>I', len(pb_data) + 9)[1:]  # 3 bytes total size (BE)
    body += bytes([0])  # flag
    body += struct.pack('>HH', module, cmd)
    body += struct.pack('>I', sid)
    body += pb_data
    
    s.send(body)
    time.sleep(1)
    
    try:
        resp = s.recv(4096)
        if len(resp) > 0:
            print(f'  ✓ Gate服务器响应: {len(resp)} 字节')
        else:
            print(f'  ⚠ Gate服务器返回空响应')
    except socket.timeout:
        print(f'  ⚠ Gate服务器响应超时 (可能正常 - 需要有效gate_key)')
except socket.timeout:
    print(f'  ✗ Gate服务器连接超时!')
except ConnectionRefusedError:
    print(f'  ✗ Gate服务器连接被拒绝!')
except Exception as e:
    print(f'  ✗ Gate服务器错误: {e}')
finally:
    s.close()
" 2>&1)
echo "$GATE_TEST"
echo ""

# 4. 测试Scene服务器TCP连接
echo "=== 4. 测试Scene服务器 (端口 $SCENE_PORT) ==="
SCENE_TEST=$(python3 -c "
import socket, time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
try:
    s.connect(('$IP', $SCENE_PORT))
    print(f'  ✓ Scene服务器TCP连接成功')
except socket.timeout:
    print(f'  ✗ Scene服务器连接超时!')
except ConnectionRefusedError:
    print(f'  ✗ Scene服务器连接被拒绝!')
except Exception as e:
    print(f'  ✗ Scene服务器错误: {e}')
finally:
    s.close()
" 2>&1)
echo "$SCENE_TEST"
echo ""

# 5. 测试资源文件访问
echo "=== 5. 测试资源文件HTTP访问 ==="
RESOURCE_TEST=$(python3 -c "
import http.client

conn = http.client.HTTPConnection('$IP', $HTTP_PORT, timeout=10)

# Test assetsversion.json
conn.request('GET', '/assetsversion.json')
resp = conn.getresponse()
data = resp.read()
if resp.status == 200 and len(data) > 0:
    print(f'  ✓ /assetsversion.json: {len(data)} 字节')
else:
    print(f'  ✗ /assetsversion.json: HTTP {resp.status}, {len(data)} 字节')

# Test appver_au.xml
conn.request('GET', '/appver_au.xml')
resp = conn.getresponse()
data = resp.read()
if resp.status == 200 and len(data) > 0:
    print(f'  ✓ /appver_au.xml: {len(data)} 字节')
else:
    print(f'  ✗ /appver_au.xml: HTTP {resp.status}')

conn.close()
" 2>&1)
echo "$RESOURCE_TEST"
echo ""

# 6. 检查防火墙
echo "=== 6. 检查防火墙规则 ==="
if command -v ufw &> /dev/null; then
    echo "  UFW状态:"
    ufw status 2>/dev/null | head -10
elif command -v iptables &> /dev/null; then
    echo "  iptables规则 (相关端口):"
    iptables -L -n 2>/dev/null | grep -E "8080|8100|8200|ACCEPT|DROP" | head -10
else
    echo "  未找到防火墙工具"
fi
echo ""

echo "=========================================="
echo "  自测完成!"
echo "  如果所有测试显示 ✓，服务器应该可以正常工作"
echo "  手机需要能访问 $IP 才能连接"
echo "=========================================="
