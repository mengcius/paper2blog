# -*- coding: utf-8 -*-
'''
# VPN配置
windows终端配置: set http_proxy=http://127.0.0.1:10809; set https_proxy=http://127.0.0.1:10809
linux终端(包括win上git bash终端)配置: export https_proxy=http://127.0.0.1:10809 http_proxy=http://127.0.0.1:10809 all_proxy=socks5://127.0.0.1:10808
python代码内配置: os.environ['http_proxy'] os.environ['https_proxy']
curl https://www.google.com
'''
import os
import sys, io
import time
import requests
import subprocess
import platform

def set_proxy(use_vpn=True):
    """设置或清除VPN系统代理环境变量"""
    if use_vpn:
        # 设置代理环境变量
        os.environ['http_proxy'] = 'http://127.0.0.1:10809'
        os.environ['https_proxy'] = 'http://127.0.0.1:10809'
        os.environ['all_proxy'] = 'socks5://127.0.0.1:10808'
        
        # 为了兼容性，也设置一些常见的大小写变体
        os.environ['HTTP_PROXY'] = 'http://127.0.0.1:10809'
        os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:10809'
        os.environ['ALL_PROXY'] = 'socks5://127.0.0.1:10808'
        
        print('Start VPN...')
    else:
        # 清除代理环境变量
        proxy_vars = ['http_proxy', 'https_proxy', 'all_proxy',
                     'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']
        for var in proxy_vars:
            if var in os.environ:
                del os.environ[var]
        print('Stop VPN...')

def test_connection():
    """测试VPN国际网络连接"""
    try:
        if platform.system() == 'Windows':
            test_cmd = ['curl', '-s', '--max-time', '10', 'https://www.google.com']
        else:
            test_cmd = ['curl', '-s', '--max-time', '10', 'https://www.google.com']
        recurl = 3
        while recurl > 0: # 重试3次
            result = subprocess.run(test_cmd, capture_output=True, text=True)
            time.sleep(3) 
            if result.returncode == 0:
                print("✓ VPN国际网络连接正常")
                return True
            else:
                print("✗ VPN国际网络连接失败", result)
                recurl -= 1
        return False
    except Exception as e:
        print(f"测试连接时出错: {e}")
        return False
