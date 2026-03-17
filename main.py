from flask import Flask, request, jsonify
import json
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import aiohttp
import asyncio
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from google.protobuf.json_format import MessageToJson
import uid_generator_pb2
import like_count_pb2
import cachetools
import threading
import time

app = Flask(__name__)

uid_cache = cachetools.TTLCache(maxsize=1000, ttl=3600)
TOKENS = []
TOKEN_REFRESH_INTERVAL = 10800

def load_tokens():
    try:
        with open("token_cis.json", "r") as f:
            return json.load(f)
    except:
        return []

def refresh_tokens_periodically():
    while True:
        global TOKENS
        TOKENS = load_tokens()
        print(f"Tokens refreshed. Loaded {len(TOKENS)} tokens.")
        time.sleep(TOKEN_REFRESH_INTERVAL)

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except:
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except:
        return None

def enc(uid):
    if uid in uid_cache:
        return uid_cache[uid]
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    if encrypted_uid:
        uid_cache[uid] = encrypted_uid
    return encrypted_uid

async def make_request_async(session, encrypt, token):
    try:
        url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'ReleaseVersion': "OB51"
        }
        async with session.post(url, data=edata, headers=headers, ssl=False, timeout=aiohttp.ClientTimeout(total=2)) as response:
            if response.status != 200:
                return None
            hex_data = await response.read()
            binary = bytes.fromhex(hex_data.hex())
            decode = like_count_pb2.Info()
            decode.ParseFromString(binary)
            return decode
    except:
        return None

async def visit_async():
    target_uid = request.args.get("uid")
    
    if not target_uid:
        return jsonify({"error": "UID required"}), 400
    if not TOKENS:
        return jsonify({"error": "No tokens"}), 400

    encrypted_target_uid = enc(target_uid)
    if not encrypted_target_uid:
        return jsonify({"error": "Encryption failed"}), 500

    total = len(TOKENS)
    success = 0
    failed = 0
    player_name = None
    player_uid = None

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(500)
        
        async def bound_request(token):
            async with semaphore:
                return await make_request_async(session, encrypted_target_uid, token['token'])

        tasks = [bound_request(token) for token in TOKENS]
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=8)
        except:
            results = []

        for result in results:
            if isinstance(result, Exception) or result is None:
                failed += 1
            else:
                success += 1
                if player_name is None:
                    jsone = MessageToJson(result)
                    data_info = json.loads(jsone)
                    player_name = str(data_info.get('AccountInfo', {}).get('PlayerNickname', ''))
                    player_uid = int(data_info.get('AccountInfo', {}).get('UID', 0))

    return jsonify({
        "TotalVisits": total,
        "SuccessfulVisits": success,
        "FailedVisits": failed,
        "PlayerNickname": player_name,
        "UID": player_uid
    })

@app.route('/visit', methods=['GET'])
def visit():
    try:
        return asyncio.run(visit_async())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    TOKENS = load_tokens()
    threading.Thread(target=refresh_tokens_periodically, daemon=True).start()
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
