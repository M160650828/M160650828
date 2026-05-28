import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uvtest.framework import set_report_config
from uvtest.syslog import output_log
from env.test_session import SessionFixture as _SessionFixture

MODULE_NAME = "ECU Robustness Test"
FILE_BASE   = "ECU_Robustness_Test"

set_report_config(module_name=MODULE_NAME, file_base=FILE_BASE)


class SessionFixture(_SessionFixture):
    def session_setup(self):
        try:
            output_log("DEBUG", "配置加载", "开始加载鲁棒性测试配置...")

            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            excel_path = os.path.join(project_root, "testinputs", "CANLinTestParameters.xlsx")

            self._export_excel_to_json(excel_path)
            self._setup_report_config(excel_path)

            output_log("DEBUG", "配置加载", "鲁棒性测试配置加载成功")
        except Exception as e:
            output_log("FAIL", "配置加载", f"鲁棒性测试配置加载失败: {e}")

    @staticmethod
    def _setup_report_config(excel_path):
        ecu_name = None
        try:
            from uvtest.config_excel import ExcelReader
            if excel_path and os.path.exists(excel_path):
                proj = ExcelReader.read_col_dict(excel_path, "ProjectInfo", 0, 2)
                ecu_index = proj.get("ECUIndex", 1)
                rows = ExcelReader.read_row_dicts(excel_path, "ECUInfo", 0, 1)
                ecu_name = next(
                    (r["ECUName"] for r in rows if r.get("ECUIndex") == ecu_index), None)
        except Exception:
            pass

        ecu_prefix = ""
        if ecu_name:
            name_str = str(ecu_name).strip()
            safe = "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in name_str)
            safe = safe.strip("_")
            if safe:
                ecu_prefix = f"{safe}_"

        report_title = f"{ecu_name} - {MODULE_NAME}" if ecu_name else MODULE_NAME
        set_report_config(
            module_name=MODULE_NAME,
            report_title=report_title,
            file_prefix=ecu_prefix,
            file_base=FILE_BASE,
        )
