from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import datetime
import os

app = Flask(__name__)
# 允许跨域请求，方便网页JavaScript调用
CORS(app)

DATABASE = 'api_data.db'

def get_db():
    """获取数据库连接"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    """初始化数据库表"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                number INTEGER NOT NULL CHECK (number BETWEEN 1 AND 5),
                ip_address TEXT,
                request_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

@app.teardown_appcontext
def close_connection(exception):
    """关闭数据库连接"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def get_client_ip():
    """从请求头获取客户端IP地址"""
    # 尝试从常见代理头中获取IP
    ip_headers = [
        'X-Forwarded-For',
        'X-Real-IP',
        'Proxy-Client-IP',
        'WL-Proxy-Client-IP',
        'HTTP_CLIENT_IP',
        'HTTP_X_FORWARDED_FOR'
    ]
    
    for header in ip_headers:
        ip = request.headers.get(header)
        if ip and ip.lower() != 'unknown':
            # X-Forwarded-For可能包含多个IP，取第一个
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            return ip
    
    # 如果没有代理头，使用remote_addr
    return request.remote_addr or '0.0.0.0'

@app.route('/api/record', methods=['POST', 'OPTIONS'])
def record_data():
    """接收并记录数据的API端点"""
    
    # 处理预检请求（CORS）
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
        for key, value in headers.items():
            response.headers[key] = value
        return response
    
    try:
        # 获取JSON数据
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # 验证必需字段
        if 'number' not in data:
            return jsonify({'error': 'Missing required field: number'}), 400
        
        number = data['number']
        
        # 验证数字范围
        if not isinstance(number, int) or number < 1 or number > 5:
            return jsonify({'error': 'Number must be an integer between 1 and 5'}), 400
        
        # 自动从请求头获取IP地址
        ip_address = get_client_ip()
        
        # 获取当前时间
        timestamp = datetime.datetime.now().isoformat()
        
        # 获取请求来源信息（可选）
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # 存入数据库
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            'INSERT INTO api_records (timestamp, number, ip_address) VALUES (?, ?, ?)',
            (timestamp, number, ip_address)
        )
        db.commit()
        
        # 记录日志（可选）
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
              f"记录评分: {number}星, IP: {ip_address}, "
              f"User-Agent: {user_agent[:50]}...")
        
        # 返回成功响应
        return jsonify({
            'status': 'success',
            'message': 'Data recorded successfully',
            'record_id': cursor.lastrowid,
            'timestamp': timestamp,
            'number': number,
            'ip_address': ip_address,
            'auto_detected_ip': True  # 标记IP是自动获取的
        }), 201
        
    except Exception as e:
        print(f"记录数据时出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({'status': 'healthy'}), 200

def create_app():
    """创建并配置应用"""
    # 确保数据库目录存在
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE)), exist_ok=True)
    
    # 初始化数据库
    init_db()
    
    return app

if __name__ == '__main__':
    # 创建应用
    app = create_app()
    
    # 启动服务器，监听所有接口的2347端口
    print(f"启动课本评分数据收集API...")
    print(f"服务端口: 2347")
    print(f"数据库文件: {os.path.abspath(DATABASE)}")
    print(f"API端点: POST /api/record")
    print(f"IP获取方式: 自动从请求头获取")
    print(f"=" * 50)
    print(f"注意: 不再需要手动传递ip_address参数")
    print(f"=" * 50)
    
    app.run(host='0.0.0.0', port=2347, debug=False)