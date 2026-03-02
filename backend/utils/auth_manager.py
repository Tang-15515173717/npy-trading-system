"""
认证管理器 - JWT Token + Session管理
实现功能：
1. JWT Token生成和验证
2. Session管理（Redis/内存存储）
3. 同账号互踢机制
4. Token过期自动续期
"""
import jwt
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import current_app
import redis
import json

# 内存存储（开发环境，生产环境应使用Redis）
_memory_sessions = {}


class AuthManager:
    """认证管理器"""
    
    # Token配置
    TOKEN_EXPIRE_HOURS = 24  # Token有效期24小时
    REFRESH_EXPIRE_DAYS = 7  # 刷新Token有效期7天
    SECRET_KEY = "stockquant-pro-secret-key-2026"  # 应该从环境变量读取
    
    def __init__(self, use_redis=False):
        """
        初始化认证管理器
        
        Args:
            use_redis: 是否使用Redis存储（生产环境推荐）
        """
        self.use_redis = use_redis
        if use_redis:
            try:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True
                )
                self.redis_client.ping()
            except:
                print("⚠️ Redis连接失败，使用内存存储")
                self.use_redis = False
    
    def generate_token(self, user_id: int, tenant_id: int, email: str) -> Dict[str, str]:
        """
        生成访问Token和刷新Token
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            email: 用户邮箱
        
        Returns:
            包含access_token和refresh_token的字典
        """
        now = datetime.utcnow()
        
        # 访问Token（短期）
        access_payload = {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'email': email,
            'type': 'access',
            'exp': now + timedelta(hours=self.TOKEN_EXPIRE_HOURS),
            'iat': now
        }
        access_token = jwt.encode(access_payload, self.SECRET_KEY, algorithm='HS256')
        
        # 刷新Token（长期）
        refresh_payload = {
            'user_id': user_id,
            'type': 'refresh',
            'exp': now + timedelta(days=self.REFRESH_EXPIRE_DAYS),
            'iat': now
        }
        refresh_token = jwt.encode(refresh_payload, self.SECRET_KEY, algorithm='HS256')
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': self.TOKEN_EXPIRE_HOURS * 3600
        }
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证Token
        
        Args:
            token: JWT Token
        
        Returns:
            解码后的payload，如果验证失败返回None
        """
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=['HS256'])
            
            # 检查是否在黑名单中（用于注销）
            if self._is_token_blacklisted(token):
                return None
            
            return payload
        except jwt.ExpiredSignatureError:
            print("Token已过期")
            return None
        except jwt.InvalidTokenError as e:
            print(f"Token无效: {e}")
            return None
    
    def create_session(self, user_id: int, tenant_id: int, token: str) -> str:
        """
        创建Session并实现互踢机制
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            token: 访问Token
        
        Returns:
            Session ID
        """
        session_id = f"session:{user_id}:{int(time.time())}"
        
        # 检查是否存在旧Session（互踢机制）
        old_session_key = f"user_session:{user_id}"
        old_session_id = self._get(old_session_key)
        
        if old_session_id:
            # 将旧Token加入黑名单
            self._blacklist_token(old_session_id)
            print(f"🔄 用户 {user_id} 的旧Session已被踢出")
        
        # 创建新Session
        session_data = {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'token': token,
            'created_at': datetime.utcnow().isoformat(),
            'last_activity': datetime.utcnow().isoformat()
        }
        
        # 存储Session数据
        self._set(session_id, json.dumps(session_data), ex=self.TOKEN_EXPIRE_HOURS * 3600)
        
        # 存储用户->Session映射（用于互踢）
        self._set(old_session_key, session_id, ex=self.TOKEN_EXPIRE_HOURS * 3600)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Session数据
        
        Args:
            session_id: Session ID
        
        Returns:
            Session数据，如果不存在或过期返回None
        """
        data = self._get(session_id)
        if not data:
            return None
        
        try:
            session_data = json.loads(data)
            
            # 更新最后活动时间
            session_data['last_activity'] = datetime.utcnow().isoformat()
            self._set(session_id, json.dumps(session_data), ex=self.TOKEN_EXPIRE_HOURS * 3600)
            
            return session_data
        except:
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除Session（注销）
        
        Args:
            session_id: Session ID
        
        Returns:
            是否成功删除
        """
        session_data = self.get_session(session_id)
        if session_data:
            # 将Token加入黑名单
            token = session_data.get('token')
            if token:
                self._blacklist_token(token)
            
            # 删除Session
            user_id = session_data.get('user_id')
            if user_id:
                self._delete(f"user_session:{user_id}")
            
            return self._delete(session_id)
        return False
    
    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        使用刷新Token获取新的访问Token
        
        Args:
            refresh_token: 刷新Token
        
        Returns:
            新的Token对，如果失败返回None
        """
        payload = self.verify_token(refresh_token)
        if not payload or payload.get('type') != 'refresh':
            return None
        
        user_id = payload.get('user_id')
        
        # 从数据库获取用户信息
        from models.user import User
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return None
        
        # 生成新Token
        return self.generate_token(user.id, user.tenant_id, user.email)
    
    def _blacklist_token(self, token: str):
        """将Token加入黑名单"""
        blacklist_key = f"blacklist:{token}"
        self._set(blacklist_key, "1", ex=self.TOKEN_EXPIRE_HOURS * 3600)
    
    def _is_token_blacklisted(self, token: str) -> bool:
        """检查Token是否在黑名单中"""
        blacklist_key = f"blacklist:{token}"
        return self._get(blacklist_key) is not None
    
    # 存储抽象层（支持Redis和内存）
    def _get(self, key: str) -> Optional[str]:
        """获取值"""
        if self.use_redis:
            return self.redis_client.get(key)
        return _memory_sessions.get(key)
    
    def _set(self, key: str, value: str, ex: int = None):
        """设置值"""
        if self.use_redis:
            self.redis_client.set(key, value, ex=ex)
        else:
            _memory_sessions[key] = value
            # 内存模式下简单处理过期（不精确）
            if ex:
                import threading
                def delete_after():
                    time.sleep(ex)
                    _memory_sessions.pop(key, None)
                threading.Thread(target=delete_after, daemon=True).start()
    
    def _delete(self, key: str) -> bool:
        """删除值"""
        if self.use_redis:
            return self.redis_client.delete(key) > 0
        return _memory_sessions.pop(key, None) is not None


# 全局认证管理器实例
auth_manager = AuthManager(use_redis=False)  # 开发环境使用内存存储


def get_current_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """
    从Token获取当前用户信息
    
    Args:
        token: JWT Token
    
    Returns:
        用户信息字典，如果验证失败返回None
    """
    payload = auth_manager.verify_token(token)
    if not payload:
        return None
    
    return {
        'user_id': payload.get('user_id'),
        'tenant_id': payload.get('tenant_id'),
        'email': payload.get('email')
    }
