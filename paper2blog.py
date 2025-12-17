#!/usr/bin/env python3
"""
paper2blog - Convert academic papers to WeChat-style Markdown blog posts

This script provides functionality to convert arXiv papers to Markdown blog posts
with embedded images in a WeChat public account style.

python paper2blog.py 2510.27350
"""
import argparse
import sys
import os
import logging
from pathlib import Path
import re
import fitz  # PyMuPDF
from openai import OpenAI
from core import get_latex_from_arxiv_with_timeout, find_image_files, copy_image_assets_from_cache
from prompts import PromptManager
from weixin import upload_media_to_weixin, access_token

# Initialize OpenAI client
client = OpenAI(
    base_url='https://api-inference.modelscope.cn/v1',
    api_key='ms-96bf3c2c-e90c-4793-9586-37a482e23856', # ModelScope Token
)
# 'Qwen/Qwen2.5-7B-Instruct' 'Qwen/Qwen3-32B' 'Qwen/Qwen2.5-72B-Instruct'(图片引用差,输出中断)
# 'deepseek-ai/DeepSeek-V3.2'(较好) 'deepseek-ai/DeepSeek-V3.1'(较好) 'deepseek-ai/DeepSeek-R1-0528'
# 'MiniMax/MiniMax-M2'(图片引用最佳,文本流畅) 'MiniMax/MiniMax-M1-80k'(像AI风格) 'ZhipuAI/GLM-4.6'(输出中断) 
model_to_use = 'deepseek-ai/DeepSeek-V3.2' 

UPLOAD_WEIXIN = True  # 是否上传图片到微信服务器

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def convert_pdf_to_png(pdf_path: str, output_dir: str) -> str | None:
    """
    Convert a PDF file to PNG format using PyMuPDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save the PNG file
        
    Returns:
        Path to the converted PNG file, or None if conversion failed
    """
    try:
        # Open the PDF file
        # logger.info(f"Converting PDF to PNG: {pdf_path}")
        doc = fitz.open(pdf_path)
        
        if doc.page_count == 0:
            logger.warning(f"No pages found in PDF: {pdf_path}")
            doc.close()
            return None
            
        # Get the first page
        page = doc[0]
        
        # Render page to an image (2x zoom for better quality)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        
        # Create output filename - place in figures/ directory
        pdf_filename = os.path.basename(pdf_path)
        png_filename = os.path.splitext(pdf_filename)[0] + ".png"
        # Ensure the PNG is saved in the figures/ directory
        png_path = os.path.join(output_dir, "figures", png_filename)
        
        # Save as PNG
        pix.save(png_path)
        pix = None  # Free pixmap memory
        doc.close()
        
        # logger.info(f"Converted {pdf_path} to {png_path}")
        # Return the path relative to output_directory for use in prompts
        return os.path.join("figures", png_filename)
    except Exception as e:
        logger.error(f"Error converting PDF to PNG: {e}")
        return None

def process_image_files(output_directory: str, image_paths: list[str]) -> list[str]:
    """
    Process image files, converting PDFs to PNGs where necessary.
    
    Args:
        output_directory: Directory containing the image files
        image_paths: List of image file paths
        
    Returns:
        Updated list of image paths with PDFs converted to PNGs
    """
    processed_paths = []
    
    for image_path in image_paths:
        full_path = os.path.join(output_directory, image_path)
        
        # Check if it's a PDF file
        if image_path.lower().endswith('.pdf'):
            # Convert PDF to PNG
            png_path = convert_pdf_to_png(full_path, output_directory)
            if png_path:
                # Use the converted PNG path
                img_path = png_path
            else:
                # If conversion failed, keep the original PDF path
                logger.warning(f"Failed to convert PDF to PNG, keeping original: {image_path}")
                img_path = image_path
        else:
            # For non-PDF files, keep the original path
            img_path = image_path
        
        # 上传图片到微信服务器，获取media_url替换本地路径
        if UPLOAD_WEIXIN:
            if img_path.lower().endswith('.png') or img_path.lower().endswith('.jpg') or img_path.lower().endswith('.jpeg'):
                img_path = os.path.join(output_directory, img_path)
                print('img_path', img_path)
                thumb_media_id, media_url = upload_media_to_weixin(access_token, img_path)
                img_path = media_url
            
        processed_paths.append(img_path)
        
    return processed_paths

