
import json
from urllib import parse, request
import time
import requests
from PIL import Image


# 微信公众号后台【设置与开发】-【基本配置】
appid = "wx8f74e7a8737d4f2b"
secret = "f7b6a3a7f5b99be54cab7752d796a1a8"
# 加入本机外网IP到IP白名单，查询在 https://ip.900cha.com/，微信公众号后台【设置与开发】-【安全中心】

def get_wxCode_token():
    '''
    获取access_token
    https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Get_access_token.html
    '''
    try:
        textmod = {"grant_type": "client_credential",
            "appid": appid,
            "secret": secret
        }
        textmod = parse.urlencode(textmod)
        header_dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'}
        url = 'https://api.weixin.qq.com/cgi-bin/token'
        # url = 'https://api.weixin.qq.com/cgi-bin/stable_token' # 稳定版接口 https://mmbizurl.cn/s/JtxxFh33r
        req = request.Request(url='%s%s%s' % (url, '?', textmod), headers=header_dict)
        res = request.urlopen(req)
        res = res.read().decode(encoding='utf-8')
        res = json.loads(res)
        access_token = res["access_token"]
        print('access_token:',(access_token, time.time()))
        return access_token
    except Exception as e:
        print('get_wxCode_token error', e)
        return False

def get_access_token(appid, secret):
    url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={}&secret={}'.format(appid, secret)
    response = requests.get(url)
    data = response.json()
    print('get_access_token:', data)
    if 'errcode' in data:
        return False
    return data['access_token']

def upload_media_to_weixin(access_token, file_path, type='image'):
    '''
    上传媒体文件到微信，类型分别有图片（image）、语音（voice）、视频（video）和缩略图（thumb）
    https://api.weixin.qq.com/cgi-bin/media/uploadnews?access_token=ACCESS_TOKEN
    '''
    url = 'https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={}&type={}'.format(access_token, type)
    files = {'media': open(file_path, 'rb')}
    response = requests.post(url, files=files)
    print('upload_media response:', response.json())    
    if 'media_id' in response.json():
        media_id = response.json()['media_id']
        media_url = response.json()['url']
        return media_id, media_url
    else:
        print('upload_media error!')
        return None, None


# 获取微信公众号的access_token
access_token = get_wxCode_token()
if not access_token:
    access_token = get_wxCode_token()
    if not access_token:
        access_token = get_wxCode_token()
        if not access_token:
            access_token = get_access_token(appid, secret)
