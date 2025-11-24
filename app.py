from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from PIL import Image
import io
import re
import numpy as np
from urllib.parse import urlparse, parse_qs
import base64
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from migration_pb2 import parse_migration_payload

app = Flask(__name__)
CORS(app)

# 配置日志（必须在其他代码之前）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)  # 输出到控制台
    ]
)

# 获取 logger
logger = logging.getLogger(__name__)
logger.info("=" * 60)
logger.info("Google 2FA 应用启动")
logger.info("=" * 60)

# 配置上传目录
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/app/data/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

# 确保上传目录存在
try:
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    logger.info(f"图片上传目录: {UPLOAD_FOLDER}")
except Exception as e:
    logger.warning(f"无法创建上传目录 {UPLOAD_FOLDER}: {e}，图片将不会被保存")

def extract_secret_from_otpauth(url):
    """从 otpauth URL 中提取密钥"""
    try:
        # 解析 URL
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # 提取 secret 参数
        if 'secret' in query_params:
            secret = query_params['secret'][0]
            return secret
        
        # 如果没有 secret 参数，尝试从 URL 路径中提取
        # 某些格式可能是 otpauth://totp/Account:secret@issuer
        if '@' in parsed.path:
            parts = parsed.path.split('@')
            if len(parts) > 0:
                account_part = parts[0]
                if ':' in account_part:
                    secret = account_part.split(':')[-1]
                    return secret
        
        return None
    except Exception as e:
        logger.error(f"解析 URL 错误: {e}", exc_info=True)
        return None

def extract_secrets_from_migration(data_base64):
    """从 Google Authenticator 迁移格式中提取密钥和账户信息"""
    try:
        # 解码 base64
        # 处理 URL-safe base64 和标准 base64
        try:
            # 先尝试 URL-safe base64 解码
            data = base64.urlsafe_b64decode(data_base64)
        except:
            # 如果失败，尝试添加填充后解码
            padding = '=' * (4 - len(data_base64) % 4)
            data = base64.urlsafe_b64decode(data_base64 + padding)
        
        # 使用 protobuf 解析器解析迁移数据
        accounts = parse_migration_payload(data)
        
        if accounts and len(accounts) > 0:
            return accounts
        else:
            return None
    except Exception as e:
        logger.error(f"解析迁移格式错误: {e}", exc_info=True)
        return None

