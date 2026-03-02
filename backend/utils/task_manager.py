"""
异步任务管理器 - StockQuant Pro
支持后台执行、进度更新、任务停止等功能
"""
import threading
import time
from typing import Dict, Callable, Any, Optional
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class AsyncTask:
    """异步任务"""

    def __init__(self, task_id: str, func: Callable, *args, **kwargs):
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.thread = None
        self.should_stop = False
        self.lock = threading.Lock()

    def start(self):
        """启动任务"""
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        """任务执行逻辑"""
        with self.lock:
            self.status = TaskStatus.RUNNING
            self.started_at = datetime.now()

        try:
            # 执行任务函数，传递任务对象以便更新进度和检查停止标志
            self.result = self.func(self, *self.args, **self.kwargs)

            if not self.should_stop:
                with self.lock:
                    self.status = TaskStatus.COMPLETED
                    self.completed_at = datetime.now()
        except Exception as e:
            with self.lock:
                self.status = TaskStatus.FAILED
                self.error = str(e)
                self.completed_at = datetime.now()
        finally:
            if self.should_stop:
                with self.lock:
                    self.status = TaskStatus.STOPPED
                    self.completed_at = datetime.now()

    def stop(self):
        """停止任务"""
        with self.lock:
            self.should_stop = True
            if self.status == TaskStatus.PENDING:
                self.status = TaskStatus.STOPPED
                self.completed_at = datetime.now()

    def update_progress(self, progress: int):
        """更新进度"""
        with self.lock:
            self.progress = max(0, min(100, progress))

    def is_running(self) -> bool:
        """检查是否正在运行"""
        with self.lock:
            return self.status == TaskStatus.RUNNING and self.thread and self.thread.is_alive()

    def get_info(self) -> Dict[str, Any]:
        """获取任务信息"""
        with self.lock:
            return {
                "task_id": self.task_id,
                "status": self.status.value,
                "progress": self.progress,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "error": self.error,
            }


class TaskManager:
    """任务管理器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.tasks: Dict[str, AsyncTask] = {}
        self.lock = threading.Lock()

    def submit(self, task_id: str, func: Callable, *args, **kwargs) -> AsyncTask:
        """提交新任务"""
        with self.lock:
            if task_id in self.tasks:
                # 清理旧任务
                old_task = self.tasks[task_id]
                if old_task.is_running():
                    old_task.stop()

            task = AsyncTask(task_id, func, *args, **kwargs)
            self.tasks[task_id] = task
            task.start()
            return task

    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """获取任务"""
        with self.lock:
            return self.tasks.get(task_id)

    def stop_task(self, task_id: str) -> bool:
        """停止任务"""
        task = self.get_task(task_id)
        if task:
            task.stop()
            return True
        return False

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        with self.lock:
            now = datetime.now()
            to_remove = []
            for task_id, task in self.tasks.items():
                if not task.is_running() and task.completed_at:
                    age = (now - task.completed_at).total_seconds() / 3600
                    if age > max_age_hours:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self.tasks[task_id]

            return len(to_remove)


# 全局任务管理器实例
task_manager = TaskManager()
