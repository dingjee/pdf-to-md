#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TXT to JSON Parser for AdeedDawisha_ArabNationalismInTheTwentiethCentury.txt

解析规则：
1. "CHAPTER ONE" 为章节分章标志
2. 其后一行"DEFINING ARAB NATIONALISM"为该章节标题
3. 其后的"T"为首行首字下沉的首字母，需要合并到下一段中
4. 其后的一长段为正文段落
5. 再其后"1 Al-Jumhuriya al-'Arabiya al-Muttahida..."这种格式的为脚注
6. 处理段落被分页打断的情况：如果前一条为footnote，当前为paragraph且首字母小写，则合并到前一个paragraph
"""

import re
import json
from typing import List, Dict, Any

def read_file_with_encoding(file_path: str) -> str:
    """
    尝试多种编码方式读取文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件内容
    """
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'windows-1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                print(f"成功使用 {encoding} 编码读取文件")
                return content
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"使用 {encoding} 编码时出现其他错误: {e}")
            continue
    
    # 如果所有编码都失败，尝试二进制读取
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            # 尝试解码，忽略错误
            return content.decode('utf-8', errors='ignore')
    except Exception as e:
        raise Exception(f"无法读取文件: {e}")

def parse_txt_to_json(file_path: str) -> List[Dict[str, Any]]:
    """
    解析txt文件并转换为JSON格式
    
    Args:
        file_path: txt文件路径
        
    Returns:
        包含章节和内容单元的JSON列表
    """
    
    content = read_file_with_encoding(file_path)
    
    # 按章节分割内容
    chapters = []
    
    # 使用正则表达式匹配章节
    chapter_pattern = r'CHAPTER\s+(\w+)\s*\n([^\n]+)\s*\n'
    chapter_matches = list(re.finditer(chapter_pattern, content, re.MULTILINE))
    
    for i, match in enumerate(chapter_matches):
        chapter_num = match.group(1)
        chapter_title = match.group(2).strip()
        
        # 获取章节内容的开始和结束位置
        start_pos = match.end()
        if i + 1 < len(chapter_matches):
            end_pos = chapter_matches[i + 1].start()
        else:
            end_pos = len(content)
        
        chapter_content = content[start_pos:end_pos].strip()
        
        # 解析章节内容
        content_units = parse_chapter_content(chapter_content, chapter_num)
        
        chapter_data = {
            "chapter": int(chapter_num) if chapter_num.isdigit() else chapter_num,
            "title": chapter_title,
            "content_units": content_units
        }
        
        chapters.append(chapter_data)
    
    return chapters

def parse_chapter_content(content: str, chapter_num: str) -> List[Dict[str, Any]]:
    """
    解析章节内容，提取标题、段落和脚注
    
    Args:
        content: 章节内容
        chapter_num: 章节号
        
    Returns:
        内容单元列表
    """
    content_units = []
    unit_id = 1
    
    # 分割内容为行
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # 检查是否是首字下沉的首字母（所有章节的第一段）
        if i == 0 and len(line) == 1 and line.isupper():
            # 这是首字下沉的首字母，需要与下一行合并
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line:
                    # 合并首字母和下一行
                    combined_text = line + next_line
                    content_units.append({
                        "id": unit_id,
                        "type": "paragraph",
                        "text": combined_text
                    })
                    unit_id += 1
                    i += 2  # 跳过下一行
                    continue
        
        # 检查是否是脚注（数字开头 + 空格 + 内容）
        if re.match(r'^\d+\s+', line):
            # 这是脚注
            footnote_match = re.match(r'^(\d+)\s+(.+)$', line)
            if footnote_match:
                footnote_num = footnote_match.group(1)
                footnote_text = footnote_match.group(2).strip()
                
                content_units.append({
                    "id": unit_id,
                    "type": "footnote",
                    "original_id": footnote_num,
                    "text": footnote_text
                })
                unit_id += 1
        else:
            # 这是普通段落
            content_units.append({
                "id": unit_id,
                "type": "paragraph",
                "text": line
            })
            unit_id += 1
        
        i += 1
    
    # 处理段落被分页打断的情况
    content_units = merge_split_paragraphs(content_units)
    
    return content_units

def merge_split_paragraphs(content_units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    合并被分页打断的段落
    
    Args:
        content_units: 内容单元列表
        
    Returns:
        处理后的内容单元列表
    """
    if len(content_units) < 2:
        return content_units
    
    merged_units = []
    i = 0
    
    while i < len(content_units):
        current_unit = content_units[i]
        
        # 检查是否需要合并
        if (i > 0 and 
            content_units[i-1]['type'] == 'footnote' and 
            current_unit['type'] == 'paragraph' and
            current_unit['text'] and 
            current_unit['text'][0].islower()):
            
            # 这是被分页打断的段落，需要合并到前一个paragraph
            # 找到前一个paragraph
            prev_paragraph_idx = None
            for j in range(len(merged_units) - 1, -1, -1):
                if merged_units[j]['type'] == 'paragraph':
                    prev_paragraph_idx = j
                    break
            
            if prev_paragraph_idx is not None:
                # 合并文本
                merged_units[prev_paragraph_idx]['text'] += ' ' + current_unit['text']
                # 添加合并说明
                if 'note' not in merged_units[prev_paragraph_idx]:
                    merged_units[prev_paragraph_idx]['note'] = []
                merged_units[prev_paragraph_idx]['note'].append(f"combined by id{current_unit['id']}")
                print(f"合并段落: id{current_unit['id']} 合并到前一个paragraph")
            else:
                # 如果找不到前一个paragraph，保留当前单元
                merged_units.append(current_unit)
        else:
            # 正常添加单元
            merged_units.append(current_unit)
        
        i += 1
    
    return merged_units

