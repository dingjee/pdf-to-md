import pdfplumber

pdf_path = "input_pdf\AdeedDawisha_ArabNationalismInTheTwentiethCentury.pdf"  # 替换为你的PDF路径
start_page = 9  # 页码从1开始
end_page = 10
max_words = 100

words_info = []
word = ""
word_chars = []
word_count = 0

def get_font_info(chars):
    if chars:
        # 取第一个字符的字体和字号
        print(f"char: {chars[0]}, font: {chars[0]['fontname']}, size: {chars[0]['size']}")
        return chars[0]["fontname"], chars[0]["size"]
    return None, None

with pdfplumber.open(pdf_path) as pdf:
    for page_num in range(start_page-1, end_page):
        page = pdf.pages[page_num]
        chars = page.chars
        for char in chars:
            text = char["text"]
            if text.isspace():
                if word:
                    font, size = get_font_info(word_chars)
                    # print(f"char: {text}, font: {font}, size: {size}")
                    words_info.append({
                        "page": page_num + 1,
                        "word": word,
                        "font": font,
                        "size": size
                    })
                    word_count += 1
                    if word_count >= max_words:
                        break
                    word = ""
                    word_chars = []
            else:
                word += text
                word_chars.append(char)
        # 行尾单词处理
        if word and word_count < max_words:
            font, size = get_font_info(word_chars)
            words_info.append({
                "page": page_num + 1,
                "word": word,
                "font": font,
                "size": size
            })
            word_count += 1
            word = ""
            word_chars = []
        if word_count >= max_words:
            break

# 输出结果
# for i, info in enumerate(words_info, 1):
#     print(f"{i}. 页码: {info['page']}, 单词: {info['word']}, 字体: {info['font']}, 字号: {info['size']}\n")