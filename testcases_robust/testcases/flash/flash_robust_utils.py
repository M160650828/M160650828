"""
Flash/Bootloader 鲁棒性测试辅助工具

基于UDS诊断服务实现刷写流程的鲁棒性测试：
- $10 02: 编程会话控制
- $27: 安全访问
- $31 RoutineControl: 刷写前置检查、擦除内存
- $34 RequestDownload: 下载请求
- $36 TransferData: 数据传输
- $37 RequestTransferExit: 传输退出

不执行实际Flash写入，仅通过诊断服务交互验证ECU的异常处理能力。

参考: testcases/bootloader/utils/bootloader_utils.py
"""

# 辅助函数已直接内联到 flash_robust_testcase.py 中。
# 如果未来需要更多可复用的Flash鲁棒性测试工具，在此补充。
