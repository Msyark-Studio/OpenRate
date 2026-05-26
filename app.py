from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
from datetime import datetime, timedelta

# ==================== SQLite 日期适配器 ====================
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s.decode('utf-8'))

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)
sqlite3.register_converter("datetime", convert_datetime)
# ===========================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DATABASE_RATINGS'] = os.environ.get('DATABASE_RATINGS', 'api_data.db')
app.config['DATABASE_USERS'] = os.environ.get('DATABASE_USERS', 'user_data.db')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== 用户模型 ====================
class User(UserMixin):
    def __init__(self, id, username, is_admin=False):
        self.id = id
        self.username = username
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(app.config['DATABASE_USERS'], detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, is_admin FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(id=user_data[0], username=user_data[1], is_admin=bool(user_data[2]))
    return None

# ==================== 配置管理函数 ====================
def get_setting(key, default=''):
    conn = get_users_db()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        if key == 'guest_mode':
            return row[0] == '1'
        return row[0]
    if key == 'guest_mode':
        return False
    if key == 'site_icon':
        return 'fas fa-star'
    if key == 'site_title':
        return 'OpenRate'
    return default

def set_setting(key, value):
    if isinstance(value, bool):
        value = '1' if value else '0'
    conn = get_users_db()
    cursor = conn.cursor()
    cursor.execute('REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (key, value))
    conn.commit()
    conn.close()

# ==================== 数据库初始化 ====================
def init_databases():
    conn_users = sqlite3.connect(app.config['DATABASE_USERS'], detect_types=sqlite3.PARSE_DECLTYPES)
    cursor_users = conn_users.cursor()
    cursor_users.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor_users.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn_users.commit()
    conn_users.close()

def get_ratings_db():
    return sqlite3.connect(app.config['DATABASE_RATINGS'], detect_types=sqlite3.PARSE_DECLTYPES)

def get_users_db():
    return sqlite3.connect(app.config['DATABASE_USERS'], detect_types=sqlite3.PARSE_DECLTYPES)

def query_db(query, args=(), one=False):
    conn = get_ratings_db()
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# ==================== 首次配置检查 ====================
@app.before_request
def check_setup():
    if request.endpoint in ('static', 'setup', 'login', 'health'):
        return
    conn = get_users_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    if count == 0:
        return redirect(url_for('setup'))

def guest_allowed():
    """检查当前是否允许访客访问"""
    if current_user.is_authenticated:
        return True
    return get_setting('guest_mode', False)

# ==================== 路由 ====================
@app.route('/setup', methods=['GET', 'POST'])
def setup():
    conn = get_users_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    if count > 0:
        flash('系统已配置，如需重新配置请清空数据库。', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        site_title = request.form.get('site_title', 'OpenRate')
        if not username or not password or not confirm_password:
            flash('请填写所有字段', 'error')
            return render_template('setup.html')
        if password != confirm_password:
            flash('两次密码输入不一致', 'error')
            return render_template('setup.html')
        if len(password) < 6:
            flash('密码长度至少6位', 'error')
            return render_template('setup.html')

        password_hash = generate_password_hash(password)
        conn = get_users_db()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                           (username, password_hash, 1))
            cursor.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', ('site_title', site_title))
            cursor.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', ('site_icon', 'fas fa-star'))
            cursor.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', ('guest_mode', '0'))
            conn.commit()
            flash('配置完成，请登录', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash(f'配置失败: {str(e)}', 'error')
        finally:
            conn.close()
    return render_template('setup.html')

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    if not current_user.is_admin:
        flash('无权限访问此页面', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        site_title = request.form.get('site_title', 'OpenRate')
        site_icon = request.form.get('site_icon', 'fas fa-star')
        guest_mode = request.form.get('guest_mode') == 'on'
        set_setting('site_title', site_title)
        set_setting('site_icon', site_icon)
        set_setting('guest_mode', guest_mode)
        flash('设置已更新', 'success')
        return redirect(url_for('settings_page'))

    current_title = get_setting('site_title', 'OpenRate')
    current_icon = get_setting('site_icon', 'fas fa-star')
    current_guest = get_setting('guest_mode', False)
    return render_template('settings.html', site_title=current_title, site_icon=current_icon, guest_mode=current_guest)

@app.context_processor
def inject_settings():
    return {
        'site_title': get_setting('site_title', 'OpenRate'),
        'site_icon': get_setting('site_icon', 'fas fa-star')
    }

@app.route('/')
def index():
    if not current_user.is_authenticated and not guest_allowed():
        return redirect(url_for('login'))
    is_guest = not current_user.is_authenticated
    return render_template('index.html', is_guest=is_guest, is_admin=current_user.is_authenticated and current_user.is_admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_users_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash, is_admin FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        conn.close()
        if user_data and check_password_hash(user_data[2], password):
            user = User(id=user_data[0], username=user_data[1], is_admin=bool(user_data[3]))
            login_user(user)
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误！', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('无权限访问管理员页面！', 'error')
        return redirect(url_for('index'))
    conn = get_users_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_user':
            username = request.form.get('username')
            password = request.form.get('password')
            is_admin = 1 if request.form.get('is_admin') else 0
            if username and password:
                try:
                    password_hash = generate_password_hash(password)
                    cursor.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                                   (username, password_hash, is_admin))
                    conn.commit()
                    flash(f'用户 {username} 添加成功！', 'success')
                except sqlite3.IntegrityError:
                    flash(f'用户名 {username} 已存在！', 'error')
        elif action == 'delete_user':
            user_id = request.form.get('user_id')
            if user_id and user_id != str(current_user.id):
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                conn.commit()
                flash('用户删除成功！', 'success')
        elif action == 'change_password':
            user_id = request.form.get('user_id')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            if user_id and new_password and confirm_password:
                if new_password != confirm_password:
                    flash('两次输入的密码不一致！', 'error')
                else:
                    if str(current_user.id) == user_id or current_user.is_admin:
                        password_hash = generate_password_hash(new_password)
                        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
                        conn.commit()
                        if str(current_user.id) == user_id:
                            flash('密码修改成功，请重新登录！', 'success')
                            conn.close()
                            logout_user()
                            return redirect(url_for('login'))
                        else:
                            flash('密码修改成功！', 'success')
                    else:
                        flash('无权限修改此用户的密码！', 'error')
    cursor.execute('SELECT id, username, is_admin, created_at FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    conn.close()
    return render_template('admin.html', users=users, current_user_id=current_user.id)

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not current_password or not new_password or not confirm_password:
            flash('请填写所有字段！', 'error')
            return render_template('change_password.html')
        if new_password != confirm_password:
            flash('两次输入的新密码不一致！', 'error')
            return render_template('change_password.html')
        conn = get_users_db()
        cursor = conn.cursor()
        cursor.execute('SELECT password_hash FROM users WHERE id = ?', (current_user.id,))
        user_data = cursor.fetchone()
        if user_data and check_password_hash(user_data[0], current_password):
            password_hash = generate_password_hash(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, current_user.id))
            conn.commit()
            conn.close()
            flash('密码修改成功，请重新登录！', 'success')
            logout_user()
            return redirect(url_for('login'))
        else:
            conn.close()
            flash('当前密码错误！', 'error')
    return render_template('change_password.html')

# ==================== API 路由 ====================
@app.route('/api/dashboard')
def get_dashboard():
    if not current_user.is_authenticated and not guest_allowed():
        return jsonify({'success': False, 'error': '未授权'}), 401
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        conn = get_ratings_db()
        cursor = conn.cursor()
        today = datetime.now().date()
        today_str = today.isoformat()
        yesterday_str = (today - timedelta(days=1)).isoformat()
        where_clause = ''
        params = []
        if date_from:
            where_clause += ' AND timestamp >= ?'
            params.append(date_from)
        if date_to:
            date_to_end = date_to + 'T23:59:59'
            where_clause += ' AND timestamp <= ?'
            params.append(date_to_end)
        cursor.execute(f'SELECT COUNT(*), AVG(number) FROM api_records WHERE timestamp LIKE ? {where_clause}', [today_str + '%'] + params)
        today_data = cursor.fetchone()
        cursor.execute(f'SELECT COUNT(*), AVG(number) FROM api_records WHERE timestamp LIKE ? {where_clause}', [yesterday_str + '%'] + params)
        yesterday_data = cursor.fetchone()
        cursor.execute(f'SELECT COUNT(*), AVG(number) FROM api_records WHERE 1=1 {where_clause}', params)
        total_data = cursor.fetchone()
        cursor.execute(f'SELECT number as rating, COUNT(*) as count FROM api_records WHERE 1=1 {where_clause} GROUP BY number ORDER BY number', params)
        rating_dist = cursor.fetchall()
        seven_days_ago = (today - timedelta(days=7)).isoformat()
        cursor.execute(f'SELECT SUBSTR(timestamp, 1, 10) as date, COUNT(*) as count, AVG(number) as avg_rating FROM api_records WHERE timestamp >= ? {where_clause} GROUP BY date ORDER BY date', [seven_days_ago] + params)
        weekly_data = cursor.fetchall()
        if not date_from and not date_to:
            thirty_days_ago = (today - timedelta(days=30)).isoformat()
            cursor.execute('SELECT SUBSTR(timestamp, 1, 10) as date, COUNT(*) as count, AVG(number) as avg_rating FROM api_records WHERE timestamp >= ? GROUP BY date ORDER BY date', [thirty_days_ago])
        else:
            chart_params = []
            chart_where = ''
            if date_from:
                chart_where += ' AND timestamp >= ?'
                chart_params.append(date_from)
            if date_to:
                date_to_end = date_to + 'T23:59:59'
                chart_where += ' AND timestamp <= ?'
                chart_params.append(date_to_end)
            cursor.execute(f'SELECT SUBSTR(timestamp, 1, 10) as date, COUNT(*) as count, AVG(number) as avg_rating FROM api_records WHERE 1=1 {chart_where} GROUP BY date ORDER BY date', chart_params)
        chart_data = cursor.fetchall()
        conn.close()
        return jsonify({
            'success': True,
            'dashboard': {
                'today': {'count': today_data[0] or 0, 'avg_rating': round(today_data[1] or 0, 2)},
                'yesterday': {'count': yesterday_data[0] or 0, 'avg_rating': round(yesterday_data[1] or 0, 2)},
                'total': {'count': total_data[0] or 0, 'avg_rating': round(total_data[1] or 0, 2)},
                'rating_distribution': [{'rating': row[0], 'count': row[1]} for row in rating_dist],
                'weekly_data': [{'date': row[0], 'count': row[1], 'avg_rating': round(row[2] or 0, 2)} for row in weekly_data],
                'chart_data': [{'date': row[0], 'count': row[1], 'avg_rating': round(row[2] or 0, 2)} for row in chart_data]
            }
        })
    except Exception as e:
        print(f"获取仪表板数据错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ratings')
@login_required
def get_ratings():
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        query = 'SELECT id, timestamp, number as rating, ip_address, request_time FROM api_records WHERE 1=1'
        count_query = 'SELECT COUNT(*) FROM api_records WHERE 1=1'
        params = []
        if date_from:
            query += ' AND timestamp >= ?'
            count_query += ' AND timestamp >= ?'
            params.append(date_from)
        if date_to:
            date_to_end = date_to + 'T23:59:59'
            query += ' AND timestamp <= ?'
            count_query += ' AND timestamp <= ?'
            params.append(date_to_end)
        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([per_page, offset])
        records = query_db(query, params)
        total = query_db(count_query, params[:len(params)-2] if date_from or date_to else [], one=True)[0]
        result = [{'id': row[0], 'timestamp': row[1], 'rating': row[2], 'ip_address': row[3], 'request_time': row[4]} for row in records]
        stats_query = 'SELECT COUNT(*) as total_count, AVG(number) as avg_rating FROM api_records WHERE 1=1'
        stats_params = []
        if date_from:
            stats_query += ' AND timestamp >= ?'
            stats_params.append(date_from)
        if date_to:
            date_to_end = date_to + 'T23:59:59'
            stats_query += ' AND timestamp <= ?'
            stats_params.append(date_to_end)
        stats_row = query_db(stats_query, stats_params, one=True)
        dist_query = 'SELECT number as rating, COUNT(*) as count FROM api_records WHERE 1=1'
        dist_params = []
        if date_from:
            dist_query += ' AND timestamp >= ?'
            dist_params.append(date_from)
        if date_to:
            date_to_end = date_to + 'T23:59:59'
            dist_query += ' AND timestamp <= ?'
            dist_params.append(date_to_end)
        dist_query += ' GROUP BY number ORDER BY number'
        dist_rows = query_db(dist_query, dist_params)
        rating_counts = {row[0]: row[1] for row in dist_rows}
        return jsonify({
            'success': True,
            'data': result,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            },
            'stats': {
                'total_count': stats_row[0] if stats_row else 0,
                'avg_rating': round(stats_row[1] if stats_row and stats_row[1] else 0, 2),
                'rating_counts': rating_counts
            }
        })
    except Exception as e:
        print(f"获取评分数据错误: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ratings/<int:rating_id>', methods=['DELETE'])
@login_required
def delete_rating(rating_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '需要管理员权限'}), 403
    try:
        conn = get_ratings_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM api_records WHERE id = ?', (rating_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '记录删除成功'})
    except Exception as e:
        print(f"删除评分记录错误: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ratings/<int:rating_id>', methods=['PUT'])
@login_required
def update_rating(rating_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '需要管理员权限'}), 403
    try:
        data = request.get_json()
        new_rating = data.get('rating')
        if not new_rating or int(new_rating) < 1 or int(new_rating) > 5:
            return jsonify({'success': False, 'error': '评分必须在1-5之间'}), 400
        conn = get_ratings_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE api_records SET number = ?, timestamp = ? WHERE id = ?', (new_rating, datetime.now().isoformat(), rating_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '记录更新成功'})
    except Exception as e:
        print(f"更新评分记录错误: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health_check():
    try:
        conn = get_ratings_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM api_records')
        conn.close()
        return jsonify({'status': 'healthy', 'service': 'bookweb_rate_display', 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    print("正在初始化数据库...")
    init_databases()
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    print(f"启动课本评分可视化系统...")
    print(f"访问地址: http://0.0.0.0:2348")
    print("首次运行请访问 /setup 进行配置")
    app.run(host='0.0.0.0', port=2348, debug=False)