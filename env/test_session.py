import os
from uvtest.framework import TestFixture, set_report_config
from uvtest.syslog import output_log

MODULE_NAME = "ECU Basic Network Test"
FILE_BASE   = "ECU_Basic_Network_Test"

set_report_config(module_name=MODULE_NAME, file_base=FILE_BASE)

class SessionFixture(TestFixture):
    def session_setup(self):
        try:
            output_log("DEBUG", "配置加载", "开始加载测试配置...")

            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            excel_path = os.path.join(project_root, "testinputs", "CANLinTestParameters.xlsx")

            self._export_excel_to_json(excel_path)

            # 报告配置：模块名 + ECU 前缀 + 文件名
            self._setup_report_config(excel_path)

            output_log("DEBUG", "配置加载", "测试配置加载成功")
        except Exception as e:
            output_log("FAIL", "配置加载", f"测试配置加载失败: {e}")

    def session_teardown(self):
        try:
            #清理运行时环境
            from slplus.runtime import sl_runtime
            sl_runtime.deinit()
        except Exception as e:
            print(f"session_teardown: sl_runtime.deinit() 失败: {e}")

    @staticmethod
    def _setup_report_config(excel_path):
        """从Excel配置提取当前ECU名称，配置报告"""
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

    @staticmethod
    def _export_excel_to_json(excel_path):
        """将 Excel 配置导出为 JSON"""
        try:
            from uvtest.excel_to_json import ExcelJsonExporter
            if not excel_path or not os.path.exists(excel_path):
                return
            output_dir = os.path.join(os.path.dirname(excel_path), "json")
            config_path = os.path.join(output_dir, "sheet_config.json")
            ExcelJsonExporter(excel_path, output_dir, config_path=config_path).export_all()
            output_log("INFO", "配置转换", f"Excel 各 Sheet 已转 JSON 到: {output_dir}")
        except Exception as ex:
            output_log("WARN", "配置转换", f"Excel 转 JSON 失败: {ex}")

