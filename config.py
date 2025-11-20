# config.py
"""
ddddocr 验证码识别系统配置文件
可以在这里调整所有参数，无需修改主程序代码
"""

class Config:
    # ==================== 网站配置 ====================
    BASE_URL = "http://xxx.XXX.cn"
    
    # ==================== 文件配置 ====================
    ACCOUNT_FILE = "zhanghao.txt"
    PASSWORD_FILE = "mima.txt"
    
    # ==================== 请求配置 ====================
    REQUEST_TIMEOUT = 10
    DELAY_BETWEEN_REQUESTS = 1
    MAX_RETRY_COUNT = 3
    RETRY_DELAY = 2
    
    # ==================== 验证码配置 ====================
    CAPTCHA_LENGTH = 4
    SAVE_CAPTCHA_IMAGES = True
    ENABLE_IMAGE_PREPROCESSING = True
    
    # ==================== 日志配置 ====================
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_TO_FILE = True
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    
    # ==================== 图像预处理配置 ====================
    # 对比度增强倍数
    CONTRAST_ENHANCE = 2.0
    # 是否启用锐化
    ENABLE_SHARPEN = True
    # 是否启用图像放大（小图像时）
    ENABLE_RESIZE = True
    # 图像放大倍数
    RESIZE_FACTOR = 2
    
    # ==================== 用户代理配置 ====================
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0'
    
    # ==================== API 端点配置 ====================
    CAPTCHA_API = "/XXX/XXX/getPhoto"
    LOGIN_API = "/XXX/login"
    
    # ==================== 报告配置 ====================
    GENERATE_DETAILED_REPORT = True
    REPORT_FILENAME_PREFIX = "ddddocr_report"
    
    # ==================== 性能配置 ====================
    # 批量处理大小（未来扩展用）
    BATCH_SIZE = 1
    # 最大并发数（未来扩展用）
    MAX_CONCURRENT = 1

# 开发环境配置（继承并覆盖生产配置）
class DevelopmentConfig(Config):
    LOG_LEVEL = "DEBUG"
    SAVE_CAPTCHA_IMAGES = True
    DELAY_BETWEEN_REQUESTS = 2  # 开发环境延迟更长

# 生产环境配置
class ProductionConfig(Config):
    LOG_LEVEL = "INFO"
    SAVE_CAPTCHA_IMAGES = False  # 生产环境不保存图片
    DELAY_BETWEEN_REQUESTS = 1

# 测试环境配置
class TestingConfig(Config):
    LOG_LEVEL = "DEBUG"
    SAVE_CAPTCHA_IMAGES = True
    MAX_RETRY_COUNT = 1  # 测试环境减少重试次数

# 默认使用生产配置
CurrentConfig = Config

def use_development_config():
    """切换到开发环境配置"""
    global CurrentConfig
    CurrentConfig = DevelopmentConfig
    return CurrentConfig

def use_production_config():
    """切换到生产环境配置"""
    global CurrentConfig
    CurrentConfig = ProductionConfig
    return CurrentConfig

def use_testing_config():
    """切换到测试环境配置"""
    global CurrentConfig
    CurrentConfig = TestingConfig
    return CurrentConfig

def get_config():
    """获取当前配置"""
    return CurrentConfig