# Form Classifier

A Python application that classifies PDF forms using Google's Gemini 2.5 Flash Lite AI model.

## Features

- Uploads PDF files directly to Gemini AI (no text extraction needed)
- Processes Hebrew PDF forms with visual analysis capabilities
- Classifies forms using detailed AI analysis with form number validation
- Verifies classifications against expected form data (number, title, page count)
- Outputs comprehensive results including confidence levels and reasoning
- Supports detailed form number validation with alternative candidate detection
- Command-line interface

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up API key:**
   Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
   Or provide the API key via command line argument.

3. **Prepare form configuration:**
   Edit `form_config.json` with your expected form data in this format:
   ```json
   [
       {
           "form_number": "1234",
           "expected_title": "כותרת הטופס בעברית",
           "expected_pages": 3
       }
   ]
   ```

## Usage

```bash
python form_classifier.py <folder_path> <config_file> <output_file> [--api-key API_KEY]
```

### Parameters

- `folder_path`: Path to folder containing PDF files
- `config_file`: Path to JSON file with expected form data (default: `form_config.json`)
- `output_file`: Path to output file for results (JSON format)
- `--api-key`: Optional Google Gemini API key (if not set in environment)

### Example

```bash
python form_classifier.py ./pdf_forms/ form_config.json results.json
```

## Output

The application generates two output files:

### 1. Results File (JSON)
Detailed technical results for each processed PDF:

```json
[
    {
        "filename": "form1.pdf",
        "form_number": "1234",
        "form_title": "כותרת הטופס",
        "page_count": 3,
        "confidence": 92,
        "is_verified": true,
        "token_usage": {
            "input_tokens": 150,
            "output_tokens": 25,
            "total_tokens": 175
        },
        "llm_response": {
            "form_classification": {
                "form_number": {
                    "value": "1234",
                    "confidence_level": 92,
                    "reasoning": "Found primary form number as standalone identifier in top-left corner.",
                    "extraction_location": "Page 1, top-left corner, standalone number",
                    "alternative_candidates": ["1235"],
                    "form_number_validation": {
                        "is_single_number": true,
                        "found_references_to_other_forms": [],
                        "primary_vs_reference_confidence": 88
                    }
                },
                "form_title": {
                    "value": "כותרת הטופס",
                    "confidence_level": 88,
                    "reasoning": "Main title appears prominently below header",
                    "extraction_location": "Page 1, center-top below header",
                    "language": "hebrew"
                },
                "page_count": {
                    "value": 3,
                    "confidence_level": 95,
                    "reasoning": "Document has clear page numbers at bottom of each page",
                    "extraction_method": "Page number counting"
                }
            },
            "processing_metadata": {
                "overall_confidence": 91,
                "processing_notes": "Well-formatted official document",
                "potential_issues": [],
                "recommended_human_review": false
            }
        },
        "error": null
    }
]
```

### 2. Statistics File (HTML)
Professional HTML table with color coding and formatting:

**Features:**
- ✅ **Color-coded confidence levels** (Green/Yellow/Orange)
- ✅ **Success indicators** (Green/Red)
- ✅ **Token usage tracking** (Input/Output tokens)
- ✅ **Hebrew text support** with proper formatting
- ✅ **Hover effects** and professional styling
- ✅ **True data appending** (never overwrites existing data)
- ✅ **Robust HTML parsing** (handles malformed HTML gracefully)
- ✅ **Summary statistics** at the top (updated with each run)
- ✅ **Responsive design** that works in any browser

The HTML file includes professional styling with:
- **Color-coded confidence levels** (green/yellow/orange based on confidence scores)
- **Success indicators** (green for verified, red for failed)
- **Token usage tracking** (monospace font for easy reading)
- **Hebrew text preservation** and proper formatting
- **Hover effects** and responsive design
- **Summary statistics** showing totals and success rates

**Double-click `classification_stats.html` to open a beautifully formatted table in your browser!**

## Usage

```bash
python form_classifier.py <folder_path> <config_file> <output_file> [--stats stats_file]
```

### Parameters

- `folder_path`: Path to folder containing PDF files
- `config_file`: Path to JSON file with expected form data (default: `form_config.json`)
- `output_file`: Path to output file for results (JSON format)
- `--stats`: Optional path to statistics file (default: `classification_stats.html`)

### Example

```bash
python form_classifier.py ./pdf_forms/ form_config.json results.json --stats my_stats.html
```

