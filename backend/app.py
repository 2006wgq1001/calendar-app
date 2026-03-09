from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
from models import db, Event, User
from datetime import datetime
import os 

app = Flask(__name__)
CORS(app, 
     origins=["http://localhost:3000", "http://localhost:3003"],  # include whichever port React uses
     # you can also use origins="*" during development to avoid this issue
     supports_credentials=True, 
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# 配置会话
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 在生产环境中应该使用环境变量
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # 允许跨域请求携带cookies
app.config['SESSION_COOKIE_SECURE'] = False  # 开发环境使用HTTP
Session(app)

# 配置数据库
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# 创建数据库表（如果文件损坏则删除重建）
with app.app_context():
    try:
        db.create_all()
        print("数据库表创建成功！")
    except Exception as e:
        print("数据库初始化出错：", e)
        # sqlite 常见的损坏问题，尝试删除文件并重新创建
        if 'disk image is malformed' in str(e):
            db_path = os.path.join(basedir, 'database.db')
            try:
                os.remove(db_path)
                print("损坏的数据库已删除，重新创建中…")
                db.create_all()
                print("数据库已重新创建。")
            except Exception as exc:
                print("重新创建数据库失败：", exc)
        else:
            raise


# 测试路由
@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Calendar API is running", "status": "ok"})


@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"message": "API is working"})


# 用户数据现在保存在数据库中，默认账户可以通过初始化脚本创建
# （如有需要，后续可添加迁移或预填充逻辑）


# 登录路由
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400

    user = User.query.filter_by(username=username).first()
    if user and user.password == password:
        session['user'] = {'id': user.id, 'username': user.username, 'name': user.name}
        return jsonify({'success': True, 'user': user.to_dict(), 'message': '登录成功'})
    else:
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401


@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    if 'user' in session:
        uid = session['user']['id']
        user = User.query.get(uid)
        if not user:
            session.pop('user', None)
            return jsonify({'error': '用户不存在'}), 401
        return jsonify({'user': user.to_dict()})
    else:
        return jsonify({'error': '未登录'}), 401

@app.route('/api/profile', methods=['GET'])
def get_profile():
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    uid = session['user']['id']
    user = User.query.get(uid)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    return jsonify({'success': True, 'user': user.to_dict()})

@app.route('/api/profile', methods=['PUT'])
def update_profile():
    if 'user' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    uid = session['user']['id']
    user = User.query.get(uid)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': '无效的JSON'}), 400

    try:
        for field in ['email', 'bio', 'name', 'gender', 'birthdate', 'avatar']:
            if field in data:
                setattr(user, field, data[field])
                session['user'][field] = data[field]
        db.session.commit()
        return jsonify({'success': True, 'user': user.to_dict()})
    except Exception as exc:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'服务器错误: {str(exc)}'}), 500

# 注册路由
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'}), 400

    try:
        new_user = User(
            username=username,
            password=password,
            name=username,
            email=data.get('email', ''),
            bio=data.get('bio', ''),
            gender=data.get('gender', ''),
            birthdate=data.get('birthdate', ''),
            avatar=data.get('avatar', ''),
        )
        db.session.add(new_user)
        db.session.commit()

        session['user'] = {'id': new_user.id, 'username': new_user.username, 'name': new_user.name}
        return jsonify({'success': True, 'user': new_user.to_dict(), 'message': '注册成功'})
    except Exception as exc:
        db.session.rollback()
        # log exception
        print('register error', exc)
        return jsonify({'success': False, 'message': '注册失败，请稍后再试'}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True, 'message': '已退出登录'})


@app.route('/api/events', methods=['GET'])
def get_events():
    """获取当前登录用户的事件，支持按年月过滤"""
    if 'user' not in session:
        return jsonify({"error": "请先登录"}), 401
    uid = session['user']['id']
    try:
        year = request.args.get('year')
        month = request.args.get('month')

        query = Event.query.filter_by(user_id=uid)

        if year and month:
            start_date = datetime(int(year), int(month), 1).date()
            if int(month) == 12:
                end_date = datetime(int(year) + 1, 1, 1).date()
            else:
                end_date = datetime(int(year), int(month) + 1, 1).date()
            query = query.filter(
                Event.start_date >= start_date,
                Event.start_date < end_date
            )

        events = query.all()
        return jsonify([event.to_dict(include_user=True) for event in events])
    except Exception as e:
        print(f"错误: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    """获取单个事件（仅限自己的事件）"""
    if 'user' not in session:
        return jsonify({"error": "请先登录"}), 401
    uid = session['user']['id']
    event = Event.query.get_or_404(event_id)
    if event.user_id != uid:
        return jsonify({"error": "无权访问此事件"}), 403
    return jsonify(event.to_dict(include_user=True))


@app.route('/api/events', methods=['POST'])
def create_event():
    """创建新事件并关联当前用户"""
    if 'user' not in session:
        return jsonify({"error": "请先登录"}), 401
    uid = session['user']['id']
    try:
        data = request.json or {}
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()

        event = Event(
            user_id=uid,
            title=data['title'],
            description=data.get('description', ''),
            start_date=start_date,
            end_date=end_date,
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            color=data.get('color', '#3788d8')
        )

        db.session.add(event)
        db.session.commit()
        return jsonify(event.to_dict()), 201
    except Exception as e:
        print(f"创建事件错误: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@app.route('/api/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    """更新事件，仅限所属用户"""
    if 'user' not in session:
        return jsonify({"error": "请先登录"}), 401
    uid = session['user']['id']
    try:
        event = Event.query.get_or_404(event_id)
        if event.user_id != uid:
            return jsonify({"error": "无权修改此事件"}), 403
        data = request.json or {}

        event.title = data.get('title', event.title)
        event.description = data.get('description', event.description)

        if data.get('start_date'):
            event.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        if data.get('end_date'):
            event.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        if data.get('start_time') is not None:
            event.start_time = data['start_time']
        if data.get('end_time') is not None:
            event.end_time = data['end_time']
        if data.get('color'):
            event.color = data['color']

        db.session.commit()
        return jsonify(event.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    """删除事件，仅限所属用户"""
    if 'user' not in session:
        return jsonify({"error": "请先登录"}), 401
    uid = session['user']['id']
    try:
        event = Event.query.get_or_404(event_id)
        if event.user_id != uid:
            return jsonify({"error": "无权删除此事件"}), 403
        db.session.delete(event)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# 返回当前用户的个人信息以及所有事件
@app.route('/api/user-data', methods=['GET'])
def user_data():
    if 'user' not in session:
        return jsonify({"error": "请先登录"}), 401
    uid = session['user']['id']
    user = User.query.get(uid)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    events = Event.query.filter_by(user_id=uid).all()
    return jsonify({
        'user': user.to_dict(),
        'events': [e.to_dict() for e in events]
    })

    """删除事件"""
    if 'user' not in session:
        return jsonify({"error": "请先登录"}), 401

    try:
        event = Event.query.get_or_404(event_id)
        db.session.delete(event)
        db.session.commit()
        return jsonify({'message': 'Event deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    print("启动日历API服务器...")
    print("访问 http://localhost:5000 测试API")
    print("访问 http://localhost:5000/api/events 获取事件")
    app.run(debug=True, port=5000, host='0.0.0.0')