# PDF to Markdown Converter (CLI)

This is a Python command-line tool that converts PDF files to Markdown (.md) format. It utilizes the `pdfplumber` library to extract text from PDFs and provides progress updates using `tqdm`.

## Features

* Converts PDF files to Markdown.
* Command-line interface (CLI).
* Displays progress using `tqdm`.
* Handles single PDF file input.
* Specifies input and output paths using command-line arguments.

## Prerequisites

* Python 3.6+
* `pdfplumber` library
* `tqdm` library

## Installation

1.  Clone the repository:

    ```bash
    git clone [https://github.com/your-username/pdf-to-markdown.git](https://www.google.com/search?q=https://github.com/your-username/pdf-to-markdown.git)
    cd pdf-to-markdown
    ```

2.  Create a virtual environment (recommended):

    ```bash
    python3 -m venv venv
    source venv/bin/activate # On macOS and Linux
    venv\Scripts\activate # On Windows
    ```

3.  Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

```bash
python pdf_to_md.py -I <input_path> -O <output_path>
