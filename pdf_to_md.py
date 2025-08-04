import pdfplumber  # For extracting text from PDF
import os  # For file and path operations
import time  # For simple animation
# import argparse  # For command-line argument parsing
# from tqdm import tqdm  # For progress bar
import pandas as pd  # For handling table conversion
import configparser
from PIL import Image

def extract_table_markdown(table):
    """
    Convert extracted table data into Markdown table format.
    """
    if not table:
        return ""
    
    # Ensure all elements in the table are strings, replace None with ""
    table = [[cell if cell is not None else "" for cell in row] for row in table]

    markdown_table = "| " + " | ".join(table[0]) + " |\n"
    markdown_table += "| " + " | ".join(["---"] * len(table[0])) + " |\n"
    
    for row in table[1:]:
        markdown_table += "| " + " | ".join(row) + " |\n"
    
    return markdown_table + "\n"

def pdf_to_md(pdf_path: str, output_path: str, page_slice: slice=slice(None)):
    """
    Extracts text and tables from a PDF file and saves it as a Markdown (.md) file.

    Args:
        pdf_path (str): Path to the PDF file to be converted.
        output_path (str): Path where the Markdown file will be saved.
    """
    import re
    # 1. 读取同名 cfg 文件
    cfg_path = os.path.splitext(pdf_path)[0] + '.cfg'
    config = {}
    if os.path.exists(cfg_path):
        parser = configparser.ConfigParser()
        parser.read(cfg_path)
        # 支持无 section 的简单 key=value
        with open(cfg_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    k, v = line.split('=', 1)
                    config[k.strip()] = v.strip()
    # 2. 解析参数
    x_tolerance_ratio = float(config.get('x_tolerance_ratio', 0.03))
    first_line_indent = config.get('first_line_indent', 'False').lower() == 'true'
    header_threshold = float(config.get('header_threshold', 0.10))
    footer_threshold = float(config.get('footer_threshold', 0.10))
    paragraph_y_gap = float(config.get('paragraph_y_gap', 20))
    # Check if the PDF file exists
    if not os.path.exists(pdf_path):
        print("Error: PDF file not found!")
        return
    
    # If output_path is a directory, generate a default filename
    if os.path.isdir(output_path):
        pdf_name = os.path.basename(pdf_path).replace(".pdf", ".md")
        output_path = os.path.join(output_path, pdf_name)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("\n[INFO] Starting conversion...")

    # Loading animation simulation
    loading_animation = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for _ in range(10):
        print(f"\r{loading_animation[_ % len(loading_animation)]} Processing PDF file...", end="", flush=True)
        time.sleep(0.1)

    # 图片输出文件夹
    pdf_base = os.path.splitext(os.path.basename(pdf_path))[0]
    image_dir = os.path.join(os.path.dirname(output_path), pdf_base)
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    # Open PDF and create a Markdown file
    with pdfplumber.open(pdf_path) as pdf, open(output_path, "w", encoding="utf-8") as md_file:
        total_pages = len(pdf.pages)

        # Show progress bar with tqdm
        # for i, page in enumerate(tqdm(pdf.pages, desc="Converting pages", unit="page")):

        pages = pdf.pages[page_slice]

        for i, page in enumerate(tqdm(pdf.pages, desc="Converting pages", unit="page")):
            page_num = i + 1
            # 动态计算 x_tolerance
            page_width = page.width
            x_tolerance = page_width * x_tolerance_ratio
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=2, extra_attrs=["size", "fontname"], use_text_flow=True)
            page_height = page.height

            # 过滤掉页眉和页脚的词
            words = [
                w for w in words
                if (w['top'] > header_threshold * page_height) and (w['bottom'] < (page_height * (1- footer_threshold)))
            ]

            # 获取页面边界
            page_x0, page_y0, page_x1, page_y1 = 0, 0, page.width, page.height

            for img_idx, img in enumerate(page.images):
                # 计算图片 bbox，并裁剪到页面范围
                x0 = max(img['x0'], page_x0)
                y0 = max(img['top'], page_y0)
                x1 = min(img['x1'], page_x1)
                y1 = min(img['bottom'], page_y1)
                # 防止浮点误差导致超界
                bbox = (x0, y0, x1, y1)
                if x1 > x0 and y1 > y0:
                    cropped = page.within_bbox(bbox)
                    if cropped:
                        pil_img = cropped.to_image(resolution=300).original
                        img_name = f"page_{page_num}"
                        if len(page.images) > 1:
                            img_name += f"_{img_idx+1}"
                        img_name += ".png"
                        img_path = os.path.join(image_dir, img_name)
                        pil_img.save(img_path, format="PNG")
                        md_file.write(f"![image]({os.path.relpath(img_path, os.path.dirname(output_path))})\n\n")
            def group_words_to_lines(words, y_tolerance=2):
                lines = []
                words = sorted(words, key=lambda w: w['top'])
                current_line = []
                last_top = None
                for word in words:
                    if last_top is None or abs(word['top'] - last_top) < y_tolerance:
                        current_line.append(word)
                    else:
                        lines.append(current_line)
                        current_line = [word]
                    last_top = word['top']
                if current_line:
                    lines.append(current_line)
                return lines
            # 分段逻辑：首行缩进或行间距
            lines = group_words_to_lines(words, y_tolerance=2)
            paragraphs = []
            current_para = []
            last_x0 = None
            last_line_top = None
            indent_threshold = page_width * 0.02  # 2% 页面宽度

            for line in lines:
                first_word = line[0]
                line_top = first_word['top']
                is_new_para = False
                if last_x0 is not None and first_word['x0'] - last_x0 > indent_threshold:
                    is_new_para = True
                if last_line_top is not None and abs(line_top - last_line_top) > paragraph_y_gap:
                    is_new_para = True
                if is_new_para:
                    if current_para:
                        paragraphs.append(current_para)
                    current_para = [line]
                else:
                    current_para.append(line)
                last_x0 = first_word['x0']
                last_line_top = line_top
            if current_para:
                paragraphs.append(current_para)
            for para in paragraphs:
                para_text = " ".join(" ".join(word['text'] for word in line) for line in para)
                md_file.write(para_text + "\n\n")
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    md_file.write("## Table\n\n")
                    md_file.write(extract_table_markdown(table))
                    md_file.write("\n\n")
            # md_file.write("---\n\n")  # Page separator

    print("\n✅ Conversion complete! Markdown file saved at:", output_path)

if __name__ == "__main__":

    input_path = "../data/input_pdf/TaoistSecretsOfLove.pdf"
    output_path = "../data/output_md/TaoistSecretsOfLove.md"

    pdf_to_md(input_path, output_path)
