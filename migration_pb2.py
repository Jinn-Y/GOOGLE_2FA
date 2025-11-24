# -*- coding: utf-8 -*-
# Generated protobuf definitions for Google Authenticator migration format
# This file defines the structure of the migration payload

class OtpType:
    """OTP 类型枚举"""
    OTP_TYPE_UNSPECIFIED = 0
    OTP_TYPE_HOTP = 1
    OTP_TYPE_TOTP = 2

class OtpAlgorithm:
    """OTP 算法枚举"""
    ALGORITHM_UNSPECIFIED = 0
    ALGORITHM_SHA1 = 1
    ALGORITHM_SHA256 = 2
    ALGORITHM_SHA512 = 3
    ALGORITHM_MD5 = 4

class OtpDigits:
    """OTP 位数枚举"""
    DIGIT_COUNT_UNSPECIFIED = 0
    DIGIT_COUNT_SIX = 1
    DIGIT_COUNT_EIGHT = 2

def parse_migration_payload(data):
    """
    解析 Google Authenticator 迁移格式的 protobuf 数据
    
    Args:
        data: 解码后的二进制数据
        
    Returns:
        list: 账户列表，每个账户包含 secret, name, issuer, algorithm, digits, type
    """
    accounts = []
    i = 0
    
    # Protobuf 格式解析
    # 迁移格式的结构大致为:
    # Payload {
    #   1: repeated OtpParameters {
    #      secret: bytes (field 1)
    #      name: string (field 2)
    #      issuer: string (field 3)
    #      algorithm: enum (field 4)
    #      digits: enum (field 5)
    #      type: enum (field 6)
    #   }
    # }
    
    while i < len(data):
        # 查找 OtpParameters 消息 (tag 1, wire type 2 = length-delimited)
        if i + 2 <= len(data):
            # 检查是否是字段标签 1 (OtpParameters 数组)
            tag = data[i]
            if (tag & 0x07) == 2:  # Wire type 2 (length-delimited)
                field_number = tag >> 3
                if field_number == 1:  # Payload.otp_parameters
                    i += 1
                    # 读取长度
                    length, length_bytes = read_varint(data, i)
                    i += length_bytes
                    
                    if i + length <= len(data):
                        # 解析单个 OtpParameters
                        account = parse_otp_parameters(data[i:i+length])
                        if account:
                            accounts.append(account)
                        i += length
                        continue
        
        # 如果当前字节不是有效字段，尝试查找其他模式
        # 直接查找 secret 字段 (tag 1, wire type 2)
        if i + 1 < len(data):
            tag = data[i]
            if tag == 0x0A:  # Field 1, wire type 2 (0x08 | 0x02 = 0x0A)
                i += 1
                # 读取 secret 长度
                secret_length, length_bytes = read_varint(data, i)
                i += length_bytes
                
                if i + secret_length <= len(data):
                    secret_bytes = data[i:i+secret_length]
                    # 尝试将 secret 转换为 base32
                    secret_base32 = bytes_to_base32(secret_bytes)
                    if secret_base32:
                        account = {
                            'secret': secret_base32,
                            'name': '',
                            'issuer': '',
                            'algorithm': 'SHA1',
                            'digits': 6,
                            'type': 'TOTP'
                        }
                        # 继续查找 name 和 issuer
                        j = i + secret_length
                        if j + 1 < len(data):
                            # 查找 name (field 2, tag 0x12)
                            if data[j] == 0x12:
                                j += 1
                                name_length, len_bytes = read_varint(data, j)
                                j += len_bytes
                                if j + name_length <= len(data):
                                    account['name'] = data[j:j+name_length].decode('utf-8', errors='ignore')
                                    j += name_length
                        
                        if j + 1 < len(data):
                            # 查找 issuer (field 3, tag 0x1A)
                            if data[j] == 0x1A:
                                j += 1
                                issuer_length, len_bytes = read_varint(data, j)
                                j += len_bytes
                                if j + issuer_length <= len(data):
                                    account['issuer'] = data[j:j+issuer_length].decode('utf-8', errors='ignore')
                        
                        accounts.append(account)
                        i = j if 'j' in locals() else i + secret_length
                        continue
        
        i += 1
    
    return accounts

