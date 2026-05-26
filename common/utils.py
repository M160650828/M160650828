import sys
import os
from uvtest.testlog import TestLog
from uvtest.syslog import output_log

from common.can_utils import send_canmsg
from common.context import ctx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TimerCyclic:
    """周期性报文发送定时器"""
    _timers: dict = {}

    @classmethod
    def start(cls, timer_id, period_ms, fn, *args, **kwargs) -> bool:
        """
        启动周期性定时器
        """
        try:
            from slplus.timer import sl_timer
            tid = str(timer_id)
            period = int(period_ms)

            if tid in cls._timers:
                old_timer = cls._timers[tid].get('timer')
                try:
                    if old_timer is not None:
                        old_timer.stop_timer()
                        old_timer.destroy_timer()
                except Exception:
                    pass
                del cls._timers[tid]

            def timer_callback(_timer_handle, _user_data):
                try:
                    info = cls._timers.get(tid)
                    if not info or info.get('stopping'):
                        return
                    info['fn'](*info.get('args', ()), **info.get('kwargs', {}))
                    info['send_count'] += 1
                except Exception as e:
                    TestLog("FAIL", "定时器", f"定时器 {tid} 发送失败: {e}")

            t = sl_timer(period, timer_callback)
            if getattr(t, 'timer', None) is None:
                TestLog("FAIL", "定时器", f"创建定时器 {tid} 失败")
                return False

            cls._timers[tid] = {
                'timer': t,
                'fn': fn,
                'args': args,
                'kwargs': kwargs,
                'send_count': 0,
                'stopping': False
            }

            if not t.start_timer():
                TestLog("FAIL", "定时器", f"启动定时器 {tid} 失败")
                t.destroy_timer()
                del cls._timers[tid]
                return False

            return True

        except Exception as e:
            TestLog("FAIL", "定时器", f"设置定时器 {timer_id} 失败: {e}")
            return False

    @classmethod
    def stop(cls, timer_id) -> bool:
        """停止销毁周期性发送定时器"""
        try:
            tid = str(timer_id)
            if tid not in cls._timers:
                return False

            info = cls._timers[tid]
            t = info.get('timer')
            info['stopping'] = True

            if t is not None:
                t.stop_timer()
                t.destroy_timer()

            del cls._timers[tid]
            return True
        except Exception as e:
            TestLog("FAIL", "定时器", f"停止定时器 {timer_id} 失败: {e}")
            return False




