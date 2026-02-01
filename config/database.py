"""
NL2SQL 数据库配置模块
"""
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    """数据库配置 - 支持 Supabase PostgreSQL"""
    
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'postgres')
    DB_DRIVER = os.getenv('DB_DRIVER', 'postgresql')  # postgresql 或 mysql
    
    @staticmethod
    def get_connection_string():
        """获取数据库连接字符串"""
        driver = DatabaseConfig.DB_DRIVER
        if driver == 'postgresql':
            # Supabase PostgreSQL 连接字符串
            return f"postgresql+psycopg2://{DatabaseConfig.DB_USER}:{DatabaseConfig.DB_PASSWORD}@{DatabaseConfig.DB_HOST}:{DatabaseConfig.DB_PORT}/{DatabaseConfig.DB_NAME}"
        else:
            # MySQL 连接字符串
            return f"mysql+pymysql://{DatabaseConfig.DB_USER}:{DatabaseConfig.DB_PASSWORD}@{DatabaseConfig.DB_HOST}:{DatabaseConfig.DB_PORT}/{DatabaseConfig.DB_NAME}"
