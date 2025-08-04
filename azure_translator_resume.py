#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Translator with Resume Functionality

支持断点续传的翻译脚本，可以从上次停止的地方继续翻译
"""

import requests
import uuid
import json
import os
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class AzureTranslator:
    def __init__(self):
        """初始化Azure Translator"""
        self.key = os.getenv('AZURE_TRANSLATOR_KEY')
        self.endpoint = os.getenv('AZURE_TRANSLATOR_ENDPOINT', 'https://api.cognitive.microsofttranslator.com')
        self.location = os.getenv('AZURE_TRANSLATOR_LOCATION')
        
        if not self.key:
            raise ValueError("请设置AZURE_TRANSLATOR_KEY环境变量")
        
        self.path = '/translate'
        self.constructed_url = self.endpoint + self.path
        
        self.headers = {
            'Ocp-Apim-Subscription-Key': self.key,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        
        # 如果设置了location，添加到headers中
        if self.location:
            self.headers['Ocp-Apim-Subscription-Region'] = self.location
    
    def translate_batch(self, texts: List[str], from_lang: str = 'en', to_lang: str = 'zh-Hans', max_retries: int = 3) -> List[str]:
        """
        批量翻译文本，支持重试机制
        
        Args:
            texts: 要翻译的文本列表
            from_lang: 源语言
            to_lang: 目标语言
            max_retries: 最大重试次数
            
        Returns:
            翻译后的文本列表
        """
        if not texts:
            return []
        
        # 过滤空文本
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            return [""] * len(texts)
        
        params = {
            'api-version': '3.0',
            'from': from_lang,
            'to': [to_lang]
        }
        
        body = [{'text': text} for text in valid_texts]
        
        for attempt in range(max_retries):
            try:
                request = requests.post(self.constructed_url, params=params, headers=self.headers, json=body)
                
                # 处理429错误（API限制）
                if request.status_code == 429:
                    wait_time = 60 * (attempt + 1)  # 递增等待时间
                    print(f"遇到API限制，等待{wait_time}秒后重试... (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                
                request.raise_for_status()
                response = request.json()
                
                translations = []
                for item in response:
                    if 'translations' in item and len(item['translations']) > 0:
                        translations.append(item['translations'][0]['text'])
                    else:
                        translations.append("")
                
                # 确保返回的翻译数量与输入文本数量一致
                result = []
                valid_idx = 0
                for i, text in enumerate(texts):
                    if text and text.strip():
                        result.append(translations[valid_idx])
                        valid_idx += 1
                    else:
                        result.append("")
                
                return result
                
            except requests.exceptions.RequestException as e:
                print(f"翻译请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    print(f"等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print("达到最大重试次数，返回空结果")
                    return [""] * len(texts)
            except Exception as e:
                print(f"翻译过程中出现错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    print(f"等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print("达到最大重试次数，返回空结果")
                    return [""] * len(texts)
        
        return [""] * len(texts)

def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON文件失败: {e}")
        return []

def save_json_file(data: List[Dict[str, Any]], file_path: str):
    """保存JSON文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"文件已保存到: {file_path}")
    except Exception as e:
        print(f"保存JSON文件失败: {e}")

def save_progress(progress_file: str, completed_indices: List[int], total_count: int):
    """保存翻译进度"""
    progress_data = {
        'completed_indices': completed_indices,
        'total_count': total_count,
        'timestamp': time.time()
    }
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存进度失败: {e}")

def load_progress(progress_file: str) -> List[int]:
    """加载翻译进度"""
    try:
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                return progress_data.get('completed_indices', [])
    except Exception as e:
        print(f"加载进度失败: {e}")
    return []

