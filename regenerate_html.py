import json
from form_classifier import FormClassifier, ClassificationResult

# Load results
with open('results_testfolder.json', 'r', encoding='utf-8') as f:
    results_data = json.load(f)

# Convert dictionaries to ClassificationResult objects
results = []
for data in results_data:
    result = ClassificationResult(
        filename=data['filename'],
        form_number=data['form_number'],
        form_title=data['form_title'],
        page_count=data['page_count'],
        confidence=data['confidence'],
        llm_response=data['llm_response'],
        is_verified=data['is_verified'],
        token_usage=data['token_usage'],
        match_type=data.get('match_type'),
        matched_title=data.get('matched_title'),
        matched_form_number=data.get('matched_form_number'),
        error=data.get('error')
    )
    results.append(result)

# Create classifier instance (just to use save_stats method)
# API key not needed for save_stats, so use dummy value
classifier = FormClassifier('dummy_key', 'form_config.json')

# Delete old HTML file first
import os
if os.path.exists('classification_stats.html'):
    os.remove('classification_stats.html')
    print("Deleted old HTML file")

# Regenerate HTML
classifier.save_stats(results, 'classification_stats.html')

print("HTML regenerated successfully!")

