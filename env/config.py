import os
from common.params import P

# 测试输入物路径
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'testinputs')

# 数据库类型和文件配置
DATABASE_TYPE = P.ECUInfo.DataBaseType 

# 数据库文件
DBC1, LDF1, ARXML1 = 1, 1, 1
DBC_FILES = {DBC1: P.ECUInfo.DataBaseDBCName} if P.ECUInfo.DataBaseDBCName else {}
LDF_FILES = {LDF1: P.ECUInfo.DataBaseLDFName} if P.ECUInfo.DataBaseLDFName else {}
ARXML_CP_FILES = {ARXML1: P.ECUInfo.DataBaseDBCName} if DATABASE_TYPE == "arxml" else {}

# 通道配置:硬件SN号和逻辑通道号
DEFAULT_HW_SN = getattr(P.ProjectInfo, "NetWorkHardwareSN", "") or "30513024300058"
CAN1 = P.ECUInfo.CommCANChannelNum or 1
CAN2 = P.ECUInfo.BOBControlCan or 2
LIN1 = P.ECUInfo.LINChannelNum or 1

# CAN 通道映射: {逻辑通道号: "SN_CAN_物理通道号"}
CAN_CHANNELS = {CAN1: f"{DEFAULT_HW_SN}_CAN_{CAN1}", CAN2: f"{DEFAULT_HW_SN}_CAN_{CAN2}"}
LIN_CHANNELS = {LIN1: f"{DEFAULT_HW_SN}_LIN_{LIN1}"}

# 路由通道映射: 
NET_TO_CHANNEL = {}
_ch = max(CAN_CHANNELS.keys()) + 1
for _net, _hwid in P.ChannelMapping.map_net_to_hwid.items():
    _exist = next((c for c, h in CAN_CHANNELS.items() if h == _hwid), None)
    if _exist:
        NET_TO_CHANNEL[_net] = _exist
    else:
        CAN_CHANNELS[_ch], NET_TO_CHANNEL[_net], _ch = _hwid, _ch, _ch + 1

# 通道列表
DEFAULT_CAN_CHANNELS = [CAN1, CAN2]                      # 默认通道
ROUTING_CAN_CHANNELS = list(set(NET_TO_CHANNEL.values()))  # 路由通道
DEFAULT_LIN_CHANNEL = LIN1
CAN_TERMINATION = {CAN1: True}


LIN_NETWORK_DEFS = {
    LIN1: "LIN 1"
}

MESSAGE_COUNT_OUTPUT_INTERVAL = 10
LOG_LEVELS = {'INFO': 'INFO', 'WARNING': 'WARNING', 'FAIL': 'FAIL', 'PASS': 'PASS', 'DEBUG': 'DEBUG'}
BLF = 2

from slplus.model import sl_model
Model = sl_model()

def __init__():
    print("=" * 70)
    print("[配置初始化]", __file__)
    print("=" * 70)

    Model.set_model_root(DATABASE_DIR)

    if DATABASE_TYPE == "arxml":
        print(f"[配置初始化] 检测到 ARXML 数据库: {ARXML_CP_FILES}")
        Model.set_arxml_cp_files(ARXML_CP_FILES)
    elif DATABASE_TYPE == "dbc":
        print(f"[配置初始化] 检测到 DBC 数据库: {DBC_FILES}")
        Model.set_dbc_files(DBC_FILES)
    elif DATABASE_TYPE == "ldf":
        print(f"[配置初始化] 检测到 LDF 数据库: {LDF_FILES}")
        Model.set_ldf_files(LDF_FILES)

    Model.set_linnet_configs(LIN_NETWORK_DEFS)
    Model.set_can_mapping(CAN_CHANNELS)
    Model.set_lin_mapping(LIN_CHANNELS)
    try:
        Model.initialize()
    except Exception as e:
        print(f"[配置初始化] 数据库初始化失败（部分功能不可用）: {e}")

    print("=" * 70)
    print("[配置初始化] 完成")
    print("=" * 70)

__init__()
