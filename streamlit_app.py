import os
import streamlit as st
from PIL import Image
import tempfile
import shutil
import traceback
import logging
import sys
from pymupdf import fitz

# Configure logging
def setup_logging(temp_folder):
    """
    Set up logging to both console and file.
    
    Args:
        temp_folder (str): Folder to store log files
    
    Returns:
        logging.Logger: Configured logger
    """
    # Ensure log will be in the same folder as output
    log_file = os.path.join(temp_folder, 'pdf_flipbook.log')
    
    # Configure logger
    logger = logging.getLogger('PDFFlipBook')
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)
    
    # File handler for detailed logs
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d: %(message)s')
    file_handler.setFormatter(file_format)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger, log_file

def convert_pdf_to_images(uploaded_file, temp_folder, logger, dpi=200, max_image_size=1024, quality=85):
    """
    Convert PDF to compressed images with enhanced error handling and logging.
    
    Args:
        uploaded_file (UploadedFile): Streamlit uploaded PDF file
        temp_folder (str): Path to temporary folder for storing images
        logger (logging.Logger): Logger for tracking events
        dpi (int): Dots per inch for image rendering (reduced for smaller file size)
        max_image_size (int): Maximum width/height for image resizing
        quality (int): JPEG compression quality (0-95, lower means smaller file)
    
    Returns:
        tuple: (list of image paths, total page count)
    """
    pdf_document = None
    try:
        # Ensure the temporary folder exists
        os.makedirs(temp_folder, exist_ok=True)
        
        # Save uploaded PDF
        pdf_path = os.path.join(temp_folder, 'uploaded.pdf')
        with open(pdf_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        logger.info(f"PDF saved to {pdf_path}")
        
        # Open the PDF with careful error handling
        try:
            pdf_document = fitz.open(pdf_path)
            total_pages = pdf_document.page_count
            logger.info(f"Opened PDF with {total_pages} pages")
        except Exception as open_error:
            logger.error(f"Error opening PDF document: {open_error}")
            logger.error(traceback.format_exc())
            raise
        
        # Store image paths
        image_paths = []
        
        # Convert each page to a compressed image
        for page_num in range(total_pages):
            # Get the page
            try:
                page = pdf_document[page_num]
                
                # Render page to an image with specified DPI
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
                
                # Convert to PIL Image for further processing
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Resize image if it's larger than max_image_size
                if max(image.width, image.height) > max_image_size:
                    image.thumbnail((max_image_size, max_image_size), Image.LANCZOS)
                
                # Create image path
                image_path = os.path.join(temp_folder, f'page_{page_num+1}.jpg')
                
                # Save the image with compression
                image.save(image_path, 'JPEG', optimize=True, quality=quality)
                image_paths.append(image_path)
                
                logger.debug(f"Generated compressed image for page {page_num + 1}")
            except Exception as page_error:
                logger.error(f"Error processing page {page_num + 1}: {page_error}")
                logger.error(traceback.format_exc())
        
        return image_paths, total_pages
    
    except Exception as e:
        logger.error(f"Error in convert_pdf_to_images: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        # Ensure PDF document is closed
        if pdf_document:
            try:
                pdf_document.close()
                logger.info("PDF document closed successfully")
            except Exception as close_error:
                logger.error(f"Error closing PDF document: {close_error}")

def main():
    st.set_page_config(layout="wide", page_title="PDF Flip Book")
    
    st.title('PDF Flip Book')
    
    # Initialize session state for page number and temporary folder
    if 'page_number' not in st.session_state:
        st.session_state.page_number = 1
    
    # Temporary folder selection
    st.sidebar.header('Temporary Folder Settings')
    
    # Option to use default or custom temporary folder
    folder_option = st.sidebar.radio(
        'Temporary Folder',
        ['Use System Temp', 'Choose Custom Folder']
    )
    
    if folder_option == 'Use System Temp':
        # Use Python's tempfile to create a temporary directory
        temp_folder = tempfile.mkdtemp(prefix='pdf_flipbook_')
    else:
        # Allow user to select a custom folder
        custom_folder = st.sidebar.text_input(
            'Enter full path to temporary folder',
            value=os.path.expanduser('~')
        )
        
        # Create the custom folder if it doesn't exist
        try:
            os.makedirs(custom_folder, exist_ok=True)
            temp_folder = os.path.join(
                custom_folder, 
                f'pdf_flipbook_{os.getpid()}'
            )
            os.makedirs(temp_folder, exist_ok=True)
        except Exception as e:
            st.sidebar.error(f"Could not create folder: {e}")
            temp_folder = tempfile.mkdtemp(prefix='pdf_flipbook_')
    
    # Set up logging
    logger, log_file = setup_logging(temp_folder)
    
    # PDF Upload
    uploaded_pdf = st.file_uploader(
        "Upload a PDF to create a Flip Book", 
        type=['pdf']
    )
    
    if uploaded_pdf is not None:
        try:
            # Attempt to convert PDF to images with logging
            logger.info(f"Attempting to convert PDF: {uploaded_pdf.name}")
            image_paths, total_pages = convert_pdf_to_images(
                uploaded_pdf, 
                temp_folder, 
                logger
            )
            
            # Main display column
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Navigation buttons
                col_prev, col_mid, col_next = st.columns([1,2,1])
                
                with col_prev:
                    prev_button = st.button('Previous Page', 
                        disabled=st.session_state.page_number <= 1
                    )
                
                with col_next:
                    next_button = st.button('Next Page', 
                        disabled=st.session_state.page_number >= total_pages
                    )
                
                # Handle page navigation
                if prev_button and st.session_state.page_number > 1:
                    st.session_state.page_number -= 1
                elif next_button and st.session_state.page_number < total_pages:
                    st.session_state.page_number += 1
                
                # Load and display selected page
                try:
                    selected_page = Image.open(
                        image_paths[st.session_state.page_number - 1]
                    )
                    # Replace use_c_width with width parameter
                    st.image(selected_page, width=700)
                except Exception as img_error:
                    logger.error(f"Error loading image: {img_error}")
                    logger.error(traceback.format_exc())
                    st.error(f"Could not load page image: {img_error}")
                
                # Display current page number
                st.write(f'Page {st.session_state.page_number} of {total_pages}')
            
            with col2:
                # Thumbnail navigation
                st.write('### Page Thumbnails')
                
                # Create thumbnails
                try:
                    thumbnails = []
                    for path in image_paths:
                        try:
                            thumb = Image.open(path)
                            thumb.thumbnail((150, 200))
                            thumbnails.append(thumb)
                        except Exception as thumb_error:
                            logger.error(f"Error creating thumbnail: {thumb_error}")
                            logger.error(traceback.format_exc())
                    
                    # Display thumbnails with selection
                    selected_thumbnail = st.radio(
                        'Jump to Page', 
                        range(1, total_pages + 1),
                        index=st.session_state.page_number - 1
                    )
                    
                    # Update page number if thumbnail is selected
                    if selected_thumbnail != st.session_state.page_number:
                        st.session_state.page_number = selected_thumbnail
                    
                    # Show selected thumbnail
                    st.image(thumbnails[selected_thumbnail - 1], width=150)
                
                except Exception as thumbnail_error:
                    logger.error(f"Error processing thumbnails: {thumbnail_error}")
                    logger.error(traceback.format_exc())
                    st.error("Could not process thumbnails")
            
            # Cleanup option
            if st.button('Clear Uploaded PDF'):
                # Remove temporary files
                try:
                    shutil.rmtree(temp_folder)
                    st.success('Temporary files cleared')
                except Exception as cleanup_error:
                    logger.error(f"Error clearing temporary files: {cleanup_error}")
                    logger.error(traceback.format_exc())
                    st.error(f"Could not clear temporary files: {cleanup_error}")
                
                # Reset page number
                st.session_state.page_number = 1
            
            # Display temporary folder and log file paths
            st.sidebar.info(f"Temporary folder: {temp_folder}")
            st.sidebar.info(f"Log file: {log_file}")
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            st.error(f"An unexpected error occurred: {e}")
            # Optional: Show log file path for debugging
            st.error(f"Check log file for details: {log_file}")

if __name__ == '__main__':
    main()