import os
import time
import requests
from urllib import parse, request
import json
from PIL import Image
import io
        
class WeixinMediaUploader:
    def __init__(self, appid, secret):
        self.appid = appid
        self.secret = secret
        self.access_token = None
        self.token_expire_time = 0
        size_limits = {
            'image': 2 * 1024 * 1024,      # 2MB
            'voice': 2 * 1024 * 1024,      # 2MB
            'video': 10 * 1024 * 1024,     # 10MB
            'thumb': 64 * 1024,            # 64KB
        }
        self.max_size = size_limits.get(type, 2 * 1024 * 1024)
        
    def get_access_token(self, use_stable=True):
        """获取access_token，优先使用稳定版接口"""
        if self.access_token and time.time() < self.token_expire_time - 60:
            return self.access_token
        
        if use_stable:
            url = 'https://api.weixin.qq.com/cgi-bin/stable_token'
            data = {
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.secret,
                "force_refresh": False
            }
            try:
                retoken = 2
                while retoken > 0:
                    response = requests.post(url, json=data, timeout=10)
                    result = response.json()
                    
                    if 'access_token' in result:
                        self.access_token = result['access_token']
                        expires_in = result.get('expires_in', 7200)
                        self.token_expire_time = time.time() + expires_in
                        return self.access_token
                    else:
                        retoken -= 1
            except Exception as e:
                print(f'稳定版token获取失败，尝试普通接口: {e}')
                # 降级到普通接口
        
        # 使用普通接口
        url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.appid}&secret={self.secret}'
        try:
            retoken2 = 2
            while retoken2 > 0:
                response = requests.get(url, timeout=10)
                result = response.json()
                if 'access_token' in result:
                    self.access_token = result['access_token']
                    expires_in = result.get('expires_in', 7200)
                    self.token_expire_time = time.time() + expires_in
                    return self.access_token
                else:
                    retoken -= 1
            print(f'获取access_token失败: {result}')
            return None
        except Exception as e:
            print(f'获取access_token时出错: {e}')
            return None
    
    def upload_media(self, file_path, type='image', max_retry=2):
        """上传媒体文件的主方法"""
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f'文件不存在: {file_path}')
            return None, None
        
        # 获取access_token
        token = self.get_access_token()
        if not token:
            print('获取access_token失败')
            return None, None
        
        # 检查文件大小
        if not self.check_file_size(file_path, type):
            # 如果是图片，尝试压缩
            if type == 'image':
                compressed_path = self.compress_image_if_needed(file_path, type)
                if compressed_path:
                    return self._upload_file(token, compressed_path, type, max_retry)
                else:
                    return None, None
            else:
                print(f'{type}类型文件超过大小限制')
                return None, None
        
        # 上传文件
        return self._upload_file(token, file_path, type, max_retry)
    
    def check_file_size(self, file_path, type):
        """检查文件大小是否符合要求"""
        try:
            file_size = os.path.getsize(file_path)
            if file_size <= self.max_size:
                return True
            else:
                print(f'文件大小超限: {file_size}字节 > {self.max_size}字节')
                return False
        except Exception as e:
            print(f'检查文件大小时出错: {e}')
            return False
    
    def _upload_file(self, access_token, file_path, type='image', max_retry=2):
        """实际的文件上传逻辑"""
        url = f'https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={access_token}&type={type}'
        
        for attempt in range(max_retry + 1):
            try:
                with open(file_path, 'rb') as file:
                    files = {'media': file}
                    response = requests.post(url, files=files, timeout=60)
                    result = response.json()
                    
                    print(f'上传结果: {result}')
                    
                    if 'media_id' in result:
                        media_id = result['media_id']
                        media_url = result.get('url', '')
                        return media_id, media_url
                    
                    # 处理错误
                    errcode = result.get('errcode')
                    errmsg = result.get('errmsg', '')
                    
                    if errcode == 40001 and attempt < max_retry:
                        print('access_token无效，重新获取...')
                        self.access_token = None
                        token = self.get_access_token()
                        if token:
                            url = f'https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type={type}'
                            continue
                    
                    print(f'上传失败: {errcode} - {errmsg}')
                    return None, None
                    
            except requests.exceptions.RequestException as e:
                print(f'网络请求出错: {e}')
                if attempt < max_retry:
                    time.sleep(2 ** attempt)  # 指数退避
                    continue
                return None, None
            except Exception as e:
                print(f'上传文件时出错: {e}')
                return None, None
        
        return None, None
    
    def compress_image_if_needed(self, file_path, type='image'):
        """如果需要，压缩图片文件"""
        if type != 'image':
            return None
        
        try:
            file_path_com = compress_image(file_path, self.max_size, quality=85)
            return file_path_com

        except Exception as e:
            print(f'压缩图片时出错: {e}')
            return None


def compress_image(file_path, max_size, quality=85):
    """
    压缩图片到指定大小
    """
    try:
        img = Image.open(file_path)
        
        # 如果是PNG，转换为JPEG以获得更好的压缩
        if img.format == 'PNG' and img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # 逐步降低质量直到达到目标大小
        for q in range(quality, 20, -5):  # 从85%质量开始，每次降低5%
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=q, optimize=True)
            size = buffer.tell()
            
            if size <= max_size:
                # 保存压缩后的文件
                compressed_path = f"{os.path.splitext(file_path)[0]}_compressed.jpg"
                with open(compressed_path, 'wb') as f:
                    f.write(buffer.getvalue())
                print(f'图片压缩成功: {size}字节 (质量: {q}%)')
                return compressed_path
        
        # 如果质量降到20%仍然太大，尝试调整尺寸
        original_width, original_height = img.size
        for scale in [0.8, 0.6, 0.5, 0.4, 0.3]:
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img_resized.save(buffer, format='JPEG', quality=70, optimize=True)
            size = buffer.tell()
            
            if size <= max_size:
                compressed_path = f"{os.path.splitext(file_path)[0]}_compressed_resized.jpg"
                with open(compressed_path, 'wb') as f:
                    f.write(buffer.getvalue())
                print(f'图片压缩成功: {size}字节 (缩放: {scale})')
                return compressed_path
        
        print('图片压缩失败，仍然超过大小限制')
        return None

    except Exception as e:
        print(f'压缩图片时出错: {e}')
        return None
    

if __name__ == "__main__":
    # 微信公众号后台【设置与开发】-【基本配置】
    appid = "wx8f74e7a8737d4f2b"
    secret = "f7b6a3a7f5b99be54cab7752d796a1a8"
    # 加入本机外网IP到IP白名单，查询在 https://ip.900cha.com/，微信公众号后台【设置与开发】-【安全中心】

    uploader = WeixinMediaUploader(appid, secret)
    
    # 上传图片
    media_id, media_url = uploader.upload_media('path/to/image.jpg', 'image')
    
    if media_id:
        print(f'上传成功: media_id={media_id}')
        print(f'URL: {media_url}')
    else:
        print('上传失败')
        