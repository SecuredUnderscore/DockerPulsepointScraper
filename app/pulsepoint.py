import json
import base64
import hashlib
import requests
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

API_BASE = "https://api.pulsepoint.org/v1/webapp"

def get_decryption_key() -> str:
    key = ''
    incidents = 'CommonIncidents'
    key += incidents[13]
    key += incidents[1]
    key += incidents[2]
    key += 'brady'
    number = 2 * 5
    key += str(int(number / 2))
    key += f"r{incidents.lower()[6]}{incidents[5]}gs"
    return key

def evp_bytestokey(password, salt, key_len, iv_len):
    dtf = d_i = b''
    while len(dtf) < (key_len + iv_len):
        d_i = hashlib.md5(d_i + password + salt).digest()
        dtf += d_i
    return dtf[:key_len], dtf[key_len:key_len + iv_len]

def decrypt_response(response_data: dict) -> dict:
    if not response_data or 'ct' not in response_data:
        return response_data
        
    passphrase = get_decryption_key().encode('utf-8')
    ct_b64 = response_data.get('ct')
    salt_hex = response_data.get('s')
    
    ct_bytes = base64.b64decode(ct_b64)
    salt_bytes = bytes.fromhex(salt_hex) if salt_hex else b""
    
    key, iv = evp_bytestokey(passphrase, salt_bytes, 32, 16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    try:
        decrypted_bytes = unpad(cipher.decrypt(ct_bytes), AES.block_size)
        decrypted_str = decrypted_bytes.decode('utf-8')
        
        first_parse = json.loads(decrypted_str)
        if isinstance(first_parse, str):
             return json.loads(first_parse)
        return first_parse
        
    except Exception as e:
        print(f"Decryption failed: {e}")
        return {}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def search_agencies(query=""):
    url = f"{API_BASE}?resource=searchagencies"
    res = requests.get(url, headers=HEADERS)
    try:
        return decrypt_response(res.json())
    except Exception as e:
        print(f"Failed to fetch agencies: {e}")
        return {}

def get_agency_data(agency_id):
    url = f"{API_BASE}?resource=agencies&agencyid={agency_id}"
    res = requests.get(url, headers=HEADERS)
    try:
        return decrypt_response(res.json())
    except Exception as e:
        print(f"Failed to fetch agency data for {agency_id}: {e}")
        return {}

def get_incidents(agency_id):
    url = f"{API_BASE}?resource=incidents&agencyid={agency_id}"
    res = requests.get(url, headers=HEADERS)
    try:
        data = res.json()
        return decrypt_response(data)
    except Exception as e:
        print(f"Failed to fetch incidents for {agency_id}: {e}")
        return {}
