import logging
from transformers import pipeline
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize translator
translator = pipeline(
    "translation", 
    model="Helsinki-NLP/opus-mt-en-zh",
    tokenizer="Helsinki-NLP/opus-mt-en-zh",
    device=-1
)

def split_into_sentences(text):
    """Split text into sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

async def translate_content(content: str, translator) -> dict:
    """
    Translate English content to Chinese.
    Handles long text by splitting into sentences and translating in smaller chunks.
    """
    try:
        if not content:
            return None
            
        # Clean and prepare content
        content = content.strip()
        
        # Split into sentences
        sentences = split_into_sentences(content)
        
        # Group sentences into smaller chunks (max 200 chars per chunk)
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            if current_length + len(sentence) > 200:
                if current_chunk:  # Save current chunk if it exists
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = len(sentence)
            else:
                current_chunk.append(sentence)
                current_length += len(sentence)
                
        if current_chunk:  # Add the last chunk
            chunks.append(' '.join(current_chunk))
        
        # Translate chunks
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            try:
                logger.info(f"Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                translation = translator(chunk, max_length=512)[0]['translation_text']
                translated_chunks.append(translation)
            except Exception as e:
                logger.error(f"Error translating chunk {i+1}: {str(e)}")
                translated_chunks.append(f"[Translation Error for chunk {i+1}]")
            
        # Combine translated chunks
        full_translation = ' '.join(translated_chunks)
        
        return {
            "original": content,
            "translation": {
                "zh": full_translation
            }
        }
        
    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        return None