## Verification Logic

The application verifies classifications by:

1. **Form Number Matching**: Comparing the detected form number against the configuration
2. **Title Verification**: Uses "contains" logic - if expected title is contained within extracted title
3. **Page Count Validation**: Verifying the page count matches the expected count
4. **Confidence Assessment**: Only if all three match is the classification considered verified

### Title Matching Logic
- **Flexible Matching**: Uses `expected_title in extracted_title` instead of exact match
- **Handles Preamble Text**: Ignores contextual text like "נספח א", years, or form references
- **Maintains Precision**: Still requires the core title to be present
- **Example**: If config has "חישוב ההכנסה החייבת" and AI extracts "נספח א חישוב ההכנסה החייבת", it will match ✅

### LLM Configuration for PII-Sensitive Content
- **Temperature: 0.1** - Balanced randomness for flexibility with PII content
- **Top-P: 0.3** - Nucleus sampling for focused responses with some variety
- **Top-K: 5** - Consider more tokens for better PII handling
- **Single Candidate** - Generate only one response per request
- **Fresh Model Instance** - New model created for each file (prevents state carryover)
- **Relaxed Safety Settings** - Reduced sensitivity to PII in legitimate forms
- **Enhanced Error Reporting** - Detailed safety filter information and troubleshooting
- **Robust Parsing** - Improved error handling for edge cases

### Why Fresh Model Instances?
When processing multiple PDF files, we create a **new model instance for each file** instead of reusing the same model. This prevents:
- **State carryover** between API calls
- **Context contamination** from previous files
- **Inconsistent responses** for later files
- **Memory accumulation** in the model

Each file gets processed with a "clean slate" model, ensuring consistent results regardless of processing order or previous files.

### Maximum Permissive Safety Settings
The application uses the most permissive safety settings available for processing legitimate government forms:

```python
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
]
```

**Warning**: `BLOCK_NONE` disables all safety filters. Use only for legitimate document processing. If you still get safety errors, the content may genuinely violate the API terms of service.

This configuration is designed to handle:
- **Personal identification data** (names, ID numbers, etc.)
- **Financial information** (tax forms, income data)
- **Official documents** (government forms with sensitive but legitimate content)

The AI model provides detailed reasoning and confidence levels for each extraction, along with alternative candidates and validation metadata for robust form number identification.

## Troubleshooting

### Safety Filter Issues (finish_reason = 2)
If you see `SAFETY` errors in the detailed error reports, this indicates the model refused to process content due to safety filters:

**Common Causes:**
- **Personal Identifiable Information** (PII) in forms
- **Financial data** triggering compliance filters
- **Official documents** with sensitive content

**Solutions:**
1. **Safety Settings**: The app uses `BLOCK_NONE` (disables all safety filters)
2. **Model Choice**: Flash model is more permissive than Pro models
3. **Content Review**: If still getting errors, the content may genuinely violate terms of service
4. **Error Details**: Look at the detailed error report for specific safety ratings and guidance
5. **API Limits**: Some content may be blocked at the API level regardless of safety settings

### PII Handling
The application uses **BLOCK_NONE safety settings** (disables all safety filters) for processing legitimate government forms:

**Safety Configuration:**
- **BLOCK_NONE** for all harm categories (maximum permissiveness)
- **Form-specific context** in prompts
- **PII-aware processing** for official documents
- **Enhanced error reporting** when safety filters trigger

**Important Warning**: `BLOCK_NONE` disables ALL safety filters. This is appropriate for legitimate document processing but may allow inappropriate content. Use responsibly.

**Note**: If you're still getting safety errors with `BLOCK_NONE`, the content may genuinely violate the Gemini API terms of service at the infrastructure level.

## How It Works

1. **PDF Upload**: The application uploads your PDF files directly to Gemini AI
2. **Visual Analysis**: Gemini analyzes the visual content, layout, and structure of the documents
3. **Hebrew Processing**: AI processes Hebrew text while preserving formatting and context
4. **Classification**: Extracts form number, title, and page count using advanced analysis
5. **Verification**: Compares results against your configuration file
6. **Results**: Generates detailed JSON output with confidence scores and reasoning

## Requirements

- Python 3.8+
- PDF files (Hebrew forms)
- Google Gemini API key
- Configuration file with expected form data
- Internet connection (for file uploads to Gemini)