def parse_qr_code(image_data):
    """解析二维码图片并提取密钥"""
    try:
        import cv2
        
        # 将图片数据转换为 numpy 数组
        if isinstance(image_data, str):
            # 如果是 base64 字符串
            import base64
            if image_data.startswith('data:image'):
                # 移除 data:image/png;base64, 前缀
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
        else:
            nparr = np.frombuffer(image_data, np.uint8)
        
        # 使用 OpenCV 解码图片
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return None, "无法读取图片，请确保图片格式正确"
        
        # 转换为灰度图（二维码检测需要）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 使用 OpenCV 的 QRCodeDetector 解析二维码
        detector = cv2.QRCodeDetector()
        
        # 先尝试单个检测（更简单可靠）
        # 兼容不同版本的 OpenCV：某些版本返回 3 个值，某些返回 4 个值
        retval = None
        decoded_info = None
        points = None
        
        def safe_bool(value):
            """安全地将值转换为 Python bool，处理 numpy 数组"""
            if value is None:
                return False
            if isinstance(value, np.ndarray):
                # 如果是数组，检查是否非空
                if value.size == 0:
                    return False
                # 如果是布尔数组，使用 any()
                if value.dtype == bool:
                    return bool(value.any())
                # 否则转换为标量
                return bool(value.item() if value.size == 1 else value.any())
            return bool(value)
        
        def safe_decode_info(info):
            """安全地处理 decoded_info，转换为字符串"""
            if info is None:
                return None
            
            # 如果已经是字符串，直接返回
            if isinstance(info, str):
                return info
            
            # 处理 numpy 数组
            if isinstance(info, np.ndarray):
                if info.size == 0:
                    return None
                # 如果是字符串类型的数组，转换为字符串
                if info.dtype.kind == 'U' or info.dtype.kind == 'S':  # Unicode 或字节字符串
                    if info.size == 1:
                        info = info.item()
                    else:
                        # 多个字符串元素，取第一个
                        info = info.flat[0]
                else:
                    # 不是字符串类型，可能是坐标点，返回 None
                    return None
            
            # 处理列表或元组
            if isinstance(info, (list, tuple)):
                if len(info) == 0:
                    return None
                # 检查第一个元素是否是字符串
                first = info[0]
                if isinstance(first, str):
                    return first
                # 如果第一个元素是数字或列表（可能是坐标点），这不是有效的解码信息
                # 尝试检查是否有字符串元素
                for item in info:
                    if isinstance(item, str):
                        return item
                # 没有字符串元素，返回 None
                return None
            
            # 尝试转换为字符串（但只对简单类型）
            if isinstance(info, (int, float, bool)):
                return None  # 这些不是有效的二维码内容
            
            # 最后尝试转换为字符串
            try:
                result = str(info)
                # 如果结果看起来像坐标点（包含数字和括号），返回 None
                if '[' in result and ('.' in result or any(c.isdigit() for c in result)):
                    return None
                return result
            except:
                return None
        
        try:
            # 尝试解包 4 个值（新版本）
            result = detector.detectAndDecode(gray)
            if len(result) == 4:
                retval, decoded_info, points, straight_qrcode = result
            elif len(result) == 3:
                retval, decoded_info, points = result
            else:
                return None, f"OpenCV 返回了意外的值数量: {len(result)}"
        except ValueError as e:
            return None, f"二维码检测失败: {str(e)}"
        except Exception as e:
            return None, f"二维码检测失败: {str(e)}"
        
        # 调试：打印实际返回的类型
        # print(f"DEBUG: retval type={type(retval)}, decoded_info type={type(decoded_info)}")
        # print(f"DEBUG: decoded_info value={decoded_info}")
        
        # 处理 decoded_info - 确保它是字符串类型
        if decoded_info is not None:
            # 如果是 numpy 数组且是字符串类型
            if isinstance(decoded_info, np.ndarray):
                if decoded_info.dtype.kind in ['U', 'S']:  # Unicode 或字节字符串
                    decoded_info = str(decoded_info.item() if decoded_info.size == 1 else decoded_info.flat[0])
                else:
                    # 不是字符串数组，可能是坐标点，清空
                    decoded_info = None
            elif not isinstance(decoded_info, str):
                # 如果不是字符串，尝试转换
                decoded_info_str = safe_decode_info(decoded_info)
                decoded_info = decoded_info_str
        
        retval_bool = safe_bool(retval)
        
        # 如果单个检测失败，尝试多码检测
        if not retval_bool or not decoded_info:
            try:
                result_multi = detector.detectAndDecodeMulti(gray)
                if len(result_multi) == 4:
                    retval, decoded_info, points, straight_qrcode = result_multi
                elif len(result_multi) == 3:
                    retval, decoded_info, points = result_multi
                else:
                    decoded_info = None
                
                # 处理返回值 - 确保它是字符串类型
                if decoded_info is not None:
                    if isinstance(decoded_info, np.ndarray):
                        if decoded_info.dtype.kind in ['U', 'S']:
                            decoded_info = str(decoded_info.item() if decoded_info.size == 1 else decoded_info.flat[0])
                        else:
                            decoded_info = None
                    elif isinstance(decoded_info, (list, tuple)):
                        # 如果是列表，取第一个字符串元素
                        for item in decoded_info:
                            if isinstance(item, str):
                                decoded_info = item
                                break
                            elif isinstance(item, np.ndarray) and item.dtype.kind in ['U', 'S']:
                                decoded_info = str(item.item() if item.size == 1 else item.flat[0])
                                break
                        else:
                            decoded_info = None
                    elif not isinstance(decoded_info, str):
                        decoded_info_str = safe_decode_info(decoded_info)
                        decoded_info = decoded_info_str
                
                retval_bool = safe_bool(retval)
            except Exception as e:
                pass
        
        if not retval_bool or not decoded_info:
            return None, "未检测到二维码，请确保图片清晰且包含有效的二维码"
        
        # 获取二维码内容
        qr_data = decoded_info
        
        if not qr_data:
            return None, "二维码内容为空，请检查图片"
        
        # 检查是否是 otpauth URL
        if qr_data.startswith('otpauth://'):
            logger.info(f"检测到标准 otpauth 格式")
            secret = extract_secret_from_otpauth(qr_data)
            if secret:
                logger.info(f"成功提取密钥，长度: {len(secret)}")
                return secret, None
            else:
                logger.warning("无法从 otpauth URL 中提取密钥")
                return None, "无法从二维码中提取密钥"
        elif qr_data.startswith('otpauth-migration://'):
            logger.info(f"检测到迁移格式 (otpauth-migration)")
            # Google Authenticator 迁移格式
            try:
                parsed = urlparse(qr_data)
                query_params = parse_qs(parsed.query)
                
                if 'data' in query_params:
                    data_base64 = query_params['data'][0]
                    logger.info(f"开始解析迁移数据，数据长度: {len(data_base64)}")
                    # 从迁移格式中提取账户信息
                    accounts = extract_secrets_from_migration(data_base64)
                    
                    if accounts and len(accounts) > 0:
                        logger.info(f"成功解析迁移格式，提取到 {len(accounts)} 个账户")
                        # 返回账户列表（特殊格式，前端需要处理）
                        return accounts, None
                    else:
                        logger.warning("无法从迁移格式中提取账户")
                        return None, "无法从迁移格式中提取密钥。请确保迁移数据格式正确。"
                else:
                    logger.warning("迁移格式缺少 data 参数")
                    return None, "迁移格式缺少 data 参数"
            except Exception as e:
                logger.error(f"解析迁移格式时出错: {str(e)}", exc_info=True)
                return None, f"解析迁移格式时出错: {str(e)}"
        else:
            # 如果不是 otpauth URL，可能直接是密钥
            # 检查是否是有效的 base32 密钥格式
            if re.match(r'^[A-Z2-7]{16,}$', qr_data.upper()):
                return qr_data.upper(), None
            else:
                return None, f"二维码内容不是有效的 2FA 格式: {qr_data[:50]}"
    
    except ImportError as e:
        logger.error(f"缺少必要的库: {e}")
        return None, "缺少 opencv-python 库，请安装: pip install opencv-python"
    except Exception as e:
        logger.error(f"解析二维码时出错: {str(e)}", exc_info=True)
        return None, f"解析二维码时出错: {str(e)}"

