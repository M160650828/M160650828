from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._base import DEFAULT_DIR, DEFAULT_MAP, Fmt, ParamSource
from .project_info import ProjectInfoCfg
from .ecu_info import ECUInfoCfg
from .can_info import CANInfoCfg
from .lin_info import LINInfoCfg
from .nm_info import NMInfoCfg
from .tp_info import TpInfoCfg
from .e2e_info import E2EInfoCfg
from .channel_info import ChannelMappingCfg
from .routing_info import RoutingInfoCfg
from .dtc_info import (
    DTCInfoCfg,
    ExtendedDTCInfoCfg,
    LostCommDTCCfg, BusOffDTCCfg, VoltageDTCCfg, AllSupportDTCCfg, InvalidDataDTCCfg,
    LostCommDTCItem, BusOffDTCItem, VoltageDTCItem, AllSupportDTCItem, InvalidDataDTCItem,
)
from .bootloader_info import BootloaderInfoCfg
from .did_info import (
    DIDCategoryCfg, DIDInfoCfg, DataItemCfg,
    DIDItem, ConfigDIDItem, ControlDIDItem, RoutineDIDItem,
    ReadDIDItem, WriteDIDItem, ConditionItem,
    ReadDIDsCfg, WriteDIDsCfg, ConditionsCfg,
)
from .sig_info import SIG_INFO_CFG
from .diag_service_info import DiagServiceInfoCfg

class Parameters:
    def __init__(self, src: Optional[ParamSource] = None) -> None:
        src = src or ParamSource(DEFAULT_DIR, DEFAULT_MAP)
        pj = src.load("ProjectInfo")
        ecu = src.load("ECUInfo")
        cani = src.load("CANInfo")
        lini = src.load("LINInfo")
        nmi = src.load("NMInfo")
        tpi = src.load("TpInfo")
        e2e = src.load("E2EInfo")
        chm = src.load("ChannelMapping")
        rti = src.load("RoutingInfo")

        pj_raw = dict(pj) if isinstance(pj, dict) else {}
        self.ProjectInfo = ProjectInfoCfg(pj_raw)

        ecu_items: List[Dict[str, Any]] = []
        if isinstance(ecu, list):
            ecu_items = [it for it in ecu if isinstance(it, dict)]
        elif isinstance(ecu, dict):
            ecu_items = [ecu]

        ecu_selected: Dict[str, Any] = {}
        if ecu_items:
            target_idx = self.ProjectInfo.ECUIndex
            for item in ecu_items:
                try:
                    if Fmt.as_int(item.get("ECUIndex"), -1) == target_idx:
                        ecu_selected = dict(item)
                        break
                except Exception:
                    continue
            if not ecu_selected:
                ecu_selected = dict(ecu_items[0])

        self.ECUInfo = ECUInfoCfg(ecu_selected)
        self.CANInfo = CANInfoCfg(dict(cani) if isinstance(cani, dict) else {})
        self.LINInfo = LINInfoCfg(dict(lini) if isinstance(lini, dict) else {})
        self.NMInfo = NMInfoCfg(dict(nmi) if isinstance(nmi, dict) else {})
        self.TpInfo = TpInfoCfg(dict(tpi) if isinstance(tpi, dict) else {}, ecu=self.ECUInfo)
        self.E2EInfo = E2EInfoCfg(e2e if isinstance(e2e, (dict, list)) else {})
        self.ChannelMapping = ChannelMappingCfg(chm if isinstance(chm, (dict, list)) else [])
        self.RoutingInfo = RoutingInfoCfg(rti if isinstance(rti, (dict, list)) else [])

        # E2E DTCs
        e2e_dtcs = src.load("E2E_DTCs")
        self.E2E_DTCs = DTCInfoCfg(e2e_dtcs if isinstance(e2e_dtcs, (dict, list)) else [])

        bl = src.load("BootloaderInfo")
        self.BootloaderInfo = BootloaderInfoCfg(bl if isinstance(bl, list) else [])

        conditions = src.load("Conditions")
        read_dids = src.load("ReadDIDs")
        write_dids = src.load("WriteDIDs")
        self.Conditions = ConditionsCfg(conditions if isinstance(conditions, (dict, list)) else [])
        self.ReadDIDs = ReadDIDsCfg(read_dids if isinstance(read_dids, (dict, list)) else [])
        self.WriteDIDs = WriteDIDsCfg(write_dids if isinstance(write_dids, (dict, list)) else [])

        control_dids = src.load("ControlDIDs")
        routine_dids = src.load("RoutineDIDs")
        self.DIDInfo = DIDInfoCfg(
            logistic=DIDCategoryCfg([], "Logistic"),
            internal=DIDCategoryCfg([], "Internal"),
            config=DIDCategoryCfg([], "Config"),
            control=DIDCategoryCfg(control_dids if isinstance(control_dids, (dict, list)) else [], "Control"),
            routine=DIDCategoryCfg(routine_dids if isinstance(routine_dids, (dict, list)) else [], "Routine"),
        )

        global_data = src.load("GlobalData")
        self.GlobalData = DataItemCfg(global_data if isinstance(global_data, (dict, list)) else [])

        lost_comm_dtcs = src.load("LostCommunicationDTCs")
        bus_off_dtcs = src.load("BusOffDTCs")
        voltage_dtcs = src.load("VoltageDTCs")
        all_support_dtcs = src.load("AllSupportDTCs")
        invalid_data_dtcs = src.load("InvalidDataDTCs")
      
        self.ExtendedDTCInfo = ExtendedDTCInfoCfg(
            lost_communication=LostCommDTCCfg(
                lost_comm_dtcs if isinstance(lost_comm_dtcs, (dict, list)) else []
            ),
            bus_off=BusOffDTCCfg(
                bus_off_dtcs if isinstance(bus_off_dtcs, (dict, list)) else []
            ),
            voltage=VoltageDTCCfg(
                voltage_dtcs if isinstance(voltage_dtcs, (dict, list)) else []
            ),
            all_support=AllSupportDTCCfg(
                all_support_dtcs if isinstance(all_support_dtcs, (dict, list)) else []
            ),
            invalid_data=InvalidDataDTCCfg(
                invalid_data_dtcs if isinstance(invalid_data_dtcs, (dict, list)) else []
            ),
        )
        sig_info = src.load("SIG_INFO")
        self.sig_info = SIG_INFO_CFG(sig_info if isinstance(bus_off_dtcs, (dict, list)) else [])

        diag_svc = src.load("DiagServiceInfo")
        self.DiagServiceInfo = DiagServiceInfoCfg(dict(diag_svc) if isinstance(diag_svc, dict) else {})


P = Parameters()

