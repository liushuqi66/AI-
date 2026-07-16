"""
阿里云函数计算 FC 入口适配器

当部署到阿里云 FC 时，FC 会调用此文件的 handler 函数。
兼容两种模式：
1. WSGI 模式：将 Flask app 包装为 WSGI handler
2. HTTP 触发器模式：直接透传到 Flask app
"""

from app import app as application


# 阿里云 FC HTTP 触发器入口
def handler(environ, start_response):
    """
    FC HTTP 触发器 handler。
    阿里云 FC 3.0 使用 WSGI 协议。
    """
    return application(environ, start_response)


# 兼容旧版 FC
def initialize(context):
    """FC 初始化函数"""
    pass
