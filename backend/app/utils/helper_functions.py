import base64
import re
from io import BytesIO

import pytesseract
from PIL import Image, ImageDraw


def extract_keywords(answer: str):
    """
    Extracts keywords from the given text if the word 'keywords' appears anywhere in the text.
    It captures everything after '**Keywords:**' (case-insensitive) and returns a list of keywords
    by extracting text enclosed in single quotes.

    Example:
        input: "**Keywords:** 'Equals', 'CAP', '$35,636,692','$9,288,633'"
        output: ['Equals', 'CAP', '$35,636,692', '$9,288,633']
    """
    match = re.search(r'(?i)\*\*keywords:\*\*\s*(.+)', answer)
    if match:
        keywords_text = match.group(1)
        # Extract content within single quotes
        return re.findall(r"'([^']+)'", keywords_text)
    return []


def remove_keywords(answer: str) -> str:
    """
    Removes the keywords section from the text if '**Keywords:**' (case-insensitive) appears anywhere.
    It removes everything from '**Keywords:**' to the end of the text and returns the cleaned string.

    Example:
        input: "This is the main text. **Keywords:** 'Equals', 'CAP', '$35,636,692','$9,288,633'"
        output: "This is the main text."
    """
    # Split the text at the '**Keywords:**' marker (case-insensitive) and return the part before it.
    parts = re.split(r'(?i)\*\*keywords:\*\*', answer, maxsplit=1)
    return parts[0].strip()


def highlight_keywords_in_image(image_b64: str, keywords: list) -> str:
    """
    Accepts an image in base64 format and a list of keywords. Performs OCR on the image using Tesseract,
    highlights the bounding boxes for any words that match the keywords (even if they include punctuation or extra spaces),
    and returns the highlighted image as a base64-encoded PNG.
    """
    # If the base64 string has a data URL header, remove it.
    if image_b64.startswith('data:image'):
        image_b64 = image_b64.split(',')[1]

    # Decode the base64 string and open the image.
    image_data = base64.b64decode(image_b64)
    img = Image.open(BytesIO(image_data)).convert('RGB')

    # Create a drawing context with support for transparency.
    draw = ImageDraw.Draw(img, 'RGBA')

    # Perform OCR to get word-level bounding boxes.
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Iterate over each detected word.
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        # Normalize by removing spaces before comparing.
        if any(
            keyword.replace(' ', '').lower() in text.replace(' ', '').lower()
            for keyword in keywords
        ):
            left = data['left'][i]
            top = data['top'][i]
            width = data['width'][i]
            height = data['height'][i]
            rect = [left, top, left + width, top + height]
            # Draw a semi-transparent yellow rectangle over the matched word.
            draw.rectangle(rect, fill=(255, 255, 0, 128))

    # Save the modified image to a bytes buffer and encode it back to base64.
    buffered = BytesIO()
    img.save(buffered, format='PNG')
    highlighted_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return highlighted_b64
