"""
数据库解析

使用示例：
    from common.db_parser import sigdb, DB, SignalDef

    result = DB.can()              # 解析DBC/ARXML格式的数据库
    result = DB.can('FLC')         # 指定ECU名称过滤报文（TX∪RX）
    tx_msgs = DB.can('FLC').tx     # 获取ECU发送的报文
    rx_msgs = DB.can('FLC').rx     # 获取ECU接收的报文
    result = DB.lin()              # 解析LDF格式的LIN数据库

    # 获取信号定义
    sig_def = sigdb.get_signal_def('VehicleSpeed')

    # 获取报文信息
    msg_def = sigdb.get_msg_def(0x123)
    signals = sigdb.get_msg_signals(0x123)

    # 获取ECU发送/接收的报文ID和信号名
    tx_ids = sigdb.ecu_tx_msg_ids('FLC')
    rx_ids = sigdb.ecu_rx_msg_ids('FLC')
    tx_sigs = sigdb.ecu_tx_signal_names('FLC')
    rx_sigs = sigdb.ecu_rx_signal_names('FLC')
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from uvtest.testlog import TestLog


@dataclass
class SignalDef:
    name: str
    msg_id: int
    msg_name: str
    start_bit: int
    bit_length: int
    byte_order: str
    is_signed: bool
    factor: float = 1.0
    offset: float = 0.0
    init_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    unit: str = ""


@dataclass
class ParseResult:
    success: bool
    messages: Dict[int, dict] = field(default_factory=dict)
    db_names: List[str] = field(default_factory=list)
    error: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def tx(self) -> Dict[int, dict]:
        return self.extra.get('tx', {})

    @property
    def rx(self) -> Dict[int, dict]:
        return self.extra.get('rx', {})


class DB:
    @staticmethod
    def can(ecu_name: str = "") -> ParseResult:
        try:
            from env.config import DATABASE_TYPE
            db_type = DATABASE_TYPE or 'dbc'
        except Exception:
            db_type = 'dbc'
        return _parse_can_database(db_type, ecu_name)

    @staticmethod
    def lin() -> ParseResult:
        return _parse_ldf_database()


def _load_database_files(db_type: str) -> List[dict]:
    from env.config import Model
    dbs = []

    if db_type == 'dbc':
        from env.config import DBC_FILES
        for idx in DBC_FILES.keys():
            db = Model.dbc(idx)
            if db:
                dbs.append(db)

    elif db_type == 'arxml':
        from env.config import ARXML_CP_FILES
        for idx in ARXML_CP_FILES.keys():
            db = Model.arxml_cp(idx)
            if db and isinstance(db, dict) and 'msgs' in db:
                dbs.append(db)

    elif db_type == 'ldf':
        from env.config import LDF_FILES
        for idx in LDF_FILES.keys():
            db = Model.ldf(idx)
            if db:
                dbs.append(db)

    return dbs


def _parse_can_database(db_type: str, ecu_name: str = "") -> ParseResult:
    tag = db_type.upper() + "解析"
    TestLog('INFO', tag, f'开始解析 {db_type.upper()} 数据库...')

    def to_list(v):
        if not v:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.replace(';', ',').split(',') if s.strip()]
        return [str(x).strip() for x in (v if isinstance(v, (list, tuple, set)) else [v]) if x]

    try:
        ecu = ecu_name.strip().upper() if ecu_name else ""

        dbs = _load_database_files(db_type)
        if not dbs:
            TestLog('FAIL', tag, '未能加载数据库')
            return ParseResult(False, error="数据库加载失败")

        names = [d.get('name', '?') for d in dbs if isinstance(d, dict)]
        TestLog('INFO', tag, f'获取到 {len(dbs)} 个数据库: {names}')

        msgs, tx_msgs, rx_msgs, total = {}, {}, {}, 0
        for db in dbs:
            for msg in db.get('msgs', []) if isinstance(db, dict) else []:
                total += 1
                mid = int(msg.get('id', 0))

                tx_list = to_list(msg.get('tx_nodes') or msg.get('transmitter') or msg.get('Transmitter'))
                rx_list = to_list(msg.get('rx_nodes') or msg.get('receiver') or msg.get('Receiver'))

                if db_type == 'arxml':
                    is_tx = bool(tx_list)
                    is_rx = bool(rx_list)
                    if not is_tx and not is_rx:
                        continue
                else:
                    if ecu and ecu not in {t.upper() for t in tx_list} | {r.upper() for r in rx_list}:
                        continue
                    is_tx = ecu in {t.upper() for t in tx_list} if ecu else bool(tx_list)
                    is_rx = ecu in {r.upper() for r in rx_list} if ecu else bool(rx_list)

                msg_info = {
                    'dlc': int(msg.get('dlc', 0)),
                    'cycle': int(msg.get('cycle', 0) or 0),
                    'name': msg.get('name', f'Unknown_{mid:x}'),
                }
                if tx_list:
                    msg_info['tx_nodes'] = tx_list
                if rx_list:
                    msg_info['rx_nodes'] = rx_list

                sigs = {s.get('name'): s.get('init_value', 0)
                        for s in msg.get('signals', []) if s.get('name')}
                if sigs:
                    msg_info['signals'] = sigs

                msgs[mid] = msg_info

                if ecu:
                    if is_tx:
                        tx_msgs[mid] = msg_info
                    if is_rx:
                        rx_msgs[mid] = msg_info

        extra = {}
        if ecu:
            extra = {'tx': tx_msgs, 'rx': rx_msgs, 'ecu_name': ecu_name}
            TestLog('INFO', tag, f'ECU [{ecu_name}] 报文统计: TX(该ECU发送) {len(tx_msgs)} 条, RX(该ECU接收) {len(rx_msgs)} 条')
        return ParseResult(True, msgs, names, extra=extra)

    except Exception as e:
        TestLog('FAIL', tag, f'解析失败: {e}')
        return ParseResult(False, error=str(e))


def _parse_ldf_database() -> ParseResult:
    tag = "LDF解析"
    TestLog('INFO', tag, '开始解析 LDF 数据库...')

    try:
        dbs = _load_database_files('ldf')
        if not dbs:
            TestLog('FAIL', tag, '未能加载 LDF 数据库')
            return ParseResult(False, error="LDF数据库加载失败")

        names = [d.get('name', '?') for d in dbs if isinstance(d, dict)]
        TestLog('INFO', tag, f'获取到 {len(dbs)} 个 LDF 数据库: {names}')

        extra = {}
        msgs = {}

        for db in dbs:
            if not isinstance(db, dict):
                continue

            if 'network_name' not in extra and db.get('name'):
                extra['network_name'] = db['name']

            for node in db.get('nodes', []):
                nm = node.get('name')
                if not nm:
                    continue
                extra.setdefault('nodes', []).append(node)
                if node.get('is_master'):
                    extra['master_name'] = nm
                else:
                    extra.setdefault('slave_names', []).append(nm)

            tables = db.get('tables', [])
            if tables and 'schedule_tables' not in extra:
                extra['schedule_tables'] = tables
                extra['schedule_indexes'] = list(range(len(tables)))
                diag_frame_names = {'masterreq', 'slaveresp'}
                normal_indexes = []
                for i, t in enumerate(tables):
                    table_name = (t.get('name') or '').lower()
                    if 'diag' in table_name:
                        continue
                    slots = t.get('slots', [])
                    has_diag_frame = any(
                        (s.get('name') or '').lower() in diag_frame_names
                        for s in slots
                    )
                    if not has_diag_frame:
                        normal_indexes.append(i)
                extra['normal_indexes'] = normal_indexes

            for msg in db.get('msgs', []):
                fid = int(msg.get('id', 0))
                pubs = msg.get('publisher', [])
                sigs = msg.get('signals', [])
                msgs[fid] = {
                    'dlc': int(msg.get('dlc', 0)),
                    'name': msg.get('name', f'Unknown_{fid:x}'),
                    'nodeName': pubs[0] if isinstance(pubs, list) and pubs else '',
                    'signals': sigs,
                    'publishers': pubs
                }

        TestLog('INFO', tag, f'解析完成: {len(msgs)} 个 LIN 帧')
        return ParseResult(True, msgs, names, extra=extra)
    except Exception as e:
        TestLog('FAIL', tag, f'解析失败: {e}')
        return ParseResult(False, error=str(e))


def _extract_bits_little_endian(data: bytes, start_bit: int, bit_length: int) -> int:
    if not data or bit_length <= 0:
        return 0

    result = 0
    for i in range(bit_length):
        bit_pos = start_bit + i
        byte_idx = bit_pos // 8
        bit_idx = bit_pos % 8
        if byte_idx < len(data):
            if data[byte_idx] & (1 << bit_idx):
                result |= (1 << i)
    return result


def _extract_bits_big_endian(data: bytes, start_bit: int, bit_length: int) -> int:
    if not data or bit_length <= 0:
        return 0

    result = 0
    start_byte = start_bit // 8
    start_bit_in_byte = start_bit % 8

    bits_collected = 0
    byte_idx = start_byte
    bit_idx = start_bit_in_byte

    while bits_collected < bit_length and byte_idx < len(data):
        if data[byte_idx] & (1 << bit_idx):
            result |= (1 << (bit_length - 1 - bits_collected))
        bits_collected += 1
        bit_idx -= 1
        if bit_idx < 0:
            bit_idx = 7
            byte_idx += 1

    return result


def _as_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "signed", "-"}:
        return True
    if s in {"0", "false", "no", "unsigned", "+"}:
        return False
    return bool(default)


def extract_signal(data: bytes, sig_def: SignalDef) -> Tuple[int, float]:
    if sig_def.byte_order == 'big_endian':
        raw = _extract_bits_big_endian(data, sig_def.start_bit, sig_def.bit_length)
    else:
        raw = _extract_bits_little_endian(data, sig_def.start_bit, sig_def.bit_length)

    if sig_def.is_signed and sig_def.bit_length > 0:
        sign_bit = 1 << (sig_def.bit_length - 1)
        if raw & sign_bit:
            raw -= (1 << sig_def.bit_length)

    # phy = raw * factor + offset
    phy = raw * sig_def.factor + sig_def.offset

    return raw, phy


class SignalDatabase:
    def __init__(self):
        self._loaded = False
        self._signal_defs: Dict[str, SignalDef] = {}    # 信号名 -> 信号定义
        self._msg_signals: Dict[int, List[str]] = {}    # 报文ID -> 信号名列表
        self._msg_defs: Dict[int, dict] = {}            # 报文ID -> 报文定义
        self._msg_tx_nodes: Dict[int, List[str]] = {}   # 报文ID -> 发送节点列表
        self._msg_rx_nodes: Dict[int, List[str]] = {}   # 报文ID -> 接收节点列表


    def get_signal_def(self, name: str) -> Optional[SignalDef]:
        self._ensure_loaded()
        return self._signal_defs.get(name)

    def get_msg_signals(self, msg_id: int) -> List[str]:
        self._ensure_loaded()
        return self._msg_signals.get(msg_id, [])

    def get_msg_def(self, msg_id: int) -> Optional[dict]:
        self._ensure_loaded()
        return self._msg_defs.get(msg_id)

    def get_signal_names(self) -> List[str]:
        self._ensure_loaded()
        return list(self._signal_defs.keys())

    def get_msg_ids(self) -> List[int]:
        self._ensure_loaded()
        return list(self._msg_defs.keys())
        
    def ecu_tx_msg_ids(self, ecu_name: str = "") -> List[int]:
        self._ensure_loaded()
        from env.config import DATABASE_TYPE
        if DATABASE_TYPE == "arxml":
            return list(self._msg_tx_nodes.keys())
        ecu = self._get_ecu_name(ecu_name)
        if not ecu:
            return []
        return [mid for mid, nodes in self._msg_tx_nodes.items()
                if ecu in {n.upper() for n in nodes}]

    def ecu_rx_msg_ids(self, ecu_name: str = "") -> List[int]:
        self._ensure_loaded()
        from env.config import DATABASE_TYPE
        if DATABASE_TYPE == "arxml":
            return list(self._msg_rx_nodes.keys())
        ecu = self._get_ecu_name(ecu_name)
        if not ecu:
            return []
        return [mid for mid, nodes in self._msg_rx_nodes.items()
                if ecu in {n.upper() for n in nodes}]

    def ecu_tx_signal_names(self, ecu_name: str = "") -> List[str]:
        tx_ids = set(self.ecu_tx_msg_ids(ecu_name))
        return [name for name, sig in self._signal_defs.items() if sig.msg_id in tx_ids]

    def ecu_rx_signal_names(self, ecu_name: str = "") -> List[str]:
        rx_ids = set(self.ecu_rx_msg_ids(ecu_name))
        return [name for name, sig in self._signal_defs.items() if sig.msg_id in rx_ids]

    def _get_ecu_name(self, ecu_name: str = "") -> str:
        if ecu_name:
            return ecu_name.strip().upper()
        try:
            from common.params import P
            return (P.ECUInfo.ECUName or '').strip().upper()
        except Exception:
            return ""

    def get_unused_bits(self, msg_id: int) -> List[int]:
        self._ensure_loaded()

        msg_def = self._msg_defs.get(msg_id)
        if not msg_def:
            return []
        total_bits = msg_def.get('data_len', 8) * 8
        used_bits = set()


        for sig_name in self._msg_signals.get(msg_id, []):
            if sig_def := self._signal_defs.get(sig_name):
                used_bits.update(self._calculate_signal_bits(sig_def, total_bits))

        return sorted(set(range(total_bits)) - used_bits)

    def check_unused_bits_value(self, msg_id: int, data: bytes,
                                 expected_value: int = 0x00) -> Tuple[bool, List[int]]:
        unused_bits = self.get_unused_bits(msg_id)
        if not unused_bits:
            return True, []

        expected_bit = 1 if expected_value == 0xFF else 0
        mismatched = []

        for bit_idx in unused_bits:
            byte_idx, bit_in_byte = divmod(bit_idx, 8)
            if byte_idx >= len(data):
                mismatched.append(bit_idx)
            elif ((data[byte_idx] >> bit_in_byte) & 1) != expected_bit:
                mismatched.append((byte_idx, bit_in_byte))

        return len(mismatched) == 0, mismatched
        
    @staticmethod
    def _to_list(v) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.replace(';', ',').split(',') if s.strip()]
        return [str(x).strip() for x in (v if isinstance(v, (list, tuple, set)) else [v]) if x]

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_database()
        self._loaded = True

    def _load_database(self) -> None:
        try:
            from env.config import Model, DATABASE_TYPE

            dbs = []
            if DATABASE_TYPE == "dbc":
                from env.config import DBC_FILES
                for idx in DBC_FILES.keys():
                    db = Model.dbc(idx)
                    if db and 'msgs' in db:
                        dbs.append(db)
            elif DATABASE_TYPE == "arxml":
                from env.config import ARXML_CP_FILES
                for idx in ARXML_CP_FILES.keys():
                    db = Model.arxml_cp(idx)
                    if db and isinstance(db, dict) and 'msgs' in db:
                        dbs.append(db)
            elif DATABASE_TYPE == "ldf":
                from env.config import LDF_FILES
                for idx in LDF_FILES.keys():
                    db = Model.ldf(idx)
                    if db and 'msgs' in db:
                        dbs.append(db)

            for db in dbs:
                for msg in db.get('msgs', []):
                    msg_id = int(msg.get('id', 0))
                    msg_name = msg.get('name', f'Unknown_{msg_id:x}')
                    dlc_to_bytes = {
                        0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
                        9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64
                    }
                    data_len = dlc_to_bytes.get(msg.get('dlc', 8), 8)
                    tx_nodes = self._to_list(msg.get('tx_nodes'))
                    rx_nodes = self._to_list(msg.get('rx_nodes'))

                    self._msg_defs[msg_id] = {
                        'name': msg_name,
                        'data_len' : data_len,
                        'dlc': msg.get('dlc', 8),
                        'cycle': msg.get('cycle', 0),
                    }

                    if tx_nodes:
                        self._msg_tx_nodes[msg_id] = tx_nodes
                    if rx_nodes:
                        self._msg_rx_nodes[msg_id] = rx_nodes

                    self._parse_message_signals(msg, msg_id, msg_name)

        except Exception as e:
            print(f"[SignalDatabase] 数据库加载失败: {e}")

    def _parse_message_signals(self, msg: dict, msg_id: int, msg_name: str) -> None:
        for sig in msg.get('signals', []):
            sig_name = sig.get('name', '')
            if not sig_name:
                continue

            byte_order_raw = sig.get('byte_order', 'little_endian')
            if isinstance(byte_order_raw, int):
                byte_order = 'big_endian' if byte_order_raw == 0 else 'little_endian'
            else:
                byte_order = str(byte_order_raw).lower()

            sig_def = SignalDef(
                name=sig_name,
                msg_id=msg_id,
                msg_name=msg_name,
                start_bit=int(sig.get('start_bit', 0)),
                bit_length=int(sig.get('bit_length', 0) or sig.get('length', 0)),
                byte_order=byte_order,
                is_signed=_as_bool(sig.get('is_signed', False)),
                factor=float(sig.get('factor', 1.0) or 1.0),
                offset=float(sig.get('offset', 0.0) or 0.0),
                init_value=float(sig.get('init_value', 0.0) or 0.0),
                min_value=float(sig.get('min_value', 0.0) or sig.get('min', 0.0) or 0.0),
                max_value=float(sig.get('max_value', 0.0) or sig.get('max', 0.0) or 0.0),
                unit=str(sig.get('unit', '')),
            )

            self._signal_defs[sig_name] = sig_def

            if msg_id not in self._msg_signals:
                self._msg_signals[msg_id] = []
            self._msg_signals[msg_id].append(sig_name)

    def _calculate_signal_bits(self, sig_def: SignalDef, total_bits: int) -> List[int]:
        bits = []

        if sig_def.byte_order == 'big_endian':
            byte_idx, bit_idx = divmod(sig_def.start_bit, 8)
            for _ in range(sig_def.bit_length):
                bits.append(byte_idx * 8 + bit_idx)
                bit_idx -= 1
                if bit_idx < 0:
                    bit_idx, byte_idx = 7, byte_idx + 1
        else:
            bits = list(range(sig_def.start_bit, sig_def.start_bit + sig_def.bit_length))

        return [b for b in bits if b < total_bits]

    def encode_msg_with_init_values(self, msg_id: int, unused_bit_value: int = 0x00) -> bytes:
        self._ensure_loaded()

        msg_def = self._msg_defs.get(msg_id)
        if not msg_def:
            return b'\x00' * 8

        dlc = msg_def.get('dlc', 8)
        fill_byte = 0xFF if unused_bit_value == 0xFF else 0x00
        data = bytearray([fill_byte] * dlc)

        for sig_name in self._msg_signals.get(msg_id, []):
            sig_def = self._signal_defs.get(sig_name)
            if not sig_def:
                continue

            init_phy = sig_def.init_value
            if sig_def.factor != 0:
                raw_value = int((init_phy - sig_def.offset) / sig_def.factor)
            else:
                raw_value = int(init_phy)

            max_raw = (1 << sig_def.bit_length) - 1
            if sig_def.is_signed:
                min_raw = -(1 << (sig_def.bit_length - 1))
                max_raw = (1 << (sig_def.bit_length - 1)) - 1
                raw_value = max(min_raw, min(max_raw, raw_value))
                if raw_value < 0:
                    raw_value = raw_value + (1 << sig_def.bit_length)
            else:
                raw_value = max(0, min(max_raw, raw_value))

            if sig_def.byte_order == 'big_endian':
                self._encode_big_endian(data, sig_def.start_bit, sig_def.bit_length, raw_value)
            else:
                self._encode_little_endian(data, sig_def.start_bit, sig_def.bit_length, raw_value)

        return bytes(data)

    def _encode_little_endian(self, data: bytearray, start_bit: int, bit_length: int, value: int) -> None:
        for i in range(bit_length):
            bit_pos = start_bit + i
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8
            if byte_idx < len(data):
                if value & (1 << i):
                    data[byte_idx] |= (1 << bit_idx)
                else:
                    data[byte_idx] &= ~(1 << bit_idx)

    def _encode_big_endian(self, data: bytearray, start_bit: int, bit_length: int, value: int) -> None:
        byte_idx = start_bit // 8
        bit_idx = start_bit % 8
        # for i in range(bit_length):
        #     if byte_idx < len(data):
        #         if value & (1 << (bit_length - 1 - i)):
        #             data[byte_idx] |= (1 << bit_idx)
        #         else:
        #             data[byte_idx] &= ~(1 << bit_idx)
        #     bit_idx -= 1
        #     if bit_idx < 0:
        #         bit_idx = 7
        #         byte_idx += 1
        for i in range(bit_length):
            if byte_idx < len(data):
                # ✅ 修改这里：value & (1 << i) 替代 value & (1 << (bit_length - 1 - i))
                if value & (1 << i):
                    data[byte_idx] |= (1 << bit_idx)
                else:
                    data[byte_idx] &= ~(1 << bit_idx)
            
            bit_idx -= 1
            if bit_idx < 0:
                bit_idx = 7
                byte_idx += 1


sigdb = SignalDatabase()


def parse_database(db_type: str = 'auto', ecu_name: str = "") -> ParseResult:
    if db_type in ('ldf', 'lin'):
        return DB.lin()
    return DB.can(ecu_name)