# 请求日志中间件
@app.before_request
def log_request_info():
    logger.info(f"[{request.remote_addr}] {request.method} {request.path}")

@app.after_request
def log_response_info(response):
    logger.info(f"[{request.remote_addr}] {request.method} {request.path} - 状态码: {response.status_code}")
    return response

@app.route('/')
def index():
    return render_template('index.html')

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_image(file, client_ip):
    """保存上传的图片到服务器"""
    try:
        # 生成唯一文件名：时间戳_IP_原始文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_ip = client_ip.replace('.', '_').replace(':', '_')
        original_filename = secure_filename(file.filename) if file.filename else 'unknown'
        
        # 获取文件扩展名
        if '.' in original_filename:
            ext = original_filename.rsplit('.', 1)[1].lower()
        else:
            ext = 'png'  # 默认扩展名
        
        # 生成新文件名
        filename = f"{timestamp}_{safe_ip}_{original_filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # 保存文件
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        logger.info(f"[{client_ip}] 图片已保存: {filename} ({file_size} 字节)")
        
        return filepath, filename
    except Exception as e:
        logger.error(f"[{client_ip}] 保存图片失败: {str(e)}", exc_info=True)
        return None, None

@app.route('/api/convert', methods=['POST'])
def convert_qr():
    client_ip = request.remote_addr
    logger.info(f"[{client_ip}] 收到二维码转换请求")
    
    try:
        if 'image' not in request.files:
            logger.warning(f"[{client_ip}] 请求中未包含图片文件")
            return jsonify({'success': False, 'error': '未上传图片'}), 400
        
        file = request.files['image']
        if file.filename == '':
            logger.warning(f"[{client_ip}] 未选择文件")
            return jsonify({'success': False, 'error': '未选择文件'}), 400
        
        # 检查文件扩展名
        if not allowed_file(file.filename):
            logger.warning(f"[{client_ip}] 不允许的文件类型: {file.filename}")
            return jsonify({'success': False, 'error': f'不支持的文件类型，仅支持: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        # 读取文件数据
        file.seek(0)
        image_data = file.read()
        file_size = len(image_data)
        logger.info(f"[{client_ip}] 开始解析二维码，文件名: {file.filename}, 大小: {file_size} 字节")
        
        # 保存图片到服务器
        file.seek(0)  # 重置文件指针以便保存
        saved_path, saved_filename = save_uploaded_image(file, client_ip)
        
        if not saved_path:
            logger.warning(f"[{client_ip}] 图片保存失败，但继续处理")
        
        # 重置文件指针以便解析
        file.seek(0)
        image_data = file.read()
        
        # 解析二维码
        result, error = parse_qr_code(image_data)
        
        if error:
            logger.warning(f"[{client_ip}] 二维码解析失败: {error}")
            return jsonify({'success': False, 'error': error}), 400
        
        if result:
            # 检查是否是账户列表（迁移格式）
            if isinstance(result, list):
                logger.info(f"[{client_ip}] 成功解析迁移格式，提取到 {len(result)} 个账户")
                # 格式化账户列表
                formatted_accounts = []
                for account in result:
                    formatted_accounts.append({
                        'secret': account['secret'],
                        'formatted_secret': format_secret(account['secret']),
                        'name': account.get('name', ''),
                        'issuer': account.get('issuer', ''),
                        'algorithm': account.get('algorithm', 'SHA1'),
                        'digits': account.get('digits', 6),
                        'type': account.get('type', 'TOTP')
                    })
                    logger.debug(f"[{client_ip}] 账户: {account.get('name', '未知')} ({account.get('issuer', '未知')})")
                response_data = {
                    'success': True,
                    'is_migration': True,
                    'accounts': formatted_accounts,
                    'count': len(formatted_accounts)
                }
                if saved_filename:
                    response_data['saved_file'] = saved_filename
                return jsonify(response_data)
            else:
                logger.info(f"[{client_ip}] 成功提取单个密钥")
                # 单个密钥（标准格式）
                response_data = {
                    'success': True,
                    'is_migration': False,
                    'secret': result,
                    'formatted_secret': format_secret(result)
                }
                if saved_filename:
                    response_data['saved_file'] = saved_filename
                return jsonify(response_data)
        else:
            logger.warning(f"[{client_ip}] 无法提取密钥")
            return jsonify({'success': False, 'error': '无法提取密钥'}), 400
    
    except Exception as e:
        logger.error(f"[{client_ip}] 服务器错误: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'服务器错误: {str(e)}'}), 500

def format_secret(secret):
    """格式化密钥，每 4 个字符一组"""
    # 移除空格
    secret = secret.replace(' ', '')
    # 每 4 个字符添加一个空格
    return ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])

if __name__ == '__main__':
    import os
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    port = int(os.getenv('PORT', 5000))
    
    logger.info(f"启动 Flask 应用")
    logger.info(f"  调试模式: {debug_mode}")
    logger.info(f"  监听地址: 0.0.0.0:{port}")
    logger.info(f"  环境变量: FLASK_ENV={os.getenv('FLASK_ENV', 'development')}")
    logger.info("=" * 60)
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)

