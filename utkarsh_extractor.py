"""
Utkarsh URL Extractor Module
Wrapper around utkarshwofree.py for use with Telegram bot
"""
import requests
import json
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
from base64 import b64decode, b64encode
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
# Configuration
API_URL = "https://application.utkarshapp.com/index.php/data_model"
COMMON_KEY = b"%!^F&^$)&^$&*$^&"
COMMON_IV = b"#*v$JvywJvyJDyvJ"
key_chars = "%!F*&^$)_*%3f&B+"
iv_chars = "#*$DJvyw2w%!_-$@"
MAX_WORKERS = 8
file_lock = Lock()
HEADERS = {
    "Authorization": "Bearer 152#svf346t45ybrer34yredk76t",
    "Content-Type": "text/plain; charset=UTF-8",
    "devicetype": "1",
    "host": "application.utkarshapp.com",
    "lang": "1",
    "user-agent": "okhttp/4.9.0",
    "userid": "0",
    "version": "152"
}
class UtkarshExtractor:
    """Extract video URLs from Utkarsh batch"""
    
    def __init__(self):
        self.session = requests.Session()
        self.key = None
        self.iv = None
        self.csrf_token = None
        self.h = None
        
    def encrypt(self, data, use_common_key=False):
        cipher_key = COMMON_KEY if use_common_key else self.key
        cipher_iv = COMMON_IV if use_common_key else self.iv
        cipher = AES.new(cipher_key, AES.MODE_CBC, cipher_iv)
        padded_data = pad(json.dumps(data, separators=(",", ":")).encode(), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        return b64encode(encrypted).decode() + ":"
    
    def decrypt(self, data, use_common_key=False):
        cipher_key = COMMON_KEY if use_common_key else self.key
        cipher_iv = COMMON_IV if use_common_key else self.iv
        cipher = AES.new(cipher_key, AES.MODE_CBC, cipher_iv)
        try:
            encrypted_data = b64decode(data.split(":")[0])
            decrypted_bytes = cipher.decrypt(encrypted_data)
            decrypted = unpad(decrypted_bytes, AES.block_size).decode()
            return decrypted
        except:
            return None
    
    def post_request(self, path, data=None, use_common_key=False):
        print(f"[API] POST to {path}, jwt present: {'jwt' in HEADERS}")
        encrypted_data = self.encrypt(data, use_common_key) if data else data
        response = requests.post(f"{API_URL}{path}", headers=HEADERS, data=encrypted_data, timeout=30)
        print(f"[API] Response status: {response.status_code}, length: {len(response.text)}")
        decrypted_data = self.decrypt(response.text, use_common_key)
        if decrypted_data:
            try:
                result = json.loads(decrypted_data)
                print(f"[API] Success, keys: {list(result.keys()) if isinstance(result, dict) else 'list'}")
                return result
            except Exception as e:
                print(f"[API] JSON parse error: {e}")
                pass
        else:
            print(f"[API] Decryption failed for response: {response.text[:100]}...")
        return {}
    
    def decrypt_stream(self, enc):
        try:
            enc = b64decode(enc)
            key = '%!$!%_$&!%F)&^!^'.encode('utf-8')
            iv = '#*y*#2yJ*#$wJv*v'.encode('utf-8')
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted_bytes = cipher.decrypt(enc)
            try:
                plaintext = unpad(decrypted_bytes, AES.block_size).decode('utf-8')
            except:
                plaintext = decrypted_bytes.decode('utf-8', errors='ignore')
            
            cleaned_json = ''
            for i in range(len(plaintext)):
                try:
                    json.loads(plaintext[:i+1])
                    cleaned_json = plaintext[:i+1]
                except:
                    continue
            
            final_brace_index = cleaned_json.rfind('}')
            if final_brace_index != -1:
                cleaned_json = cleaned_json[:final_brace_index + 1]
            return cleaned_json
        except:
            return None
    
    def decrypt_and_load_json(self, enc):
        decrypted_data = self.decrypt_stream(enc)
        try:
            return json.loads(decrypted_data)
        except:
            return None
    
    def encrypt_stream(self, plain_text):
        key = '%!$!%_$&!%F)&^!^'.encode('utf-8')
        iv = '#*y*#2yJ*#$wJv*v'.encode('utf-8')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = pad(plain_text.encode(), AES.block_size)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode()
    
    def login(self, username, password):
        """Login to Utkarsh and get tokens"""
        try:
            print(f"[LOGIN] Starting login with username: {username}")
            
            # Get CSRF token
            base_url = 'https://online.utkarsh.com/'
            r1 = self.session.get(base_url, timeout=30)
            self.csrf_token = r1.cookies.get('csrf_name')
            
            if not self.csrf_token:
                print("[LOGIN] CSRF token not found in cookies")
                raise ValueError("CSRF token not found")
            
            print(f"[LOGIN] Got CSRF token")
            
            # Login with correct format (matching utkarshwofree.py)
            login_url = 'https://online.utkarsh.com/web/Auth/login'
            login_data = {
                'csrf_name': self.csrf_token,
                'mobile': username,
                'url': '0',
                'password': password,
                'submit': 'LogIn',
                'device_token': 'null'
            }
            # Use browser-like headers
            login_headers = {
                'Host': 'online.utkarsh.com',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.6045.199 Safari/537.36'
            }
            
            r2 = self.session.post(login_url, data=login_data, headers=login_headers, timeout=30)
            print(f"[LOGIN] Login response status: {r2.status_code}")
            
            r2_json = r2.json()
            response_data = r2_json.get("response")
            
            if not response_data:
                print(f"[LOGIN] No response data: {r2_json}")
                raise ValueError("No response data")
            
            # Decrypt the response
            dr1 = self.decrypt_and_load_json(response_data)
            if not dr1:
                print("[LOGIN] Failed to decrypt login response")
                raise ValueError("Decryption failed")
            
            t = dr1.get("token")
            jwt = dr1.get("data", {}).get("jwt")
            
            if not t or not jwt:
                print(f"[LOGIN] Missing token/jwt: {dr1}")
                raise ValueError("Missing token or jwt")
            
            print(f"[LOGIN] Got token and JWT")
            
            # Store headers for subsequent requests
            self.h = {
                "token": t,
                "jwt": jwt,
                "csrf_name": self.csrf_token
            }
            HEADERS["jwt"] = jwt
            
            # Get user profile
            profile = self.post_request("/users/get_my_profile", use_common_key=True)
            if not profile or "data" not in profile:
                print(f"[LOGIN] Profile request failed: {profile}")
                raise ValueError("Profile request failed")
            
            user_id = profile["data"]["id"]
            HEADERS["userid"] = user_id
            
            self.key = "".join(key_chars[int(i)] for i in (user_id + "1524567456436545")[:16]).encode()
            self.iv = "".join(iv_chars[int(i)] for i in (user_id + "1524567456436545")[:16]).encode()
            
            print(f"[LOGIN] Login successful! User ID: {user_id}")
            return True
        except Exception as e:
            print(f"[LOGIN] Login error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_batch(self, batch_id, username=None, password=None):
        """
        Extract all URLs from a batch
        Returns: (list of (title, url) tuples, txt_file_path)
        """
        # Login if credentials provided
        if username and password:
            if not self.login(username, password):
                return [], None
        
        try:
            print(f"[EXTRACT] Starting extraction for batch: {batch_id}")
            
            tiles_data_url = 'https://online.utkarsh.com/web/Course/tiles_data'
            layer_two_data_url = 'https://online.utkarsh.com/web/Course/get_layer_two_data'
            meta_source_url = '/meta_distributer/on_request_meta_source'
            
            # Get course data
            d3 = {"course_id": batch_id, "layer": 0, "page": 1, "parent_id": batch_id, "revert_api": "1#0#0#1", "tile_id": 0, "type": "course"}
            de1 = self.encrypt_stream(json.dumps(d3))
            d4 = {'tile_input': de1, 'csrf_name': self.csrf_token}
            
            print(f"[EXTRACT] Requesting course data...")
            u4 = self.session.post(tiles_data_url, headers=self.h, data=d4).json()
            r4 = u4.get("response")
            
            if not r4:
                print(f"[EXTRACT] No response from tiles_data: {u4}")
                return [], None
            
            dr3 = self.decrypt_and_load_json(r4)
            
            if not dr3 or "data" not in dr3:
                print(f"[EXTRACT] Failed to decrypt or no data: {dr3}")
                return [], None
            
            courses = dr3.get("data", [])
            print(f"[EXTRACT] Found {len(courses)} courses in batch")
            
            # Create output file
            fn = f"Batch_{batch_id}.txt"
            all_urls = []
            
            with open(fn, "w", encoding="utf-8") as f:
                for item in dr3.get("data", []):
                    fi = item.get("id")
                    tn = item.get("title")
                    binfo = item.get("segment_information")
                    
                    f.write(f"\n{'='*80}\n")
                    f.write(f"Course: {tn} (ID: {fi})\n")
                    f.write(f"Info: {binfo}\n")
                    f.write(f"{'='*80}\n\n")
                    
                    # Get layer 1 data
                    d5 = {"course_id": fi, "layer": 1, "page": 1, "parent_id": fi, "revert_api": "1#1#0#1", "tile_id": "0", "type": "content"}
                    de2 = self.encrypt_stream(json.dumps(d5))
                    d6 = {'tile_input': de2, 'csrf_name': self.csrf_token}
                    u5 = self.session.post(tiles_data_url, headers=self.h, data=d6).json()
                    r5 = u5.get("response")
                    dr4 = self.decrypt_and_load_json(r5)
                    
                    if not dr4 or "data" not in dr4:
                        continue
                    
                    for sub in dr4["data"]["list"]:
                        sfi = sub.get("id")
                        
                        # Get layer 2 data
                        d7 = {"course_id": fi, "parent_id": fi, "layer": 2, "page": 1, "revert_api": "1#0#0#1", "subject_id": sfi, "tile_id": 0, "topic_id": sfi, "type": "content"}
                        de3 = base64.b64encode(json.dumps(d7).encode()).decode()
                        d8 = {'layer_two_input_data': de3, 'csrf_name': self.csrf_token}
                        u6 = self.session.post(layer_two_data_url, headers=self.h, data=d8).json()
                        r6 = u6["response"]
                        dr5 = self.decrypt_and_load_json(r6)
                        
                        if not dr5 or "data" not in dr5:
                            continue
                        
                        for topic in dr5["data"]["list"]:
                            ti = topic.get("id")
                            
                            # Get layer 3 data (videos)
                            d9 = {"course_id": fi, "parent_id": fi, "layer": 3, "page": 1, "revert_api": "1#0#0#1", "subject_id": sfi, "tile_id": 0, "topic_id": ti, "type": "content"}
                            de4 = base64.b64encode(json.dumps(d9).encode()).decode()
                            d10 = {'layer_two_input_data': de4, 'csrf_name': self.csrf_token}
                            u7 = self.session.post(layer_two_data_url, headers=self.h, data=d10).json()
                            r7 = u7["response"]
                            dr6 = self.decrypt_and_load_json(r7)
                            
                            if dr6 and "data" in dr6 and "list" in dr6["data"]:
                                video_items = []
                                for video in dr6["data"]["list"]:
                                    video['course_id'] = fi
                                    video_items.append(video)
                                
                                # Process videos
                                def process_video(video_item):
                                    try:
                                        ji = video_item.get("id")
                                        jt = video_item.get("title")
                                        jti = video_item["payload"]["tile_id"]
                                        
                                        j4 = {
                                            "course_id": video_item.get("course_id"),
                                            "device_id": "server_does_not_validate_it",
                                            "device_name": "server_does_not_validate_it",
                                            "download_click": "0",
                                            "name": ji + "_0_0",
                                            "tile_id": jti,
                                            "type": "video"
                                        }
                                        j5 = self.post_request(meta_source_url, j4)
                                        cj = j5.get("data", [])
                                        
                                        if cj:
                                            qo = cj.get("bitrate_urls", [])
                                            if qo and isinstance(qo, list):
                                                vu1 = qo[3].get("url", "") if len(qo) > 3 else ""
                                                vu2 = qo[2].get("url", "") if len(qo) > 2 else ""
                                                vu3 = qo[1].get("url", "") if len(qo) > 1 else ""
                                                vu = qo[0].get("url", "") if len(qo) > 0 else ""
                                                selected_vu = vu1 or vu2 or vu3 or vu
                                                if selected_vu:
                                                    pu = selected_vu.split("?Expires=")[0]
                                                    return (jt, pu)
                                            else:
                                                vu = cj.get("link", "")
                                                if vu:
                                                    if ".m3u8" in vu or ".pdf" in vu:
                                                        pu = vu.split("?Expires=")[0]
                                                        return (jt, pu)
                                                    elif vu.startswith('http'):
                                                        return (jt, vu)
                                                    else:
                                                        pu = f"https://www.youtube.com/embed/{vu}"
                                                        return (jt, pu)
                                    except:
                                        pass
                                    return None
                                
                                # Process concurrently
                                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                                    futures = [executor.submit(process_video, v) for v in video_items]
                                    for future in as_completed(futures):
                                        result = future.result()
                                        if result:
                                            title, url = result
                                            all_urls.append((title, url))
                                            f.write(f"{title}:{url}\n")
                                            f.flush()
            
            return all_urls, fn
            
        except Exception as e:
            print(f"Extraction error: {e}")
            return [], None
