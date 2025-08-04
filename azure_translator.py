#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Translator for JSON content

从JSON文件中提取title和paragraph的text，使用Azure Translator API翻译为中文
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
    
    def translate_text(self, text: str, from_lang: str = 'en', to_lang: str = 'zh-Hans') -> str:
        """
        翻译单个文本
        
        Args:
            text: 要翻译的文本
            from_lang: 源语言
            to_lang: 目标语言
            
        Returns:
            翻译后的文本
        """
        if not text or not text.strip():
            return ""
        
        params = {
            'api-version': '3.0',
            'from': from_lang,
            'to': [to_lang]
        }
        
        body = [{'text': text}]
        
        try:
            request = requests.post(self.constructed_url, params=params, headers=self.headers, json=body)
            request.raise_for_status()
            response = request.json()
            
            if response and len(response) > 0 and 'translations' in response[0]:
                return response[0]['translations'][0]['text']
            else:
                print(f"翻译响应格式异常: {response}")
                return ""
                
        except requests.exceptions.RequestException as e:
            print(f"翻译请求失败: {e}")
            return ""
        except Exception as e:
            print(f"翻译过程中出现错误: {e}")
            return ""
    
    def translate_batch(self, texts: List[str], from_lang: str = 'en', to_lang: str = 'zh-Hans') -> List[str]:
        """
        批量翻译文本
        
        Args:
            texts: 要翻译的文本列表
            from_lang: 源语言
            to_lang: 目标语言
            
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
        
        try:
            request = requests.post(self.constructed_url, params=params, headers=self.headers, json=body)
            
            # 处理429错误（API限制）
            if request.status_code == 429:
                print("遇到API限制，等待60秒后重试...")
                time.sleep(60)
                # 重试一次
                request = requests.post(self.constructed_url, params=params, headers=self.headers, json=body)
            
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
            print(f"批量翻译请求失败: {e}")
            return [""] * len(texts)
        except Exception as e:
            print(f"批量翻译过程中出现错误: {e}")
            return [""] * len(texts)

def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """
    加载JSON文件
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        JSON数据
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON文件失败: {e}")
        return []

def save_json_file(data: List[Dict[str, Any]], file_path: str):
    """
    保存JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 保存路径
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"文件已保存到: {file_path}")
    except Exception as e:
        print(f"保存JSON文件失败: {e}")

def extract_texts_for_translation(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从JSON数据中提取需要翻译的文本
    
    Args:
        data: JSON数据
        
    Returns:
        包含需要翻译文本的列表，每个元素包含索引信息和文本
    """
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
                            'type': unit.get('type')
                        })
    
    return texts_to_translate

def translate_json_content(input_file: str, output_file: str = None):
    """
    翻译JSON文件中的内容
    
    Args:
        input_file: 输入JSON文件路径
        output_file: 输出JSON文件路径，如果为None则覆盖原文件
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
    
    # 初始化翻译器
    try:
        translator = AzureTranslator()
        print("Azure Translator 初始化成功")
    except Exception as e:
        print(f"Azure Translator 初始化失败: {e}")
        return
    
    # 批量翻译
    print("开始翻译...")
    batch_size = 20  # 减少批次大小以避免API限制
    output_path = output_file or input_file
    
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
        
        # 每批次完成后立即保存
        save_json_file(data, output_path)
        print(f"批次 {i//batch_size + 1} 完成，已保存到文件")
        
        # 增加延迟避免API限制
        if i + batch_size < len(texts_to_translate):
            print("等待3秒...")
            time.sleep(3)
    
    print("翻译完成！")

def main():
    """主函数"""
    input_file = "output_json/all_chapters_output.json"
    
    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        print("请先运行 txt_to_json_parser.py 生成JSON文件")
        return
    
    output_file = "all_chapters_output_translated.json"
    translate_json_content(input_file, output_file)

if __name__ == "__main__":
    main() 