"""
JWT处理器 - SaaS量化交易平台
JWT生成、验证和刷新机制
"""
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import current_app


class JWTHandler:
    """JWT Token处理器"""

    # Token类型
    ACCESS_TOKEN = "access"
    REFRESH_TOKEN = "refresh"

    @staticmethod
    def generate_token(
        user_id: int,
        tenant_id: int,
        role: str,
        token_type: str = "access",
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        生成JWT Token

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            role: 用户角色
            token_type: token类型 (access/refresh)
            expires_delta: 过期时间间隔

        Returns:
            JWT Token字符串
        """
        if expires_delta is None:
            # 默认过期时间：access token 2小时，refresh token 7天
            if token_type == JWTHandler.ACCESS_TOKEN:
                expires_delta = timedelta(hours=2)
            else:
                expires_delta = timedelta(days=7)

        now = datetime.utcnow()
        expire = now + expires_delta

        payload = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "type": token_type,
            "iat": now,
            "exp": expire,
        }

        # 使用Flask SECRET_KEY
        secret_key = current_app.config.get("SECRET_KEY", "dev-secret-key")
        token = jwt.encode(payload, secret_key, algorithm="HS256")
        
        return token

    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """
        解码并验证JWT Token

        Args:
            token: JWT Token字符串

        Returns:
            解码后的payload，验证失败返回None
        """
        try:
            secret_key = current_app.config.get("SECRET_KEY", "dev-secret-key")
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        """
        验证Access Token

        Args:
            token: JWT Token字符串

        Returns:
            验证成功返回payload，失败返回None
        """
        payload = JWTHandler.decode_token(token)
        
        if payload is None:
            return None
        
        # 检查token类型
        if payload.get("type") != JWTHandler.ACCESS_TOKEN:
            return None
        
        return payload

    @staticmethod
    def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
        """
        验证Refresh Token

        Args:
            token: JWT Token字符串

        Returns:
            验证成功返回payload，失败返回None
        """
        payload = JWTHandler.decode_token(token)
        
        if payload is None:
            return None
        
        # 检查token类型
        if payload.get("type") != JWTHandler.REFRESH_TOKEN:
            return None
        
        return payload

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        """
        使用Refresh Token刷新Access Token

        Args:
            refresh_token: Refresh Token字符串

        Returns:
            新的Access Token，失败返回None
        """
        payload = JWTHandler.verify_refresh_token(refresh_token)
        
        if payload is None:
            return None
        
        # 生成新的access token
        new_access_token = JWTHandler.generate_token(
            user_id=payload["user_id"],
            tenant_id=payload["tenant_id"],
            role=payload["role"],
            token_type=JWTHandler.ACCESS_TOKEN
        )
        
        return new_access_token

    @staticmethod
    def generate_token_pair(user_id: int, tenant_id: int, role: str) -> Dict[str, str]:
        """
        生成Access Token和Refresh Token对

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            role: 用户角色

        Returns:
            {"access_token": "...", "refresh_token": "..."}
        """
        access_token = JWTHandler.generate_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            token_type=JWTHandler.ACCESS_TOKEN
        )
        
        refresh_token = JWTHandler.generate_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            token_type=JWTHandler.REFRESH_TOKEN
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