def extract_texts_for_translation(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从JSON数据中提取需要翻译的文本"""
    texts_to_translate = []
    
    for chapter_idx, chapter in enumerate(data):
        if 'content_units' in chapter:
            for unit_idx, unit in enumerate(chapter['content_units']):
                # 只翻译title和paragraph类型
                if unit.get('type') in ['title', 'paragraph']:
                    text = unit.get('text', '')
                    if text and text.strip():
                        texts_to_translate.append({
                            'chapter_idx': chapter_idx,
                            'unit_idx': unit_idx,
                            'text': text,
                            'type': unit.get('type'),
                            'global_index': len(texts_to_translate)  # 全局索引
                        })
    
    return texts_to_translate

def translate_json_content_with_resume(input_file: str, output_file: str = None, progress_file: str = "translation_progress.json"):
    """
    支持断点续传的翻译功能
    
    Args:
        input_file: 输入JSON文件路径
        output_file: 输出JSON文件路径
        progress_file: 进度文件路径
    """
    # 加载JSON数据
    print(f"加载JSON文件: {input_file}")
    data = load_json_file(input_file)
    if not data:
        print("无法加载JSON数据")
        return
    
    # 提取需要翻译的文本
    print("提取需要翻译的文本...")
    texts_to_translate = extract_texts_for_translation(data)
    print(f"找到 {len(texts_to_translate)} 个需要翻译的文本")
    
    if not texts_to_translate:
        print("没有找到需要翻译的文本")
        return
    
    # 加载之前的进度
    completed_indices = load_progress(progress_file)
    if completed_indices:
        print(f"发现之前的翻译进度，已完成 {len(completed_indices)} 个文本")
        # 过滤掉已完成的文本
        texts_to_translate = [item for item in texts_to_translate if item['global_index'] not in completed_indices]
        print(f"剩余 {len(texts_to_translate)} 个文本需要翻译")
    
    if not texts_to_translate:
        print("所有文本都已翻译完成！")
        return
    
    # 初始化翻译器
    try:
        translator = AzureTranslator()
        print("Azure Translator 初始化成功")
    except Exception as e:
        print(f"Azure Translator 初始化失败: {e}")
        return
    
    # 批量翻译
    print("开始翻译...")
    batch_size = 5  # 更小的批次大小
    output_path = output_file or input_file
    
    try:
        for i in range(0, len(texts_to_translate), batch_size):
            batch = texts_to_translate[i:i + batch_size]
            texts = [item['text'] for item in batch]
            
            print(f"翻译批次 {i//batch_size + 1}/{(len(texts_to_translate) + batch_size - 1)//batch_size}")
            translations = translator.translate_batch(texts)
            
            # 将翻译结果写回数据并立即保存
            for j, item in enumerate(batch):
                chapter_idx = item['chapter_idx']
                unit_idx = item['unit_idx']
                translation = translations[j] if j < len(translations) else ""
                
                # 添加azure_translation字段
                if 'azure_translation' not in data[chapter_idx]['content_units'][unit_idx]:
                    data[chapter_idx]['content_units'][unit_idx]['azure_translation'] = ""
                
                data[chapter_idx]['content_units'][unit_idx]['azure_translation'] = translation
                
                # 显示翻译进度
                print(f"  已翻译: {item['type']} - {item['text'][:50]}... -> {translation[:50]}...")
            
            # 更新进度
            batch_indices = [item['global_index'] for item in batch]
            completed_indices.extend(batch_indices)
            save_progress(progress_file, completed_indices, len(texts_to_translate) + len(completed_indices))
            
            # 每批次完成后立即保存
            save_json_file(data, output_path)
            print(f"批次 {i//batch_size + 1} 完成，已保存到文件")
            
            # 增加延迟避免API限制
            if i + batch_size < len(texts_to_translate):
                print("等待5秒...")
                time.sleep(5)
        
        print("翻译完成！")
        # 删除进度文件
        if os.path.exists(progress_file):
            os.remove(progress_file)
            print("进度文件已删除")
            
    except KeyboardInterrupt:
        print("\n翻译被用户中断")
        print("进度已保存，下次运行时会从断点继续")
    except Exception as e:
        print(f"翻译过程中出现错误: {e}")
        print("进度已保存，下次运行时会从断点继续")

def main():
    """主函数"""
    input_file = "all_chapters_output.json"
    
    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        print("请先运行 txt_to_json_parser.py 生成JSON文件")
        return
    
    output_file = "all_chapters_output_translated.json"
    translate_json_content_with_resume(input_file, output_file)

if __name__ == "__main__":
    main() 