def parse_all_chapters():
    """
    解析全部章节
    """
    file_path = "AdeedDawisha_ArabNationalismInTheTwentiethCentury.txt"
    
    try:
        chapters = parse_txt_to_json(file_path)
        
        if chapters:
            print(f"=== 解析完成 ===")
            print(f"总章节数: {len(chapters)}")
            
            for i, chapter in enumerate(chapters):
                print(f"第{i+1}章: {chapter['chapter']} - {chapter['title']}")
                print(f"  内容单元数量: {len(chapter['content_units'])}")
                
                # 统计各类型单元数量
                paragraph_count = sum(1 for unit in chapter['content_units'] if unit['type'] == 'paragraph')
                footnote_count = sum(1 for unit in chapter['content_units'] if unit['type'] == 'footnote')
                print(f"  段落数: {paragraph_count}, 脚注数: {footnote_count}")
                print()
            
            # 保存全部章节的JSON结果
            with open('all_chapters_output.json', 'w', encoding='utf-8') as f:
                json.dump(chapters, f, ensure_ascii=False, indent=2)
            
            print("全部章节解析完成，结果已保存到 all_chapters_output.json")
            
            # 同时保存第一章的单独结果用于测试
            with open('chapter_one_output.json', 'w', encoding='utf-8') as f:
                json.dump([chapters[0]], f, ensure_ascii=False, indent=2)
            
            print("第一章单独结果已保存到 chapter_one_output.json")
            
        else:
            print("未找到任何章节")
            
    except Exception as e:
        print(f"解析过程中出现错误: {e}")

def test_chapter_one_parsing():
    """
    仅测试第一章的解析
    """
    file_path = "AdeedDawisha_ArabNationalismInTheTwentiethCentury.txt"
    
    try:
        chapters = parse_txt_to_json(file_path)
        
        # 只处理第一章
        if chapters:
            chapter_one = chapters[0]
            print("=== 第一章解析结果 ===")
            print(f"章节号: {chapter_one['chapter']}")
            print(f"章节标题: {chapter_one['title']}")
            print(f"内容单元数量: {len(chapter_one['content_units'])}")
            print("\n=== 内容单元详情 ===")
            
            for unit in chapter_one['content_units']:
                print(f"ID: {unit['id']}, 类型: {unit['type']}")
                if unit['type'] == 'footnote':
                    print(f"  原始ID: {unit['original_id']}")
                if 'note' in unit:
                    print(f"  合并说明: {unit['note']}")
                print(f"  文本: {unit['text'][:100]}{'...' if len(unit['text']) > 100 else ''}")
                print()
            
            # 保存第一章的JSON结果
            with open('chapter_one_output.json', 'w', encoding='utf-8') as f:
                json.dump([chapter_one], f, ensure_ascii=False, indent=2)
            
            print("第一章解析完成，结果已保存到 chapter_one_output.json")
            
        else:
            print("未找到任何章节")
            
    except Exception as e:
        print(f"解析过程中出现错误: {e}")

if __name__ == "__main__":
    parse_all_chapters() 