def generate_blog_post(
    arxiv_id: str,
    api_key: str | None = None,
    model_name: str = "gpt-4.1-2025-04-14",
    language: str = "zh",
) -> bool:
    """
    Generate a WeChat-style blog post from an arXiv paper.
    
    Args:
        arxiv_id: The arXiv ID of the paper to process
        api_key: API key for the LLM service
        model_name: Name of the model to use
        language: Language for the blog post ("en" for English, "zh" for Chinese)
        
    Returns:
        True if successful, False otherwise
    """
    # Define paths
    cache_dir = f"cache/{arxiv_id}"
    output_directory = f"blog/{arxiv_id}/"
    blog_md_path = f"{output_directory}blog.md"
    
    # Create directories if not exist
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(output_directory, exist_ok=True)
    os.makedirs(os.path.join(output_directory, "figures"), exist_ok=True)  # Ensure figures/ directory exists
    
    # Fetch LaTeX source
    logger.info("Fetching LaTeX source from arXiv...")
    latex_source = get_latex_from_arxiv_with_timeout(arxiv_id, cache_dir)
    if latex_source is None:
        logger.error(
            "Failed to retrieve LaTeX source from arXiv within timeout. Aborting generation."
        )
        return False
    
    # Ensure figures and images referenced by the paper are available under blog/<id>/
    try:
        copy_image_assets_from_cache(arxiv_id, cache_dir, output_directory)
    except Exception as e:
        logger.debug(f"Copying image assets skipped due to error: {e}")
    
    # Find images under output dir to include in blog post
    image_paths = find_image_files(output_directory)
    logger.info(f"Found {len(image_paths)} image files for potential inclusion")
    
    # Process image files (convert PDFs to PNGs)
    processed_image_paths = process_image_files(output_directory, image_paths)
    logger.info(f"Processed image files: {len(processed_image_paths)} paths available")
    
    # Initialize prompt manager
    prompt_manager = PromptManager()
    
    # Build prompt for blog post generation
    system_message, user_prompt = prompt_manager.build_blog_prompt(
        latex_source=latex_source,
        image_paths=processed_image_paths,
        language=language,
    )
    
    try:
        rechat = 2 # 重试次数
        while rechat>0:
            logger.info(f"LLM chating: {model_to_use}")
            
            # set extra_body for thinking control
            extra_body = {
                # enable thinking, set to False to disable
                "enable_thinking": False
            }
            
            response = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                max_tokens=4000,
                timeout=600,  # 默认30秒超时
                extra_body=extra_body,
            )
            
            logger.info(f"Received response from LLM.")
            
            # Extract blog content from response
            blog_content = extract_content_from_response(response, "markdown")
            
            if not blog_content:
                logger.error(f"No blog content found in the response: {response}")
                rechat -= 1
                # return False
            else:
                break
            
        # Save blog post
        with open(blog_md_path, "w", encoding="utf-8") as f:
            f.write(blog_content)
        logger.info(f"Blog post saved to {blog_md_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating blog post: {e}")
        return False

def extract_content_from_response(response, language: str = "markdown") -> str | None:
    """
    Extract content from LLM response.
    
    Args:
        response: Response from the language model
        language: Language to extract (default is 'markdown')
        
    Returns:
        Extracted content or None if not found
    """
    import re
    
    pattern = re.compile(rf"```{language}\s*(.*?)```", re.DOTALL)
    match = pattern.search(response.choices[0].message.content)
    content = match.group(1).strip() if match else None
    return content


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert arXiv papers to WeChat-style Markdown blog posts"
    )
    parser.add_argument(
        "arxiv_id",
        type=str,
        help="The arXiv ID of the paper to process",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="API key to use (overrides env). If omitted, uses OPENAI_API_KEY or DASHSCOPE_API_KEY.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4.1-2025-04-14",
        help="Model name to use (default: gpt-4.1-2025-04-14)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="zh",
        choices=["en", "zh"],
        help="Language for the blog post (en for English, zh for Chinese)",
    )
    
    args = parser.parse_args()
    
    if not generate_blog_post(
        args.arxiv_id,
        api_key=args.api_key,
        model_name=args.model,
        language=args.language,
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()