# pdpvp-textract.streamlit.app
import os
import io
import json
import requests
from pathlib import Path

import fitz  # PyMuPDF
import traceback
import streamlit as st
from PIL import Image, ImageDraw

prefix = 'pdpvp_textract_test_cases/'
repo = 'ipos-fst/public_artefacts'

BLOCK_COLORS = {
    'LAYOUT_FIGURE': (255, 0, 0, 64),      # Red
    'LAYOUT_TABLE': (0, 0, 255, 64),       # Blue
    'LAYOUT_TEXT': (0, 255, 0, 64),        # Green
    'LAYOUT_HEADER/TITLE': (128, 0, 128, 64),    # Purple
    'LAYOUT_FOOTER': (255, 255, 0, 64)     # Yellow
}

def get_github_file_content(path):
    try:
        url = f'https://raw.githubusercontent.com/{repo}/outputs/{path}'
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        return response.content
    except requests.RequestException as e:
        st.error(f"Error fetching file from GitHub: {e}")
        return None

def rgba_to_hex(rgba):
    return f'#{rgba[0]:02x}{rgba[1]:02x}{rgba[2]:02x}'

def display_legends_with_columns():
    st.markdown("### Block Type Legend")
    
    st.markdown("""
        <style>
        .legend-box {
            padding: 5px;
            border-radius: 3px;
            margin: 2px 0;
            text-align: center;
            font-size: 14px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Create columns for legend items
    cols = st.columns(len(BLOCK_COLORS))
    
    for col, (block_type, color) in zip(cols, BLOCK_COLORS.items()):
        with col:
            hex_color = rgba_to_hex(color)
            st.markdown(
                f'''
                <div class="legend-box" style="background-color: {hex_color};">
                    {block_type}
                </div>
                ''',
                unsafe_allow_html=True
            )

def load_processed_results():
    """Load previously processed results"""
    try:
        with open('processing_map.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("No previously processed results found. Please process files first.")
        return

def main():
    st.header("Document Processing Viewer")
    # Load previously processed results
    results = load_processed_results()
    
    if results:
        folders = list(results.keys())
        selected_folder = st.selectbox("Select Folder", folders)
        
        if selected_folder:
            files = list(results[selected_folder].keys())
            selected_file = st.selectbox("Select File", files)
            
            if selected_file:
                # Display processed content
                pdf_file = f"{selected_file}.pdf"
                pdf_path = Path(selected_folder) / pdf_file
                output_path = results[selected_folder][selected_file]
                try:
                    output_path = output_path.replace('\\', '/')
                    st.write(f"Processing file: {output_path}")
                    raw_content = get_github_file_content(output_path)
                    
                    # # Debug information
                    # st.write("Raw content type:", type(raw_content))
                    # st.write("Raw content length:", len(raw_content))
                    # st.write("First 500 characters of raw content:", raw_content[:500])
                    
                    if not raw_content:
                        st.error("File is empty")
                        return
                        
                    try:
                        content = json.loads(raw_content)
                    except json.JSONDecodeError as e:
                        st.error(f"Invalid JSON format: {str(e)}")
                        st.write("Content that failed to parse:", raw_content)
                        with st.expander("Show Error Traceback"):
                            st.code(traceback.format_exc())
                        return

                    pdf_document = fitz.open(pdf_path)

                    # Extract all blocks from all responses
                    all_blocks = []
                    document_key = f"{prefix}/{pdf_path}"
                    document_key = os.path.normpath(document_key).replace('\\', '/')
                    textract_parts = content[document_key]
                    for part in textract_parts:
                        all_blocks.extend(part["Blocks"])

                    # Now you can process blocks by type
                    line_blocks = []
                    word_blocks = []
                    figure_blocks = []
                    table_blocks = []
                    for block in all_blocks:
                        if block['BlockType'] == 'LINE':
                            line_blocks.append(block)
                        elif block['BlockType'] == 'WORD':
                            word_blocks.append(block)
                        elif block['BlockType'] == 'LAYOUT_FIGURE':
                            figure_blocks.append(block)
                        elif block['BlockType'] == 'LAYOUT_TABLE':
                            table_blocks.append(block)
                    stats = {
                        "Page Count": len(pdf_document),
                        "Line Count": len(line_blocks),
                        "Word Count": len(word_blocks),
                        "Figure Count": len(figure_blocks),
                        "Table Count": len(table_blocks)
                    }
                    st.write("Statistics:", stats)

                    display_legends_with_columns()
                    st.header(f"Processed File: {selected_file}")
                    
                    for page_num in range(1, len(pdf_document)+1):
                        page_line_blocks = []
                        page_word_blocks = []
                        page_figure_blocks = []
                        page_table_blocks = []
                        page_text_blocks = []
                        page_header_blocks = []
                        page_footer_blocks = []

                        for block in all_blocks:
                            if block['Page'] != page_num:
                                continue

                            if block['BlockType'] == 'LINE':
                                page_line_blocks.append(block)
                            if block['BlockType'] == 'WORD':
                                page_word_blocks.append(block)
                            if block['BlockType'] == 'LAYOUT_FIGURE':
                                page_figure_blocks.append(block)
                            if block['BlockType'] == 'LAYOUT_TABLE':
                                page_table_blocks.append(block)
                            if block['BlockType'] == 'LAYOUT_TEXT':
                                page_text_blocks.append(block)
                            if block['BlockType'] in ['LAYOUT_SECTION_HEADER', 'LAYOUT_HEADER', 'LAYOUT_TITLE']:
                                page_header_blocks.append(block)
                            if block['BlockType'] == 'LAYOUT_FOOTER':
                                page_footer_blocks.append(block)

                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader(f"Original PDF Page {page_num}")
                            page = pdf_document.load_page(page_num - 1)
                            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                            img_bytes = pix.tobytes()
                            img = Image.open(io.BytesIO(img_bytes))
                            img_width, img_height = img.size

                            for block in page_figure_blocks:
                                bounding_box = block['Geometry']['BoundingBox']
                                left = int(img_width * bounding_box['Left'])
                                top = int(img_height * bounding_box['Top'])
                                width = int(img_width * bounding_box['Width'])
                                height = int(img_height * bounding_box['Height'])

                                # Draw a rectangle on the image with transperancy 80% and a shade of blue
                                # Create a transparent overlay for highlighting text
                                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                draw = ImageDraw.Draw(overlay)
                                
                                # Draw a semi-transparent blue rectangle
                                draw.rectangle(
                                    [(left, top), (left + width, top + height)],
                                    fill=(255, 0, 0, 64)  # RGBA: Red with 25% opacity
                                )
                                
                                # Combine the original image with the overlay
                                img = Image.alpha_composite(img.convert('RGBA'), overlay)
                            
                            for block in page_table_blocks:
                                bounding_box = block['Geometry']['BoundingBox']
                                left = int(img_width * bounding_box['Left'])
                                top = int(img_height * bounding_box['Top'])
                                width = int(img_width * bounding_box['Width'])
                                height = int(img_height * bounding_box['Height'])

                                # Draw a rectangle on the image with transperancy 80% and a shade of blue
                                # Create a transparent overlay for highlighting text
                                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                draw = ImageDraw.Draw(overlay)
                                
                                # Draw a semi-transparent blue rectangle
                                draw.rectangle(
                                    [(left, top), (left + width, top + height)],
                                    fill=(0, 0, 255, 64)  # RGBA: Blue with 25% opacity
                                )
                                
                                # Combine the original image with the overlay
                                img = Image.alpha_composite(img.convert('RGBA'), overlay)

                            for block in page_text_blocks:
                                bounding_box = block['Geometry']['BoundingBox']
                                left = int(img_width * bounding_box['Left'])
                                top = int(img_height * bounding_box['Top'])
                                width = int(img_width * bounding_box['Width'])
                                height = int(img_height * bounding_box['Height'])

                                # Draw a rectangle on the image with transperancy 80% and a shade of blue
                                # Create a transparent overlay for highlighting text
                                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                draw = ImageDraw.Draw(overlay)
                                
                                # Draw a semi-transparent blue rectangle
                                draw.rectangle(
                                    [(left, top), (left + width, top + height)],
                                    fill=(0, 255, 0, 64)  # RGBA: Green with 25% opacity
                                )
                                
                                # Combine the original image with the overlay
                                img = Image.alpha_composite(img.convert('RGBA'), overlay)

                            for block in page_header_blocks:
                                bounding_box = block['Geometry']['BoundingBox']
                                left = int(img_width * bounding_box['Left'])
                                top = int(img_height * bounding_box['Top'])
                                width = int(img_width * bounding_box['Width'])
                                height = int(img_height * bounding_box['Height'])

                                # Draw a rectangle on the image with transperancy 80% and a shade of blue
                                # Create a transparent overlay for highlighting text
                                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                draw = ImageDraw.Draw(overlay)
                                
                                # Draw a semi-transparent blue rectangle
                                draw.rectangle(
                                    [(left, top), (left + width, top + height)],
                                    fill=(128, 0, 128, 64)  # RGBA: Purple with 25% opacity
                                )
                                
                                # Combine the original image with the overlay
                                img = Image.alpha_composite(img.convert('RGBA'), overlay)

                            for block in page_footer_blocks:
                                bounding_box = block['Geometry']['BoundingBox']
                                left = int(img_width * bounding_box['Left'])
                                top = int(img_height * bounding_box['Top'])
                                width = int(img_width * bounding_box['Width'])
                                height = int(img_height * bounding_box['Height'])

                                # Draw a rectangle on the image with transperancy 80% and a shade of blue
                                # Create a transparent overlay for highlighting text
                                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                draw = ImageDraw.Draw(overlay)
                                
                                # Draw a semi-transparent blue rectangle
                                draw.rectangle(
                                    [(left, top), (left + width, top + height)],
                                    fill=(255, 255, 0, 64)  # RGBA: Yellow with 25% opacity
                                )
                                
                                # Combine the original image with the overlay
                                img = Image.alpha_composite(img.convert('RGBA'), overlay)

                            st.image(img, use_container_width=True)
                        with col2:
                            st.subheader("Extracted Text")
                            for block in page_line_blocks:
                                st.markdown(
                                    f'<p style="color: #FF0000; font-size: 12px;">{block["Text"]}</p>', 
                                    unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error loading processed file: {e}")
                    with st.expander("Show Error Traceback"):
                        st.code(traceback.format_exc())

if __name__ == "__main__":
    st.set_page_config(page_title="Document Processing Viewer", layout="wide")
    main()