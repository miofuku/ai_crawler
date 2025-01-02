import logging
from transformers import pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize models
summarizer = pipeline(
    "summarization", 
    model="sshleifer/distilbart-cnn-12-6",
    device=-1
)

translator = pipeline(
    "translation", 
    model="Helsinki-NLP/opus-mt-en-zh",
    tokenizer="Helsinki-NLP/opus-mt-en-zh",
    device=-1
)

async def summarize_content(content: str, summarizer, translator) -> dict:
    """Summarize and translate content"""
    try:
        if not content:
            return None
            
        # Clean content
        cleaned_content = ' '.join(str(content).split())
        
        # Split content into paragraphs
        paragraphs = [p.strip() for p in cleaned_content.split('\n') if p.strip()]
        
        # Combine paragraphs into a single text for initial summarization
        full_text = ' '.join(paragraphs)
        
        # Generate initial summary with dynamic max_length
        input_length = len(full_text[:1024])
        max_length = min(150, input_length - 10)
        min_length = min(50, max_length - 10)

        initial_summary = summarizer(
            full_text[:1024],
            max_length=max_length,
            min_length=min_length,
            do_sample=False
        )
        summary_en = initial_summary[0]['summary_text'] if initial_summary else ""
        
        # Extract key points
        key_points_en = []
        chunk_size = 1024
        chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        for chunk in chunks:
            chunk_length = len(chunk)
            max_length = min(50, chunk_length - 5)
            min_length = min(20, max_length - 5)

            point_summary = summarizer(
                chunk,
                max_length=max_length,
                min_length=min_length,
                do_sample=False
            )
            if point_summary:
                key_points_en.append(point_summary[0]['summary_text'])
        
        # Translate summaries
        summary_zh = translator(summary_en)[0]['translation_text'] if summary_en else ""
        key_points_zh = [translator(point)[0]['translation_text'] for point in key_points_en]
        
        return {
            "summary": {
                "en": summary_en,
                "zh": summary_zh
            },
            "key_points": {
                "en": key_points_en,
                "zh": key_points_zh
            }
        }
        
    except Exception as e:
        logger.error(f"Error in summarize_content: {e}")
        return None
