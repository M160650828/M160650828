def parse_hex(hex_file_path):
    """
    解析HEX文件，返回所有连续数据段拼接后的数据块及起始地址。
    
    返回值:
        - data_blocks: 列表，每个元素为字典，包含 'address' 和 'data'
        - start_address: 首个数据块的地址（若文件无数据，返回None）
    """
    with open(hex_file_path, 'r') as f:
        lines = f.readlines()
    
    data_blocks = []          # 存储所有数据块 [{address: int, data: bytes}, ...]
    upper_address = 0x0000    # 扩展线性地址（类型04）
    current_segment = 0x0000  # 扩展段地址（类型02）
    start_address = None

    current_block_addr = None
    current_block_data = bytearray()
    last_data_end_addr = None

    for line in lines:
        line = line.strip()
        if not line.startswith(':'):
            continue
        
        # 解析字段
        byte_count = int(line[1:3], 16)
        address = int(line[3:7], 16)
        record_type = int(line[7:9], 16)
        data_bytes = bytes.fromhex(line[9:-2])
        checksum = int(line[-2:], 16)
        
        # 校验和验证
        computed_sum = sum(bytes.fromhex(line[1:-2])) & 0xFF
        computed_checksum = (0x100 - computed_sum) & 0xFF
        if checksum != computed_checksum:
            raise ValueError(f"校验和错误: {line}")
        
        # 处理记录类型
        if record_type == 0x00:  # 数据记录
            # 计算完整地址（支持段地址和线性地址）
            if upper_address != 0x0000:
                full_address = (upper_address << 16) + address
            else:
                full_address = (current_segment << 4) + address

            # 如果是第一个数据块
            if current_block_addr is None:
                current_block_addr = full_address
                current_block_data = bytearray(data_bytes)
                last_data_end_addr = full_address + len(data_bytes)
                if start_address is None:
                    start_address = full_address
            else:
                # 判断是否与上一个数据块连续
                if full_address == last_data_end_addr:
                    # 连续，拼接
                    current_block_data.extend(data_bytes)
                    last_data_end_addr = full_address + len(data_bytes)
                else:
                    # 不连续，先保存前一个数据块
                    data_blocks.append({
                        'address': current_block_addr,
                        'data': bytes(current_block_data)
                    })
                    # 开始新的数据块
                    current_block_addr = full_address
                    current_block_data = bytearray(data_bytes)
                    last_data_end_addr = full_address + len(data_bytes)
                    if start_address is None:
                        start_address = full_address

        elif record_type == 0x02:  # 扩展段地址
            current_segment = int.from_bytes(data_bytes, byteorder='big')
        elif record_type == 0x04:  # 扩展线性地址
            upper_address = int.from_bytes(data_bytes, byteorder='big')
        elif record_type == 0x01:  # 文件结束
            break

    # 文件结束后，别忘了保存最后一个数据块
    if current_block_addr is not None and current_block_data:
        data_blocks.append({
            'address': current_block_addr,
            'data': bytes(current_block_data)
        })

    return data_blocks, start_address



if __name__ == "__main__":
    hex_file = r"C:\Users\xuefeilong\Desktop\s19_bin_parser\files\PLCM_BOD13A001_APP01.01.11_250612\1-driver.hex"
    hex_file = r"C:\Users\xuefeilong\Desktop\s19_bin_parser\files\PLCM_BOD13A001_APP01.01.11_250612\2-app.hex"
    hex_file = r"C:\Users\xuefeilong\Desktop\s19_bin_parser\files\PICU_POW05A001_APP01.02.05_250612_HWV1.01\2-app-SHA-PICU-Hex-R01-U1-PPV4-CRC-release.hex"
    data_blocks, start_addr = parse_hex(hex_file)

    # 打印输出
    if start_addr is not None:
        print(f"文件起始地址: 0x{start_addr:08X}")
        for idx, block in enumerate(data_blocks):
            print(f"数据块 {idx + 1}:")
            print(f"  起始地址: 0x{block['address']:08X}")
            print(f"  数据长度: {hex(len(block['data']))} 字节")
            block_data = block['data']
            print(f"  数据内容: {block_data[:10].hex().upper()}...{block_data[-10:].hex().upper()}")
    else:
        print("HEX文件中未找到有效数据记录！")