def read_varint(data, offset):
    """
    读取 protobuf varint 值
    
    Returns:
        tuple: (value, bytes_read)
    """
    result = 0
    shift = 0
    bytes_read = 0
    
    for i in range(offset, min(offset + 10, len(data))):
        byte = data[i]
        bytes_read += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    
    return result, bytes_read

def bytes_to_base32(secret_bytes):
    """
    将字节数组转换为 base32 字符串
    """
    import base64
    
    try:
        # 直接编码为 base32
        secret_base32 = base64.b32encode(secret_bytes).decode('ascii')
        # 移除填充
        secret_base32 = secret_base32.rstrip('=')
        return secret_base32
    except:
        return None

def parse_otp_parameters(data):
    """
    解析单个 OtpParameters 消息
    
    Args:
        data: OtpParameters 消息的二进制数据
        
    Returns:
        dict: 包含 secret, name, issuer 等的字典
    """
    account = {
        'secret': '',
        'name': '',
        'issuer': '',
        'algorithm': 'SHA1',
        'digits': 6,
        'type': 'TOTP'
    }
    
    i = 0
    while i < len(data):
        if i + 1 > len(data):
            break
            
        tag = data[i]
        field_number = tag >> 3
        wire_type = tag & 0x07
        i += 1
        
        if wire_type == 2:  # Length-delimited
            length, length_bytes = read_varint(data, i)
            i += length_bytes
            
            if i + length > len(data):
                break
            
            field_data = data[i:i+length]
            i += length
            
            if field_number == 1:  # secret
                secret_base32 = bytes_to_base32(field_data)
                if secret_base32:
                    account['secret'] = secret_base32
            elif field_number == 2:  # name
                try:
                    account['name'] = field_data.decode('utf-8', errors='ignore')
                except:
                    pass
            elif field_number == 3:  # issuer
                try:
                    account['issuer'] = field_data.decode('utf-8', errors='ignore')
                except:
                    pass
            elif field_number == 4:  # algorithm
                if len(field_data) > 0:
                    algo_val = field_data[0] if isinstance(field_data, bytes) else field_data
                    algorithms = ['SHA1', 'SHA256', 'SHA512', 'MD5']
                    if 0 <= algo_val < len(algorithms):
                        account['algorithm'] = algorithms[algo_val]
            elif field_number == 5:  # digits
                if len(field_data) > 0:
                    digits_val = field_data[0] if isinstance(field_data, bytes) else field_data
                    if digits_val == 1:
                        account['digits'] = 6
                    elif digits_val == 2:
                        account['digits'] = 8
            elif field_number == 6:  # type
                if len(field_data) > 0:
                    type_val = field_data[0] if isinstance(field_data, bytes) else field_data
                    if type_val == 1:
                        account['type'] = 'HOTP'
                    elif type_val == 2:
                        account['type'] = 'TOTP'
        elif wire_type == 0:  # Varint
            value, bytes_read = read_varint(data, i)
            i += bytes_read
            
            if field_number == 4:  # algorithm
                algorithms = ['SHA1', 'SHA256', 'SHA512', 'MD5']
                if 0 <= value < len(algorithms):
                    account['algorithm'] = algorithms[value]
            elif field_number == 5:  # digits
                if value == 1:
                    account['digits'] = 6
                elif value == 2:
                    account['digits'] = 8
            elif field_number == 6:  # type
                if value == 1:
                    account['type'] = 'HOTP'
                elif value == 2:
                    account['type'] = 'TOTP'
        else:
            # 跳过未知的 wire type
            break
    
    return account if account['secret'] else None

