"""
EventStream: 实时可见 + 可恢复
目标：UI 实时看到执行过程，断线可恢复
"""
import asyncio
import json
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from runtime.platform.trace_store import TraceStore, TraceEvent

class EventStream:
    """事件流：SSE 或 WebSocket（推荐 SSE）"""
    
    def __init__(self, trace_store: TraceStore):
        self.trace_store = trace_store
        self.active_streams: Dict[str, asyncio.Queue] = {}
    
    async def stream_events(
        self,
        task_id: str,
        cursor: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        生成 SSE 事件流
        
        Yields:
            SSE 格式字符串
        """
        # 先发送历史事件（如果有 cursor）
        if cursor:
            events, _ = self.trace_store.load_events(task_id, cursor=cursor, limit=100)
            for event in events:
                yield self._format_sse_event(event)
        
        # 创建实时事件队列
        if task_id not in self.active_streams:
            self.active_streams[task_id] = asyncio.Queue()
        
        queue = self.active_streams[task_id]
        
        # 持续监听新事件
        while True:
            try:
                # 等待新事件（带超时，避免阻塞）
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield self._format_sse_event(event)
            except asyncio.TimeoutError:
                # 发送心跳
                yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.now().isoformat()})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                break
    
    def emit_event(self, task_id: str, event: TraceEvent):
        """发送事件到流"""
        # 保存到 trace_store
        self.trace_store.save_event(event)
        
        # 发送到活跃流
        if task_id in self.active_streams:
            try:
                self.active_streams[task_id].put_nowait(event)
            except asyncio.QueueFull:
                # 队列满，丢弃（或记录警告）
                pass
    
    def _format_sse_event(self, event: TraceEvent) -> str:
        """格式化 SSE 事件"""
        event_dict = {
            "event_id": event.event_id,
            "task_id": event.task_id,
            "ts": event.ts,
            "type": event.type,
            "payload_ref": event.payload_ref,
            "payload": event.payload
        }
        return f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"
    
    def close_stream(self, task_id: str):
        """关闭流"""
        if task_id in self.active_streams:
            del self.active_streams[task_id]


